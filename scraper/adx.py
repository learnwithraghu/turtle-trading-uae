"""
ADX equities scraper.

URL: https://www.adx.ae/all-equities

ADX returns 403 to non-browser requests, so we use Playwright with a realistic
user-agent.

Strategy:
- Current session prices come from the all-equities table (scraped each run).
- Historical data is built incrementally: each run appends today's row to the
  per-ticker JSON cache.
- On the first run (empty cache), Yahoo Finance is used as a warmup source so
  that we have enough history to compute Turtle signals immediately.

Data flow:
  ADX page → today's OHLCV row
  + cache   → last N days of history
  = signal-ready history list
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import date
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

log = logging.getLogger(__name__)

ADX_EQUITIES_URL = "https://www.adx.ae/all-equities"


async def scrape_adx(config: object) -> dict[str, list[dict]]:
    """
    Scrape ADX equities page for current prices and build/update history cache.

    Returns
    -------
    dict
        ``{ticker: [OHLCV rows]}`` sorted oldest→newest.
    """
    history_path = Path(config.history_path)
    history_path.mkdir(parents=True, exist_ok=True)

    today_str = date.today().isoformat()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=config.headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        page = await context.new_page()

        today_rows: list[dict] = []
        try:
            log.info("Navigating to ADX all-equities page…")
            # Random delay to avoid bot detection
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.goto(ADX_EQUITIES_URL, timeout=config.timeout_ms, wait_until="networkidle")

            # Wait for the equities table
            try:
                await page.wait_for_selector("table tbody tr, .equities-table tr", timeout=config.timeout_ms)
            except PWTimeout:
                log.warning("ADX: equities table did not load; will use cached data")

            today_rows = await _extract_adx_table(page)
            log.info("ADX: scraped %d tickers from live page", len(today_rows))

        except PWTimeout:
            log.error("ADX: page load timed out; falling back to cache only")
        except Exception as exc:  # noqa: BLE001
            log.error("ADX: scrape error — %s", exc)
        finally:
            await browser.close()

    results: dict[str, list[dict]] = {}

    for row in today_rows:
        ticker = row["ticker"]
        cache_file = history_path / f"ADX_{ticker}.json"
        cached = _load_cache(cache_file)

        # Warmup from Yahoo Finance if cache is empty
        if not cached:
            cached = await _yf_warmup(ticker)
            if cached:
                log.info("ADX %s: Yahoo Finance warmup — %d rows", ticker, len(cached))

        # Build today's OHLCV row (ADX page shows last/close only; use it for all OHLC)
        today_ohlcv = {
            "date":      today_str,
            "open":      row.get("open",  row["close"]),
            "high":      row.get("high",  row["close"]),
            "low":       row.get("low",   row["close"]),
            "close":     row["close"],
            "volume":    row["volume"],
            "value_aed": row["value_aed"],
        }

        merged = _merge_rows(cached, [today_ohlcv])
        _save_cache(cache_file, merged)
        results[f"ADX_{ticker}"] = merged

    # For any ticker in the cache that wasn't on today's page, still load it
    for cache_file in history_path.glob("ADX_*.json"):
        key = cache_file.stem  # e.g. ADX_ADIB
        if key not in results:
            cached = _load_cache(cache_file)
            if cached:
                results[key] = cached

    return results


async def _extract_adx_table(page) -> list[dict]:
    """
    Parse the ADX all-equities table.

    Expected columns (may vary): Ticker | Name | Last | Change | Change% | Volume | Value
    We handle column index guessing since ADX restructures the page periodically.
    """
    rows = []
    tr_elements = await page.query_selector_all("table tbody tr, .equities-table tbody tr")

    for tr in tr_elements:
        cells = await tr.query_selector_all("td")
        if len(cells) < 5:
            continue
        texts = [(await c.inner_text()).strip().replace(",", "") for c in cells]

        # Best-effort column mapping
        ticker    = _first_short_upper(texts)
        close_val = _parse_float_safe(texts, index=2)
        volume    = _parse_float_safe(texts, index=5)
        value_aed = _parse_float_safe(texts, index=6)

        if ticker and close_val is not None and close_val > 0:
            rows.append({
                "ticker":    ticker,
                "close":     close_val,
                "volume":    volume or 0.0,
                "value_aed": value_aed or 0.0,
            })
    return rows


async def _yf_warmup(ticker: str) -> list[dict]:
    """
    Fetch 90 days of history from Yahoo Finance as a warmup source.
    ADX tickers on Yahoo typically use the suffix ``.AD`` (e.g. ``ADIB.AD``).
    """
    try:
        import yfinance as yf  # type: ignore[import]

        yf_symbol = f"{ticker}.AD"
        df = yf.download(yf_symbol, period="3mo", progress=False, auto_adjust=True)
        if df.empty:
            return []
        rows = []
        for idx, r in df.iterrows():
            rows.append({
                "date":      str(idx.date()),
                "open":      float(r["Open"]),
                "high":      float(r["High"]),
                "low":       float(r["Low"]),
                "close":     float(r["Close"]),
                "volume":    float(r["Volume"]),
                "value_aed": float(r["Close"]) * float(r["Volume"]),
            })
        return rows
    except Exception as exc:  # noqa: BLE001
        log.warning("ADX %s: Yahoo Finance warmup failed — %s", ticker, exc)
        return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _first_short_upper(texts: list[str]) -> str | None:
    """Return the first cell value that looks like a stock ticker."""
    for t in texts[:3]:
        cleaned = t.strip().upper().replace(".", "")
        if 2 <= len(cleaned) <= 8 and cleaned.isalnum():
            return cleaned
    return None


def _parse_float_safe(texts: list[str], index: int) -> float | None:
    try:
        return float(texts[index].replace("%", "").replace("+", "").replace("-", ""))
    except (ValueError, IndexError):
        return None


def _load_cache(path: Path) -> list[dict]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save_cache(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, indent=2))


def _merge_rows(existing: list[dict], new_rows: list[dict]) -> list[dict]:
    """Merge, deduplicate by date, sort oldest→newest."""
    by_date: dict[str, dict] = {r["date"]: r for r in existing}
    for r in new_rows:
        by_date[r["date"]] = r
    return sorted(by_date.values(), key=lambda r: r["date"])
