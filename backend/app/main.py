from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.market import router as market_router
from app.routers.news import router as news_router
from app.routers.report import router as report_router
from app.services.market_overview import market_overview_service

@asynccontextmanager
async def lifespan(_: FastAPI):
    await market_overview_service.start()
    yield
    await market_overview_service.stop()

app = FastAPI(title="Market Analyzer API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(market_router)
app.include_router(news_router)
app.include_router(report_router)
