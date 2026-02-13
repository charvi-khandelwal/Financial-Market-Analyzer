from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from app.config import settings
from app.services.alphavantage import client
from app.services.analytics import (
    aggregate_news_sentiment,
    build_market_guidance,
    summarize_crypto_daily,
    summarize_fx_daily,
    summarize_timeseries_daily,
)

AV_CALL_SLEEP_SECONDS = max(0.05, 60.0 / max(settings.MAX_CALLS_PER_MINUTE, 1))


def _parse_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_fx_pairs(value: str) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for pair in _parse_csv(value):
        if "/" not in pair:
            continue
        from_symbol, to_symbol = pair.split("/", 1)
        pairs.append((from_symbol.strip().upper(), to_symbol.strip().upper()))
    return pairs


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _raise_if_av_error(data: Dict[str, Any]) -> None:
    if isinstance(data, dict) and ("Note" in data or "Information" in data or "Error Message" in data):
        raise RuntimeError(str(data))


class MarketOverviewService:
    def __init__(self) -> None:
        self.stocks = [s.upper() for s in _parse_csv(settings.MARKET_OVERVIEW_STOCKS)]
        self.cryptos = [s.upper() for s in _parse_csv(settings.MARKET_OVERVIEW_CRYPTOS)]
        self.fx_pairs = _parse_fx_pairs(settings.MARKET_OVERVIEW_FX_PAIRS)
        self.data_file = Path(settings.MARKET_OVERVIEW_DATA_FILE)
        self._task: Optional[asyncio.Task] = None
        self._refresh_task: Optional[asyncio.Task] = None
        self._snapshot: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()
        self._status_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._tz = self._resolve_tz(settings.MARKET_SCHEDULE_TIMEZONE)
        self._load_from_disk()
        latest_generated_at = None
        latest = self._snapshot.get("latest")
        if isinstance(latest, dict):
            latest_generated_at = latest.get("generated_at")
        self._refresh_status: Dict[str, Any] = {
            "state": "idle",
            "reason": None,
            "started_at": None,
            "finished_at": None,
            "total_steps": 0,
            "completed_steps": 0,
            "progress_percent": 0.0,
            "current_step": None,
            "message": None,
            "error": None,
            "latest_generated_at": latest_generated_at,
        }

    @staticmethod
    def _resolve_tz(name: str):
        if ZoneInfo is None:
            return timezone.utc
        try:
            return ZoneInfo(name)
        except Exception:
            return timezone.utc

    def _load_from_disk(self) -> None:
        if not self.data_file.exists():
            return
        try:
            self._snapshot = json.loads(self.data_file.read_text(encoding="utf-8"))
        except Exception:
            self._snapshot = {}

    def _persist(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(json.dumps(self._snapshot, ensure_ascii=True, indent=2), encoding="utf-8")

    @staticmethod
    def _seconds_until_next_half_hour(tz) -> float:
        now = datetime.now(tz)
        minute = now.minute
        next_minute = 30 if minute < 30 else 60
        next_slot = now.replace(second=0, microsecond=0)
        if next_minute == 60:
            next_slot = (next_slot + timedelta(hours=1)).replace(minute=0)
        else:
            next_slot = next_slot.replace(minute=30)
        return max((next_slot - now).total_seconds(), 1.0)

    @staticmethod
    def _latest_close(points: List[Dict[str, Any]]) -> Optional[float]:
        if not points:
            return None
        return points[0].get("close")

    def _total_steps(self) -> int:
        return len(self.stocks) + len(self.fx_pairs) + len(self.cryptos) + 1

    async def _set_refresh_status(self, **updates: Any) -> Dict[str, Any]:
        async with self._status_lock:
            self._refresh_status = {**self._refresh_status, **updates}
            return dict(self._refresh_status)

    async def _fetch_stock_rows(
        self,
        progress_cb: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        rows: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        for symbol in self.stocks:
            try:
                raw = await client.time_series_daily(symbol, outputsize="compact")
                _raise_if_av_error(raw)
                summary = summarize_timeseries_daily(raw)
                rows.append(
                    {
                        "asset_class": "stock",
                        "symbol": symbol,
                        "price": self._latest_close(summary.get("points", [])),
                        "momentum_1d": summary.get("momentum_1d"),
                        "volatility_proxy": summary.get("volatility_proxy"),
                        "last_refreshed": summary.get("last_refreshed"),
                    }
                )
            except Exception as exc:
                errors.append({"asset_class": "stock", "symbol": symbol, "error": str(exc)})
            if progress_cb:
                await progress_cb(f"Fetched stock {symbol}")
            await asyncio.sleep(AV_CALL_SLEEP_SECONDS)
        return rows, errors

    async def _fetch_crypto_rows(
        self,
        progress_cb: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        rows: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        for symbol in self.cryptos:
            try:
                raw = await client.crypto_daily(symbol, market="USD")
                _raise_if_av_error(raw)
                summary = summarize_crypto_daily(raw)
                rows.append(
                    {
                        "asset_class": "crypto",
                        "symbol": symbol,
                        "price": self._latest_close(summary.get("points", [])),
                        "momentum_1d": summary.get("momentum_1d"),
                        "volatility_proxy": None,
                        "last_refreshed": summary.get("last_refreshed"),
                    }
                )
            except Exception as exc:
                errors.append({"asset_class": "crypto", "symbol": symbol, "error": str(exc)})
            if progress_cb:
                await progress_cb(f"Fetched crypto {symbol}")
            await asyncio.sleep(AV_CALL_SLEEP_SECONDS)
        return rows, errors

    async def _fetch_fx_rows(
        self,
        progress_cb: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        rows: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []
        for from_symbol, to_symbol in self.fx_pairs:
            pair = f"{from_symbol}/{to_symbol}"
            try:
                raw = await client.fx_daily(from_symbol, to_symbol, outputsize="compact")
                _raise_if_av_error(raw)
                summary = summarize_fx_daily(raw)
                rows.append(
                    {
                        "asset_class": "fx",
                        "symbol": pair,
                        "price": self._latest_close(summary.get("points", [])),
                        "momentum_1d": summary.get("momentum_1d"),
                        "volatility_proxy": None,
                        "last_refreshed": summary.get("last_refreshed"),
                    }
                )
            except Exception as exc:
                errors.append({"asset_class": "fx", "symbol": pair, "error": str(exc)})
            if progress_cb:
                await progress_cb(f"Fetched FX {pair}")
            await asyncio.sleep(AV_CALL_SLEEP_SECONDS)
        return rows, errors

    async def refresh_once(self, reason: str = "manual", track_progress: bool = False) -> Dict[str, Any]:
        async with self._refresh_lock:
            total_steps = self._total_steps()
            completed_steps = 0

            async def mark_step(step_label: str) -> None:
                nonlocal completed_steps
                completed_steps += 1
                if track_progress:
                    progress_percent = round((completed_steps / total_steps) * 100, 2) if total_steps else 0.0
                    await self._set_refresh_status(
                        total_steps=total_steps,
                        completed_steps=completed_steps,
                        progress_percent=progress_percent,
                        current_step=step_label,
                        message=step_label,
                    )

            if track_progress:
                await self._set_refresh_status(
                    state="running",
                    reason=reason,
                    started_at=_iso_utc_now(),
                    finished_at=None,
                    total_steps=total_steps,
                    completed_steps=0,
                    progress_percent=0.0,
                    current_step="Starting refresh",
                    message="Starting refresh",
                    error=None,
                )

            try:
                stock_rows, stock_errors = await self._fetch_stock_rows(progress_cb=mark_step if track_progress else None)
                fx_rows, fx_errors = await self._fetch_fx_rows(progress_cb=mark_step if track_progress else None)
                crypto_rows, crypto_errors = await self._fetch_crypto_rows(progress_cb=mark_step if track_progress else None)

                news_raw = await client.news_sentiment(topics="financial_markets", limit=200)
                _raise_if_av_error(news_raw)
                news_summary = aggregate_news_sentiment(news_raw)
                if track_progress:
                    await mark_step("Fetched market news sentiment")

                sentiment_map = news_summary.get("ticker_average_sentiment", {}) or {}
                for row in stock_rows + crypto_rows + fx_rows:
                    row["sentiment"] = sentiment_map.get(row["symbol"])

                guidance = build_market_guidance(stock_rows, fx_rows, crypto_rows, news_summary)

                now_iso = _iso_utc_now()
                snapshot = {
                    "generated_at": now_iso,
                    "reason": reason,
                    "timezone": str(self._tz),
                    "coverage": {
                        "stocks": len(stock_rows),
                        "fx_pairs": len(fx_rows),
                        "cryptos": len(crypto_rows),
                    },
                    "stocks": stock_rows,
                    "fx": fx_rows,
                    "crypto": crypto_rows,
                    "news": news_summary,
                    "guidance": guidance,
                    "errors": stock_errors + fx_errors + crypto_errors,
                    "notes": [
                        "Coverage is based on configured watchlists and not every global tradable instrument.",
                        guidance.get("disclaimer"),
                    ],
                }

                async with self._lock:
                    history = self._snapshot.get("history", [])
                    history.append(snapshot)
                    self._snapshot = {
                        "latest": snapshot,
                        "history": history[-200:],
                    }
                    self._persist()

                if track_progress:
                    await self._set_refresh_status(
                        state="completed",
                        finished_at=_iso_utc_now(),
                        total_steps=total_steps,
                        completed_steps=total_steps,
                        progress_percent=100.0,
                        current_step="Completed",
                        message="Refresh completed successfully.",
                        error=None,
                        latest_generated_at=now_iso,
                    )

                return snapshot
            except Exception as exc:
                if track_progress:
                    await self._set_refresh_status(
                        state="failed",
                        finished_at=_iso_utc_now(),
                        current_step="Failed",
                        message="Refresh failed.",
                        error=str(exc),
                    )
                raise

    async def _run_refresh_task(self, reason: str) -> None:
        try:
            await self.refresh_once(reason=reason, track_progress=True)
        finally:
            self._refresh_task = None

    async def start_refresh(self, reason: str = "manual") -> Dict[str, Any]:
        async with self._start_lock:
            running = self._refresh_task is not None and not self._refresh_task.done()
            if running:
                return {"accepted": False, "status": await self.get_refresh_status()}

            latest_generated_at = self._refresh_status.get("latest_generated_at")
            status = await self._set_refresh_status(
                state="running",
                reason=reason,
                started_at=_iso_utc_now(),
                finished_at=None,
                total_steps=self._total_steps(),
                completed_steps=0,
                progress_percent=0.0,
                current_step="Queued",
                message="Refresh queued.",
                error=None,
                latest_generated_at=latest_generated_at,
            )
            self._refresh_task = asyncio.create_task(self._run_refresh_task(reason))
            return {"accepted": True, "status": status}

    async def get_refresh_status(self) -> Dict[str, Any]:
        async with self._status_lock:
            status = dict(self._refresh_status)
        running = self._refresh_task is not None and not self._refresh_task.done()
        status["is_running"] = running
        return status

    async def get_latest(self) -> Dict[str, Any]:
        async with self._lock:
            return self._snapshot.get("latest", {})

    async def get_history(self, limit: int = 48) -> List[Dict[str, Any]]:
        async with self._lock:
            history = self._snapshot.get("history", [])
            return history[-limit:]

    async def _scheduler_loop(self) -> None:
        while True:
            wait_seconds = self._seconds_until_next_half_hour(self._tz)
            await asyncio.sleep(wait_seconds)
            try:
                await self.start_refresh(reason="scheduled")
            except Exception:
                # Keep scheduler alive even if one cycle fails.
                continue

    async def start(self) -> None:
        if not settings.MARKET_SCHEDULER_ENABLED or self._task:
            return
        self._task = asyncio.create_task(self._scheduler_loop())

    async def stop(self) -> None:
        if not self._task:
            pass
        else:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None


market_overview_service = MarketOverviewService()
