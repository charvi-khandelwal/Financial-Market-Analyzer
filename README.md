# Financial Market Analyzer (Alpha Vantage)

A simple full-stack app:
- **Backend:** FastAPI (Python) – stocks/FX/crypto + news sentiment + JSON/PDF reports
- **Frontend:** Next.js + Tailwind – glassy dashboard UI with a chart + sentiment bar

## Configure
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Put your Alpha Vantage key in `backend/.env`:
```bash
ALPHAVANTAGE_API_KEY=YOUR_KEY
```

## Run (Docker)
```bash
docker compose up --build
```

Open:
- Frontend: http://localhost:3000
- Backend docs: http://localhost:8000/docs

## Endpoints
- `GET /market/quote?symbol=AAPL`
- `GET /market/stocks/daily?symbol=AAPL`
- `GET /market/fx/daily?from_symbol=EUR&to_symbol=USD`
- `GET /market/crypto/daily?symbol=BTC&market=USD`
- `GET /news/sentiment?tickers=AAPL&limit=50`
- `GET /report/asset?kind=stock&symbol=AAPL&as_pdf=true`

## Disclaimer
This tool summarizes data and sentiment and is not investment advice.
