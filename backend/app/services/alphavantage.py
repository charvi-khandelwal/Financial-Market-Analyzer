from __future__ import annotations

import asyncio
import csv
import io
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.rate_limiter import MinuteRateLimiter

_quote_cache = TTLCache(maxsize=512, ttl=settings.CACHE_TTL_QUOTE)
_series_cache = TTLCache(maxsize=256, ttl=settings.CACHE_TTL_DAILY)
_intraday_cache = TTLCache(maxsize=128, ttl=settings.CACHE_TTL_INTRADAY)
_news_cache = TTLCache(maxsize=256, ttl=settings.CACHE_TTL_NEWS)
_universe_cache = TTLCache(maxsize=8, ttl=settings.CACHE_TTL_UNIVERSE)

_rl = MinuteRateLimiter(settings.MAX_CALLS_PER_MINUTE)


def _parse_keys() -> List[str]:
  keys: List[str] = []
  if settings.ALPHAVANTAGE_API_KEYS.strip():
    keys.extend([k.strip() for k in settings.ALPHAVANTAGE_API_KEYS.split(",") if k.strip()])
  if settings.ALPHAVANTAGE_API_KEY.strip():
    keys.append(settings.ALPHAVANTAGE_API_KEY.strip())
  numeric_env_keys = sorted(
    [
      env_key
      for env_key in os.environ.keys()
      if env_key.startswith("ALPHAVANTAGE_API_KEY_")
    ],
    key=lambda k: int(k.rsplit("_", 1)[1]) if k.rsplit("_", 1)[1].isdigit() else 10**9,
  )
  for env_key in numeric_env_keys:
    val = os.environ.get(env_key, "").strip()
    if val:
      keys.append(val)
  # Deduplicate while preserving order.
  seen = set()
  out: List[str] = []
  for key in keys:
    if key not in seen:
      seen.add(key)
      out.append(key)
  return out


@dataclass
class AlphaVantageClient:
  api_keys: List[str] = field(default_factory=_parse_keys)
  base_url: str = settings.ALPHAVANTAGE_BASE_URL
  _next_key_idx: int = 0
  _key_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

  def _maybe_rate_limit(self):
    if settings.ENABLE_SERVER_RATE_LIMIT:
      _rl.acquire()

  async def _take_next_key(self) -> str:
    if not self.api_keys:
      raise RuntimeError("No Alpha Vantage API keys configured.")
    async with self._key_lock:
      key = self.api_keys[self._next_key_idx]
      self._next_key_idx = (self._next_key_idx + 1) % len(self.api_keys)
      return key

  @staticmethod
  def _is_throttle_payload(payload: Dict[str, Any]) -> bool:
    if not isinstance(payload, dict):
      return False
    return "Note" in payload and isinstance(payload.get("Note"), str)

  @retry(wait=wait_exponential(multiplier=0.6, min=0.5, max=6), stop=stop_after_attempt(3))
  async def _get(self, params: Dict[str, Any]) -> Dict[str, Any]:
    self._maybe_rate_limit()
    base_params = dict(params)
    attempts = max(1, len(self.api_keys))

    for _ in range(attempts):
      key = await self._take_next_key()
      query = dict(base_params)
      query["apikey"] = key

      async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get(self.base_url, params=query)
        r.raise_for_status()
        data = r.json()

      if self._is_throttle_payload(data):
        continue
      return data

    # Return one payload with the next key so router can surface upstream detail.
    fallback_key = await self._take_next_key()
    query = dict(base_params)
    query["apikey"] = fallback_key
    async with httpx.AsyncClient(timeout=30) as http:
      r = await http.get(self.base_url, params=query)
      r.raise_for_status()
      return r.json()

  @retry(wait=wait_exponential(multiplier=0.6, min=0.5, max=6), stop=stop_after_attempt(3))
  async def _get_csv(self, params: Dict[str, Any]) -> List[Dict[str, str]]:
    self._maybe_rate_limit()
    base_params = dict(params)
    base_params["datatype"] = "csv"
    attempts = max(1, len(self.api_keys))

    for _ in range(attempts):
      key = await self._take_next_key()
      query = dict(base_params)
      query["apikey"] = key

      async with httpx.AsyncClient(timeout=60) as http:
        r = await http.get(self.base_url, params=query)
        r.raise_for_status()
        text = r.text

      # CSV success payload should contain a header row.
      if "{" in text and '"Note"' in text:
        continue
      rows = list(csv.DictReader(io.StringIO(text)))
      if rows:
        return rows

    fallback_key = await self._take_next_key()
    query = dict(base_params)
    query["apikey"] = fallback_key
    async with httpx.AsyncClient(timeout=60) as http:
      r = await http.get(self.base_url, params=query)
      r.raise_for_status()
      rows = list(csv.DictReader(io.StringIO(r.text)))
      return rows

  async def global_quote(self, symbol: str) -> Dict[str, Any]:
    key = ("GLOBAL_QUOTE", symbol.upper())
    if key in _quote_cache:
      return _quote_cache[key]
    data = await self._get({"function": "GLOBAL_QUOTE", "symbol": symbol.upper()})
    _quote_cache[key] = data
    return data

  async def time_series_daily(self, symbol: str, outputsize: str = "compact") -> Dict[str, Any]:
    key = ("TIME_SERIES_DAILY", symbol.upper(), outputsize)
    if key in _series_cache:
      return _series_cache[key]
    data = await self._get(
      {"function": "TIME_SERIES_DAILY", "symbol": symbol.upper(), "outputsize": outputsize}
    )
    _series_cache[key] = data
    return data

  async def time_series_intraday(
    self, symbol: str, interval: str = "5min", outputsize: str = "compact"
  ) -> Dict[str, Any]:
    key = ("TIME_SERIES_INTRADAY", symbol.upper(), interval, outputsize)
    if key in _intraday_cache:
      return _intraday_cache[key]
    data = await self._get(
      {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol.upper(),
        "interval": interval,
        "outputsize": outputsize,
      }
    )
    _intraday_cache[key] = data
    return data

  async def fx_daily(
    self, from_symbol: str, to_symbol: str, outputsize: str = "compact"
  ) -> Dict[str, Any]:
    key = ("FX_DAILY", from_symbol.upper(), to_symbol.upper(), outputsize)
    if key in _series_cache:
      return _series_cache[key]
    data = await self._get(
      {
        "function": "FX_DAILY",
        "from_symbol": from_symbol.upper(),
        "to_symbol": to_symbol.upper(),
        "outputsize": outputsize,
      }
    )
    _series_cache[key] = data
    return data

  async def crypto_daily(self, symbol: str, market: str = "USD") -> Dict[str, Any]:
    key = ("DIGITAL_CURRENCY_DAILY", symbol.upper(), market.upper())
    if key in _series_cache:
      return _series_cache[key]
    data = await self._get(
      {
        "function": "DIGITAL_CURRENCY_DAILY",
        "symbol": symbol.upper(),
        "market": market.upper(),
      }
    )
    _series_cache[key] = data
    return data

  async def news_sentiment(
    self,
    tickers: Optional[str] = None,
    topics: Optional[str] = None,
    time_from: Optional[str] = None,
    time_to: Optional[str] = None,
    sort: str = "LATEST",
    limit: int = 50,
  ) -> Dict[str, Any]:
    key = ("NEWS_SENTIMENT", tickers, topics, time_from, time_to, sort, limit)
    if key in _news_cache:
      return _news_cache[key]
    params: Dict[str, Any] = {"function": "NEWS_SENTIMENT", "sort": sort, "limit": limit}
    if tickers:
      params["tickers"] = tickers
    if topics:
      params["topics"] = topics
    if time_from:
      params["time_from"] = time_from
    if time_to:
      params["time_to"] = time_to
    data = await self._get(params)
    _news_cache[key] = data
    return data

  async def listing_status(self, state: str = "active") -> List[Dict[str, str]]:
    normalized_state = state.lower().strip() or "active"
    key = ("LISTING_STATUS", normalized_state)
    if key in _universe_cache:
      return _universe_cache[key]
    rows = await self._get_csv({"function": "LISTING_STATUS", "state": normalized_state})
    _universe_cache[key] = rows
    return rows


client = AlphaVantageClient()
