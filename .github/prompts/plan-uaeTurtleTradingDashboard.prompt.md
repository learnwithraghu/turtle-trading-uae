# Plan: UAE Turtle Trading Dashboard — Cloud Run App

## Context
- GCP Project: data-engineer-423808
- Region: asia-south1 (Mumbai)
- Data: yfinance (free, end-of-day)
- Strategy: Turtle System 1 — 20-day high breakout
- Stop-loss: 2× ATR14 below entry
- Exchange fees: Emirates NBD Securities — 0.1575% per trade (0.15% + 5% VAT)
- Investment per trade: 5,000 AED
- Net profit target: 3.14% on 5,000 AED = 157 AED

## Fee Math
- Commission: 0.001575 per side (buy + sell)
- Buy fee: 5000 / 1.001575 → 4,992.14 AED worth of stock (7.86 AED fee, paid from 5000)
- Target price multiplier: (1 + 0.0314) × (1 + 0.001575) / (1 - 0.001575) = 1.034654
- Target Price = Entry × 1.034654 (+3.4654% price move needed)

## Stock Universe
### DFM (.DU suffix on Yahoo Finance)
EMAAR.DU, DEWA.DU, DIB.DU, SALIK.DU, TECOM.DU, DFM.DU, AIRARABIA.DU,
AMANAT.DU, CBD.DU, SPINNEYS.DU, PARKIN.DU, ALANSARI.DU, EMAARDEV.DU,
TABREED.DU, DU.DU, GFH.DU, EIIB.DU, AJMANBANK.DU

### ADX (.AD suffix on Yahoo Finance)
FAB.AD, ADCB.AD, ADIB.AD, IHC.AD, ALDAR.AD, TAQA.AD, NMDC.AD,
ADNOCGAS.AD, ADNOCDIST.AD, ADPORTS.AD, ALPHADHABI.AD, AGTHIA.AD,
JULPHAR.AD, RAKBANK.AD, SIB.AD, MODON.AD, PUREHEALTH.AD, FERTIGLOBE.AD

## Signal Scoring
score = (close - 20d_low) / (20d_high - 20d_low) × 100
- >100 or ~100 = BREAKOUT (price at/above 20-day high)
- 80-99 = PRE-BREAKOUT (strong candidate)
- Lower = weaker

## GTT Order Display (per stock)
- GTT Buy Trigger: 20-day high (breakout level)
- Buy Limit Price: 20-day high (or slightly above = + 1 tick)
- Shares to buy: floor(4992.14 / trigger_price)  — so total ≈ 5000 AED
- Target Sell Price: buy_price × 1.034654
- Stop Loss: buy_price - (2 × ATR14)
- Expected fees: buy_commission + sell_commission
- Net profit if target hit: 157 AED (3.14%)

## File Structure
```
turtle-trading-uae/
├── app.py                   # Flask backend
├── stocks.py                # Stock universe + signal engine
├── calculator.py            # Fee/profit/GTT calculator
├── templates/index.html     # Single-page responsive UI
├── requirements.txt
├── Dockerfile
└── cloudbuild.yaml
```

## App Flow
1. User opens URL → Flask serves index.html
2. Page auto-calls /api/signals on load
3. Backend fetches 60-day OHLCV for all tickers via yfinance
4. Calculates signal scores, filters failed tickers, returns top 5 DFM + top 5 ADX
5. UI renders two sections (DFM | ADX) with card/table per stock
6. Refresh button re-calls /api/signals

## Key Backend Logic (app.py / stocks.py)
- yfinance.download(tickers, period="3mo", interval="1d")
- Calculate: 20d_high = max(close[-20:]), ATR14, signal_score
- Sort by score descending, take top 5 per exchange
- Return JSON with: symbol, name, close, 20d_high, ATR14, score, signal_label, gtt fields

## UI Design (index.html)
- Header with title + last-updated timestamp + "Refresh Data" button
- Loading spinner during fetch
- Two columns: DFM (left) | ADX (right)
- Each stock card shows:
  * Rank + Symbol + Name + Signal badge (BREAKOUT / PRE-BREAKOUT)
  * Current Price
  * GTT Buy Trigger price
  * Target Sell Price (with AED net profit shown)
  * Stop Loss price (with AED risk shown)
  * Shares to buy + Total outlay breakdown
  * Buy fee + Sell fee + Net after fees table
- Color: green for target, red for stop
- Mobile responsive (Tailwind CSS via CDN)

## Deployment (cloudbuild.yaml + Dockerfile)
- Docker: python:3.11-slim, gunicorn, port 8080
- cloudbuild.yaml: 3 steps: build → push → deploy to Cloud Run
- GCP: data-engineer-423808 | region: asia-south1
- Cloud Run: --allow-unauthenticated, --memory=512Mi, --timeout=120s

## Phases
### Phase 1: Backend
1. requirements.txt
2. stocks.py — ticker list + signal engine using yfinance
3. calculator.py — fee/GTT math
4. app.py — Flask routes: GET / and GET /api/signals

### Phase 2: Frontend
5. templates/index.html — full UI with Tailwind, fetch calls, cards/tables

### Phase 3: Deployment
6. Dockerfile
7. cloudbuild.yaml

## Verification
1. Local: python app.py → open localhost:5000 → verify signals load, math is correct
2. Check target price = entry × 1.034654
3. Check shares × entry ≈ 4992 AED (leaving 7.86 for buy fee ≈ total 5000)
4. Deploy: Cloud Build trigger should pick up cloudbuild.yaml, deploy to Cloud Run
5. Visit Cloud Run URL, verify it works publicly
