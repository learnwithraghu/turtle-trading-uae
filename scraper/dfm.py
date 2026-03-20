"""
DFM historical price scraper.

URL: https://www.dfm.ae/the-exchange/statistics-reports/historical-data/company-prices

The page is a Nuxt.js SPA. Data loads after JS executes, so we use Playwright
to drive a real Chromium browser.

Steps per ticker:
  1. Navigate to the historical-data page.
  2. Select the company from the dropdown.
  3. Set the date range to the last 90 days.
  4. Click Search.
  5. Wait for the price table to populate.
  6. Extract OHLCV rows.
  7. Append new rows to the local JSON cache.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import date, timedelta
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

log = logging.getLogger(__name__)

DFM_URL = "https://www.dfm.ae/the-exchange/statistics-reports/historical-data/company-prices"


async def scrape_dfm(config: object) -> dict[str, list[dict]]:
    """
    Scrape DFM historical prices for all listed companies.

    Returns
    -------
    dict
        ``{ticker: [OHLCV rows]}`` where each row is:
        ``{"date", "open", "high", "low", "close", "volume", "value_aed"}``
    """
    history_path = Path(config.history_path)
    history_path.mkdir(parents=True, exist_ok=True)

    results: dict[str, list[dict]] = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=config.headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = await context.new_page()

        try:
            log.info("Navigating to DFM historical data page…")
            await page.goto(DFM_URL, timeout=config.timeout_ms, wait_until="networkidle")

            # ── Discover all company names/tickers from the dropdown ──────────
            company_selector = "select[name*='company'], select[id*='company'], .company-select select"
            try:
                await page.wait_for_selector(company_selector, timeout=config.timeout_ms)
            except PWTimeout:
                # Fallback: try a broader dropdown scan
                company_selector = "select"
                await page.wait_for_selector(company_selector, timeout=config.timeout_ms)

            options = await page.query_selector_all(f"{company_selector} option")
            companies: list[tuple[str, str]] = []  # (value, label)
            for opt in options:
                val   = await opt.get_attribute("value") or ""
                label = (await opt.inner_text()).strip()
                if val and label and label.lower() not in ("select", "all", "-- select --", ""):
                    companies.append((val, label))

            log.info("DFM: found %d companies", len(companies))

            today     = date.today()
            date_from = (today - timedelta(days=90)).strftime("%d/%m/%Y")
            date_to   = today.strftime("%d/%m/%Y")

            for ticker_val, ticker_name in companies:
                ticker = _clean_ticker(ticker_val, ticker_name)
                cache_file = history_path / f"DFM_{ticker}.json"
                cached = _load_cache(cache_file)

                try:
                    rows = await _scrape_one_company(
                        page, company_selector, ticker_val,
                        date_from, date_to, config.timeout_ms,
                    )
                    if rows:
                        merged = _merge_rows(cached, rows)
                        _save_cache(cache_file, merged)
                        results[f"DFM_{ticker}"] = merged
                        log.info("DFM %s: %d rows (total cached)", ticker, len(merged))
                    elif cached:
                        results[f"DFM_{ticker}"] = cached
                        log.warning("DFM %s: no new rows; using %d cached rows", ticker, len(cached))
                    else:
                        log.warning("DFM %s: no data at all, skipping", ticker)

                except PWTimeout:
                    log.error("DFM %s: timeout, skipping", ticker)
                    if cached:
                        results[f"DFM_{ticker}"] = cached
                except Exception as exc:  # noqa: BLE001
                    log.error("DFM %s: %s", ticker, exc)
                    if cached:
                        results[f"DFM_{ticker}"] = cached

                # Polite delay between requests
                await asyncio.sleep(random.uniform(0.5, 1.5))

        finally:
            await browser.close()

    return results


async def _scrape_one_company(
    page,
    company_selector: str,
    ticker_val: str,
    date_from: str,
    date_to: str,
    timeout_ms: int,
) -> list[dict]:
    """Select a company, set date range, click Search, extract table rows."""

    # Select company
    await page.select_option(company_selector, value=ticker_val)
    await asyncio.sleep(0.3)

    # Set date range — try common input patterns
    for date_from_sel in ["input[name*='from']", "input[placeholder*='From']", "#dateFrom", ".date-from input"]:
        try:
            await page.fill(date_from_sel, date_from, timeout=3000)
            break
        except Exception:  # noqa: BLE001
            continue

    for date_to_sel in ["input[name*='to']", "input[placeholder*='To']", "#dateTo", ".date-to input"]:
        try:
            await page.fill(date_to_sel, date_to, timeout=3000)
            break
        except Exception:  # noqa: BLE001
            continue

    # Click Search button
    for search_sel in ["button[type='submit']", "button:has-text('Search')", "input[type='submit']", ".search-btn"]:
        try:
            await page.click(search_sel, timeout=5000)
            break
        except Exception:  # noqa: BLE001
            continue

    # Wait for table to populate
    await page.wait_for_selector("table tbody tr", timeout=timeout_ms)
    await asyncio.sleep(0.5)  # let JS finish populating

    return await _extract_table(page)


async def _extract_table(page) -> list[dict]:
    """Parse visible price table → list of OHLCV dicts."""
    rows = []
    tr_elements = await page.query_selector_all("table tbody tr")
    for tr in tr_elements:
        cells = await tr.query_selector_all("td")
        if len(cells) < 7:
            continue
        texts = [((await c.inner_text()).strip().replace(",", "")) for c in cells]
        try:
            row = {
                "date":      texts[0],
                "open":      float(texts[1]),
                "high":      float(texts[2]),
                "low":       float(texts[3]),
                "close":     float(texts[4]),
                "volume":    float(texts[5]),
                "value_aed": float(texts[6]),
            }
            rows.append(row)
        except (ValueError, IndexError):
            continue
    return rows


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_ticker(val: str, label: str) -> str:
    """Derive a short ticker string from the dropdown value/label."""
    # Use value if it looks like a ticker (short, alphanumeric)
    if val and len(val) <= 8 and val.isalnum():
        return val.upper()
    # Fall back to first word of the label
    return label.split()[0].upper().replace(".", "")


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
    """Merge, deduplicate by date, and sort oldest→newest."""
    by_date: dict[str, dict] = {r["date"]: r for r in existing}
    for r in new_rows:
        by_date[r["date"]] = r  # new rows overwrite stale cache
    return sorted(by_date.values(), key=lambda r: r["date"])
