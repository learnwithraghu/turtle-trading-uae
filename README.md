# Turtle Trading UAE Dashboard

Flask app that scans selected DFM and ADX stocks for Turtle System 1 breakout candidates and generates fee-adjusted GTT levels for a 5,000 AED position size.

## What It Does

- Pulls end-of-day OHLC data from Yahoo Finance (`yfinance`) for the UAE stock universe.
- Computes:
  - 20-day high / low
  - ATR14
  - Signal score: `(close - 20d_low) / (20d_high - 20d_low) * 100`
- Labels candidates as:
  - `BREAKOUT` (close at/above 20-day high)
  - `PRE-BREAKOUT` (score >= 80)
  - `WATCH`
- Renders top 5 candidates each for DFM and ADX.
- Builds GTT-ready position levels with Emirates NBD fee assumptions.

## Fee + Target Assumptions

- Investment per trade: `5000 AED`
- Fee per side: `0.1575%` (`0.15% + 5% VAT`)
- Net profit target: `3.14%`
- Target price multiplier: `1.034654`

## Project Structure

```
turtle-trading-uae/
├── app.py
├── calculator.py
├── stocks.py
├── templates/
│   └── index.html
├── requirements.txt
├── Dockerfile
└── cloudbuild.yaml
```

## Run Locally

### Option A (Recommended): uv

1. Install uv (if not already installed).

macOS / Linux:

```bash
command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { irm https://astral.sh/uv/install.ps1 | iex }
```

2. Create and activate the virtual environment.

macOS / Linux:

```bash
uv python install 3.11
uv venv --python 3.11 .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
uv python install 3.11
uv venv --python 3.11 .venv
.venv\Scripts\Activate.ps1
```

3. Install dependencies and run the app.

```bash
uv pip install -r requirements.txt
python app.py
```

### Option B: Standard Python venv

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## API

- `GET /` - dashboard page
- `GET /api/signals` - returns:
	- `meta` with strategy and fee constants
	- `data.dfm` and `data.adx` arrays with signal + GTT fields

## Deploy to Cloud Run

Configured through `cloudbuild.yaml`:

- Build container image
- Push to Artifact Registry
- Deploy to Cloud Run service `turtle-trading-uae` in `asia-south1`

Build submit:

```bash
gcloud builds submit --project data-engineer-423808
```