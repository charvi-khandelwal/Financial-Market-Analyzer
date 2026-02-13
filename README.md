# Financial Market Analyzer (Alpha Vantage)

A simple full-stack app:
- **Backend:** FastAPI (Python) – stocks/FX/crypto + news sentiment + JSON/PDF reports
- **Frontend:** Next.js + Tailwind – glassy dashboard UI with a chart + sentiment bar

## Project Structure
```
├── backend/
│   ├── app/            # FastAPI application
│   ├── data/           # Runtime data (gitignored)
│   ├── ve/             # Python virtual environment (gitignored)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/            # Next.js app directory
│   ├── node_modules/   # Dependencies (gitignored)
│   ├── .next/          # Build output (gitignored)
│   └── Dockerfile
├── start.sh            # Unix startup script
├── start.cmd           # Windows startup script
└── docker-compose.yml
```

## Configure
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Put your Alpha Vantage key in `backend/.env`:
```bash
ALPHAVANTAGE_API_KEY=YOUR_KEY
```

## Run

### Option 1: Docker
```bash
docker compose up --build
```

### Option 2: Local Development

**Prerequisites:**
- Python 3.x with a virtual environment at `backend/ve/`
- Node.js with dependencies installed in `frontend/`

**Setup (first time):**
```bash
# Backend
cd backend
python -m venv ve
ve\Scripts\activate      # Windows
source ve/bin/activate   # Unix
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

**Start servers:**
```bash
# Windows
start.cmd

# Unix/macOS
./start.sh
```

This launches both backend (uvicorn) and frontend (Next.js dev server) concurrently.

Open:
- **Frontend:** http://localhost:3000
- **Backend docs:** http://localhost:8000/docs

## Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /market/quote?symbol=AAPL` | Real-time quote |
| `GET /market/stocks/daily?symbol=AAPL` | Daily stock data |
| `GET /market/fx/daily?from_symbol=EUR&to_symbol=USD` | Daily FX rates |
| `GET /market/crypto/daily?symbol=BTC&market=USD` | Daily crypto data |
| `GET /news/sentiment?tickers=AAPL&limit=50` | News sentiment |
| `GET /report/asset?kind=stock&symbol=AAPL&as_pdf=true` | JSON/PDF report |

## Disclaimer
This tool summarizes data and sentiment and is not investment advice.
