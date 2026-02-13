from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

def _safe_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def summarize_quote(global_quote_json: Dict[str, Any]) -> Dict[str, Any]:
    q = global_quote_json.get("Global Quote", {}) if isinstance(global_quote_json, dict) else {}
    price = _safe_float(q.get("05. price"))
    change = _safe_float(q.get("09. change"))
    change_pct = q.get("10. change percent")
    return {
        "symbol": q.get("01. symbol"),
        "price": price,
        "change": change,
        "change_percent": change_pct,
        "volume": _safe_float(q.get("06. volume")),
        "latest_trading_day": q.get("07. latest trading day"),
    }

def summarize_timeseries_daily(ts_json: Dict[str, Any]) -> Dict[str, Any]:
    meta = ts_json.get("Meta Data", {}) if isinstance(ts_json, dict) else {}
    series = ts_json.get("Time Series (Daily)", {}) if isinstance(ts_json, dict) else {}
    points = []
    for date_str, ohlc in series.items():
        points.append((date_str, _safe_float(ohlc.get("4. close"))))
    points.sort(key=lambda x: x[0], reverse=True)
    closes = [p[1] for p in points if p[1] is not None][:30]
    mom = (closes[0] - closes[1]) / closes[1] if len(closes) >= 2 and closes[1] else None
    rets = []
    for i in range(len(closes)-1):
        if closes[i] and closes[i+1]:
            rets.append((closes[i] - closes[i+1]) / closes[i+1])
    vol = (sum((r - (sum(rets)/len(rets)))**2 for r in rets) / (len(rets)-1))**0.5 if len(rets) > 2 else None
    return {
        "symbol": meta.get("2. Symbol"),
        "last_refreshed": meta.get("3. Last Refreshed"),
        "points": [{"date": d, "close": c} for d, c in points[:120]],
        "momentum_1d": mom,
        "volatility_proxy": vol,
    }

def summarize_fx_daily(ts_json: Dict[str, Any]) -> Dict[str, Any]:
    meta = ts_json.get("Meta Data", {}) if isinstance(ts_json, dict) else {}
    series = ts_json.get("Time Series FX (Daily)", {}) if isinstance(ts_json, dict) else {}
    points = []
    for date_str, ohlc in series.items():
        points.append((date_str, _safe_float(ohlc.get("4. close"))))
    points.sort(key=lambda x: x[0], reverse=True)
    closes = [p[1] for p in points if p[1] is not None][:30]
    mom = (closes[0] - closes[1]) / closes[1] if len(closes) >= 2 and closes[1] else None
    return {
        "pair": f'{meta.get("2. From Symbol")}/{meta.get("3. To Symbol")}',
        "last_refreshed": meta.get("5. Last Refreshed"),
        "points": [{"date": d, "close": c} for d, c in points[:120]],
        "momentum_1d": mom,
    }

def summarize_crypto_daily(ts_json: Dict[str, Any]) -> Dict[str, Any]:
    meta = ts_json.get("Meta Data", {}) if isinstance(ts_json, dict) else {}
    series_key = next((k for k in ts_json.keys() if k.startswith("Time Series")), None)
    series = ts_json.get(series_key, {}) if series_key else {}
    points = []
    for date_str, row in series.items():
        close = row.get("4a. close (USD)") or row.get("4b. close (USD)") or row.get("4. close")
        points.append((date_str, _safe_float(close)))
    points.sort(key=lambda x: x[0], reverse=True)
    closes = [p[1] for p in points if p[1] is not None][:30]
    mom = (closes[0] - closes[1]) / closes[1] if len(closes) >= 2 and closes[1] else None
    return {
        "asset": meta.get("2. Digital Currency Code"),
        "market": meta.get("3. Market Code"),
        "last_refreshed": meta.get("6. Last Refreshed") or meta.get("5. Last Refreshed"),
        "points": [{"date": d, "close": c} for d, c in points[:120]],
        "momentum_1d": mom,
    }

def aggregate_news_sentiment(news_json: Dict[str, Any]) -> Dict[str, Any]:
    feed = news_json.get("feed", []) if isinstance(news_json, dict) else []
    sentiments = []
    by_ticker: Dict[str, List[float]] = {}
    items = []
    for item in feed:
        overall = _safe_float(item.get("overall_sentiment_score"))
        if overall is not None:
            sentiments.append(overall)
        ticker_sentiments = item.get("ticker_sentiment", []) or []
        for ts in ticker_sentiments:
            t = ts.get("ticker")
            s = _safe_float(ts.get("ticker_sentiment_score"))
            if t and s is not None:
                by_ticker.setdefault(t, []).append(s)
        items.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "time_published": item.get("time_published"),
            "source": item.get("source"),
            "overall_sentiment_score": overall,
            "overall_sentiment_label": item.get("overall_sentiment_label"),
        })
    avg = sum(sentiments)/len(sentiments) if sentiments else None
    per = {t: (sum(vals)/len(vals)) for t, vals in by_ticker.items() if vals}
    top = sorted(per.items(), key=lambda x: x[1], reverse=True)[:10]
    bottom = sorted(per.items(), key=lambda x: x[1])[:10]
    return {
        "overall_average_sentiment": avg,
        "ticker_average_sentiment": per,
        "top_positive": [{"ticker": t, "avg_sentiment": s} for t, s in top],
        "top_negative": [{"ticker": t, "avg_sentiment": s} for t, s in bottom],
        "items": items[:100],
    }

def build_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    headline_score = payload.get("news", {}).get("overall_average_sentiment")
    market_moves = payload.get("market", {})
    mood = "mixed"
    if isinstance(headline_score, (int, float)):
        if headline_score > 0.15:
            mood = "positive"
        elif headline_score < -0.15:
            mood = "negative"
        else:
            mood = "neutral"
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sentiment_mood": mood,
        "sentiment_score": headline_score,
        "market_snapshot": market_moves,
        "notes": [
            "This report summarizes publicly available data and sentiment. It is not investment advice.",
            "Consider validating signals with fundamentals, risk limits, and multiple data sources."
        ],
    }

def _bounded(x: Optional[float], lo: float = -1.0, hi: float = 1.0) -> float:
    if x is None:
        return 0.0
    return max(lo, min(hi, x))

def _label_from_score(score: float) -> str:
    if score >= 0.22:
        return "buy"
    if score <= -0.22:
        return "sell"
    return "hold"

def build_market_guidance(
    stock_rows: List[Dict[str, Any]],
    fx_rows: List[Dict[str, Any]],
    crypto_rows: List[Dict[str, Any]],
    news_summary: Dict[str, Any],
) -> Dict[str, Any]:
    news_avg = news_summary.get("overall_average_sentiment")
    public_mood = "neutral"
    if isinstance(news_avg, (int, float)):
        if news_avg > 0.15:
            public_mood = "bullish"
        elif news_avg < -0.15:
            public_mood = "bearish"

    merged: List[Dict[str, Any]] = []
    for row in stock_rows + fx_rows + crypto_rows:
        momentum = _bounded(row.get("momentum_1d"))
        volatility = _bounded(row.get("volatility_proxy"), lo=0.0, hi=1.0)
        sentiment = _bounded(row.get("sentiment"))
        score = (0.5 * momentum) + (0.35 * sentiment) - (0.25 * volatility)

        merged.append({
            **row,
            "signal_score": round(score, 4),
            "signal": _label_from_score(score),
            "risk_score": round(volatility, 4),
        })

    safest = sorted(merged, key=lambda r: (r.get("risk_score", 0.0), -r.get("signal_score", 0.0)))[:10]
    riskiest = sorted(merged, key=lambda r: (r.get("risk_score", 0.0), -abs(r.get("momentum_1d", 0.0))), reverse=True)[:10]
    buys = [r for r in sorted(merged, key=lambda x: x.get("signal_score", 0.0), reverse=True) if r.get("signal") == "buy"][:10]
    sells = [r for r in sorted(merged, key=lambda x: x.get("signal_score", 0.0)) if r.get("signal") == "sell"][:10]
    holds = [r for r in sorted(merged, key=lambda x: abs(x.get("signal_score", 0.0))) if r.get("signal") == "hold"][:10]

    expected_direction = "range-bound"
    if isinstance(news_avg, (int, float)):
        if news_avg > 0.2:
            expected_direction = "upside bias"
        elif news_avg < -0.2:
            expected_direction = "downside bias"

    return {
        "public_mood": public_mood,
        "expected_market_direction": expected_direction,
        "signals": merged,
        "safest_bets": safest,
        "riskiest_bets": riskiest,
        "buy_candidates": buys,
        "sell_candidates": sells,
        "hold_candidates": holds,
        "disclaimer": "Signal rankings are heuristic and educational, not financial advice.",
    }
