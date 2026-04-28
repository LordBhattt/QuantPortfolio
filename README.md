# QuantPortfolio

Quant portfolio management with Black-Litterman optimization, Mean-Variance optimization, LSTM forecasting, HMM regime detection, CVaR, Monte Carlo simulation, and Fama-French analytics.

## Structure

```text
.
├── backend/     FastAPI + PostgreSQL + Redis
└── frontend/    React + Vite
```

## Quick Start

### Backend

```bash
cd backend
alembic upgrade head
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173
