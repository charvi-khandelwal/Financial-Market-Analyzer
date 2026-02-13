from fastapi import APIRouter, HTTPException, Query
from app.services.alphavantage import client
from app.services.analytics import (
    summarize_quote, summarize_timeseries_daily, summarize_fx_daily, summarize_crypto_daily
)

router = APIRouter(prefix="/market", tags=["market"])

def _raise_if_av_error(data):
    if isinstance(data, dict) and ("Note" in data or "Information" in data or "Error Message" in data):
        raise HTTPException(status_code=502, detail=data)

@router.get("/quote")
async def quote(symbol: str = Query(..., min_length=1)):
    data = await client.global_quote(symbol)
    _raise_if_av_error(data)
    return summarize_quote(data)

@router.get("/stocks/daily")
async def stock_daily(symbol: str, outputsize: str = "compact"):
    data = await client.time_series_daily(symbol, outputsize=outputsize)
    _raise_if_av_error(data)
    return summarize_timeseries_daily(data)

@router.get("/stocks/intraday")
async def stock_intraday(symbol: str, interval: str = "5min", outputsize: str = "compact"):
    data = await client.time_series_intraday(symbol, interval=interval, outputsize=outputsize)
    _raise_if_av_error(data)
    return data

@router.get("/fx/daily")
async def fx_daily(from_symbol: str, to_symbol: str, outputsize: str = "compact"):
    data = await client.fx_daily(from_symbol, to_symbol, outputsize=outputsize)
    _raise_if_av_error(data)
    return summarize_fx_daily(data)

@router.get("/crypto/daily")
async def crypto_daily(symbol: str, market: str = "USD"):
    data = await client.crypto_daily(symbol, market=market)
    _raise_if_av_error(data)
    return summarize_crypto_daily(data)


@router.get("/universe-snapshot")
async def universe_snapshot(state: str = Query("active", pattern="^(active|delisted)$")):
    rows = await client.listing_status(state=state)
    if not rows:
        raise HTTPException(status_code=502, detail="Empty universe snapshot response from Alpha Vantage.")
    return {
        "state": state,
        "count": len(rows),
        "updated_every_minutes": 30,
        "tickers": rows,
    }
