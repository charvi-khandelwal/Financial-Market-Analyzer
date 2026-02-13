import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

def _load_env_into_environ(env_file: str = ".env") -> None:
    """Load all key=value pairs from .env into os.environ so that
    numbered keys like ALPHAVANTAGE_API_KEY_1 are visible to os.environ
    look-ups (pydantic-settings only maps declared fields, not arbitrary keys)."""
    path = Path(env_file)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value

_load_env_into_environ()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ALPHAVANTAGE_API_KEY: str = ""
    ALPHAVANTAGE_API_KEYS: str = ""
    ALPHAVANTAGE_BASE_URL: str = "https://www.alphavantage.co/query"

    CACHE_TTL_QUOTE: int = 60
    CACHE_TTL_INTRADAY: int = 60
    CACHE_TTL_DAILY: int = 300
    CACHE_TTL_NEWS: int = 300
    CACHE_TTL_UNIVERSE: int = 1800

    ENABLE_SERVER_RATE_LIMIT: bool = True
    MAX_CALLS_PER_MINUTE: int = 5
    MARKET_SCHEDULER_ENABLED: bool = True
    MARKET_SCHEDULE_TIMEZONE: str = "UTC"
    MARKET_OVERVIEW_STOCKS: str = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,JPM,UNH,XOM"
    MARKET_OVERVIEW_CRYPTOS: str = "BTC,ETH,SOL,BNB,XRP,ADA,DOGE,AVAX"
    MARKET_OVERVIEW_FX_PAIRS: str = "EUR/USD,GBP/USD,USD/JPY,USD/CHF,AUD/USD,USD/CAD"
    MARKET_OVERVIEW_DATA_FILE: str = "data/market_overview.json"

settings = Settings()
