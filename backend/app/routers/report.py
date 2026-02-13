from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Query, Response

from app.services.alphavantage import client
from app.services.analytics import (
    summarize_quote,
    summarize_timeseries_daily,
    summarize_fx_daily,
    summarize_crypto_daily,
    aggregate_news_sentiment,
    build_report,
)
from app.config import settings
from app.services.pdf_report import render_pdf
from app.services.market_overview import market_overview_service

router = APIRouter(prefix="/report", tags=["report"])

# Alpha Vantage free tier often expects ~1 request/sec burst.
# Use a slightly >1s delay to reduce throttling.
AV_BURST_SLEEP_SECONDS = max(0.05, 60.0 / max(settings.MAX_CALLS_PER_MINUTE, 1))


def _raise_if_av_error(data):
    if isinstance(data, dict) and (
        "Note" in data or "Information" in data or "Error Message" in data
    ):
        raise HTTPException(status_code=502, detail=data)


@router.get("/asset")
async def asset_report(
    kind: str = Query(..., description="stock|fx|crypto"),
    symbol: str | None = None,
    from_symbol: str | None = None,
    to_symbol: str | None = None,
    market: str = "USD",
    tickers_for_news: str | None = None,
    topics: str | None = None,
    as_pdf: bool = False,
    include_news: bool = True,
    news_limit: int = Query(50, ge=1, le=1000),
):
    """
    Builds a combined market + sentiment report for:
    - stock: uses GLOBAL_QUOTE + TIME_SERIES_DAILY
    - fx:    uses FX_DAILY
    - crypto: uses DIGITAL_CURRENCY_DAILY

    Optionally fetches NEWS_SENTIMENT for sentiment aggregation.
    """
    market_summary = {}

    if kind == "stock":
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol required")

        # Call 1
        q = await client.global_quote(symbol)
        _raise_if_av_error(q)

        # Respect burst limit
        await asyncio.sleep(AV_BURST_SLEEP_SECONDS)

        # Call 2
        d = await client.time_series_daily(symbol, outputsize="compact")
        _raise_if_av_error(d)

        market_summary = {
            **summarize_quote(q),
            **{"daily": summarize_timeseries_daily(d)},
        }

        if not tickers_for_news:
            tickers_for_news = symbol.upper()

    elif kind == "fx":
        if not (from_symbol and to_symbol):
            raise HTTPException(
                status_code=400, detail="from_symbol and to_symbol required"
            )

        # Call 1
        d = await client.fx_daily(from_symbol, to_symbol, outputsize="compact")
        _raise_if_av_error(d)

        market_summary = summarize_fx_daily(d)

        if not tickers_for_news:
            tickers_for_news = f"FOREX:{to_symbol.upper()}"

    elif kind == "crypto":
        if not symbol:
            raise HTTPException(status_code=400, detail="symbol required")

        # Call 1
        d = await client.crypto_daily(symbol, market=market)
        _raise_if_av_error(d)

        market_summary = summarize_crypto_daily(d)

        if not tickers_for_news:
            tickers_for_news = f"CRYPTO:{symbol.upper()}"

    else:
        raise HTTPException(status_code=400, detail="kind must be stock|fx|crypto")

    # Optional news sentiment (often triggers throttling if called too soon after price endpoints)
    news_summary = {
        "overall_average_sentiment": None,
        "ticker_average_sentiment": {},
        "top_positive": [],
        "top_negative": [],
        "items": [],
    }

    if include_news and tickers_for_news:
        # Respect burst limit before calling news
        await asyncio.sleep(AV_BURST_SLEEP_SECONDS)

        news = await client.news_sentiment(
            tickers=tickers_for_news,
            topics=topics,
            limit=news_limit,
        )
        _raise_if_av_error(news)
        news_summary = aggregate_news_sentiment(news)

    report = build_report({"market": market_summary, "news": news_summary})

    if as_pdf:
        pdf_bytes = render_pdf(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline; filename=report.pdf"},
        )

    return {"report": report, "news": news_summary}

@router.get("/market-overview")
async def market_overview():
    latest = await market_overview_service.get_latest()
    return {"latest": latest}

@router.get("/market-overview/history")
async def market_overview_history(limit: int = Query(48, ge=1, le=500)):
    history = await market_overview_service.get_history(limit=limit)
    return {"history": history}

@router.post("/market-overview/refresh")
async def refresh_market_overview():
    return await market_overview_service.start_refresh(reason="manual")

@router.get("/market-overview/refresh-status")
async def refresh_market_overview_status():
    status = await market_overview_service.get_refresh_status()
    return {"status": status}
