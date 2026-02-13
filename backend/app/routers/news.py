from fastapi import APIRouter, HTTPException, Query
from app.services.alphavantage import client
from app.services.analytics import aggregate_news_sentiment

router = APIRouter(prefix="/news", tags=["news"])

def _raise_if_av_error(data):
    if isinstance(data, dict) and ("Note" in data or "Information" in data or "Error Message" in data):
        raise HTTPException(status_code=502, detail=data)

@router.get("/sentiment")
async def sentiment(
    tickers: str | None = None,
    topics: str | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
    sort: str = "LATEST",
    limit: int = Query(50, ge=1, le=1000)
):
    data = await client.news_sentiment(
        tickers=tickers,
        topics=topics,
        time_from=time_from,
        time_to=time_to,
        sort=sort,
        limit=limit
    )
    _raise_if_av_error(data)
    return aggregate_news_sentiment(data)
