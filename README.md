# UAE Turtle Trader 🐢

Scrapes official DFM and ADX price pages, applies Turtle Trading breakout logic,
and outputs a curated list of 7 stocks with exact GTT order parameters (trigger,
target, stop) net of ENBD Securities commissions.

Run every evening after market close (Sun–Thu, after 3 PM UAE time).

---

## Running in GitHub Codespace (Docker only)

### 1. Open in Codespace

Click **Code → Codespaces → Create codespace on main**.
The devcontainer will build automatically and `docker compose build` will run.

### 2. Run the scanner

```bash
docker compose up
```

### 3. View the report

After the scan finishes, open `output/report.html` in the Codespace file explorer
and right-click → **Open with Live Server** (or download it to your local machine).

### Run with custom flags

```bash
# Turtle System 2 (55-day channel)
docker compose run --rm scanner python scan.py --system 55

# Override trade size
docker compose run --rm scanner python scan.py --trade 10000

# Show browser window (requires a display — not available in Codespace)
# python scan.py --debug
```

---

## Configuration

Edit `config.toml` before rebuilding. Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `trade_size_aed` | 5000 | Capital per trade (AED) |
| `profit_target_aed` | 150 | Net P&L target after commissions |
| `turtle_system` | 20 | 20 = System 1, 55 = System 2 |
| `min_volume_aed` | 500000 | Minimum daily traded value filter |
| `dfm_picks` | 4 | DFM stocks in the top-7 |
| `adx_picks` | 3 | ADX stocks in the top-7 |

After editing `config.toml`, no rebuild needed — it is bind-mounted read-only.

---

## Project Structure

```
.
├── .devcontainer/
│   └── devcontainer.json    ← Codespace config (Docker-in-Docker)
├── config.toml              ← user settings (edit this)
├── requirements.txt
├── Dockerfile               ← multi-stage; installs Playwright + Chromium
├── docker-compose.yml       ← mounts data/ and output/ as volumes
├── scan.py                  ← main entry point
├── scraper/
│   ├── dfm.py               ← DFM historical data (Playwright)
│   └── adx.py               ← ADX equities (Playwright + YF warmup)
├── turtle/
│   ├── commission.py        ← ENBD Securities fee calculator
│   └── signals.py           ← 20/55-day channel breakout logic
├── output/
│   ├── renderer.py          ← HTML report builder
│   └── report.html          ← generated each run (git-ignored)
└── data/history/            ← per-stock OHLCV cache, grows daily (git-ignored)
```

---

## Commission Schedule (ENBD Securities)

| Exchange | Rate (per side) | Flat fee |
|----------|----------------|----------|
| DFM      | 0.28625%       | AED 10.50 |
| ADX      | 0.15750%       | — |

On an AED 5,000 trade: DFM round-trip ≈ AED 38 · ADX round-trip ≈ AED 16

---

## Historical Data Strategy

| Run | DFM | ADX |
|-----|-----|-----|
| Day 1 | Playwright scrapes 90-day history from dfm.ae | ADX current prices + Yahoo Finance warmup |
| Day 2+ | Playwright scrapes incrementally, appends to cache | ADX page row appended to cache |
| After 20 days | 100% official for System 1 | 100% official for System 1 |
| After 55 days | 100% official for System 2 | 100% official for System 2 |

Cache files: `data/history/{EXCHANGE}_{TICKER}.json` — persisted via Docker volume.
