"""
UAE Turtle Trader — main entry point.

Usage:
    python scan.py
    python scan.py --system 55
    python scan.py --trade 10000
    python scan.py --no-browser
    python scan.py --debug
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import toml

from scraper.dfm import scrape_dfm
from scraper.adx import scrape_adx
from turtle.signals import get_signal, score_signal
from turtle.commission import calc_round_trip_commission
from output.renderer import render_report, open_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Config dataclass ──────────────────────────────────────────────────────────

@dataclass
class Config:
    trade_size_aed:    float
    profit_target_aed: float
    turtle_system:     int
    min_volume_aed:    float
    max_picks:         int
    dfm_picks:         int
    adx_picks:         int
    headless:          bool
    timeout_ms:        int
    auto_open_report:  bool
    report_path:       str
    history_path:      str


def load_config(path: str = "config.toml", overrides: dict | None = None) -> Config:
    raw = toml.load(path)
    t = raw.get("trading", {})
    b = raw.get("browser", {})
    o = raw.get("output", {})

    cfg = Config(
        trade_size_aed    = t.get("trade_size_aed",    5000),
        profit_target_aed = t.get("profit_target_aed", 150),
        turtle_system     = t.get("turtle_system",     20),
        min_volume_aed    = t.get("min_volume_aed",    500_000),
        max_picks         = t.get("max_picks",         7),
        dfm_picks         = t.get("dfm_picks",         4),
        adx_picks         = t.get("adx_picks",         3),
        headless          = b.get("headless",          True),
        timeout_ms        = b.get("timeout_ms",        30_000),
        auto_open_report  = o.get("auto_open_report",  True),
        report_path       = o.get("report_path",       "output/report.html"),
        history_path      = o.get("history_path",      "data/history"),
    )

    if overrides:
        for k, v in overrides.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

    return cfg


# ── Curation logic ─────────────────────────────────────────────────────────────

def curate_picks(results: list[dict], config: Config) -> list[dict]:
    """
    Rank and select top N picks (DFM + ADX mix) according to scoring rules.
    """
    # Separate by exchange, filter out errors and stocks with no shares
    dfm_candidates = [r for r in results if r["exchange"] == "DFM"
                      and r.get("signal") != "ERROR" and r.get("shares", 0) >= 1]
    adx_candidates = [r for r in results if r["exchange"] == "ADX"
                      and r.get("signal") != "ERROR" and r.get("shares", 0) >= 1]

    dfm_sorted = sorted(dfm_candidates, key=lambda r: r["score"], reverse=True)
    adx_sorted = sorted(adx_candidates, key=lambda r: r["score"], reverse=True)

    picks: list[dict] = []
    picks.extend(dfm_sorted[: config.dfm_picks])
    picks.extend(adx_sorted[: config.adx_picks])

    # Fill remaining slots if either exchange didn't have enough
    already_tickers = {p["ticker"] for p in picks}
    remainder = sorted(
        [r for r in results
         if r["ticker"] not in already_tickers
         and r.get("signal") != "ERROR"
         and r.get("shares", 0) >= 1],
        key=lambda r: r["score"], reverse=True,
    )
    for r in remainder:
        if len(picks) >= config.max_picks:
            break
        picks.append(r)

    return picks[: config.max_picks]


# ── Terminal summary ──────────────────────────────────────────────────────────

def print_summary(picks: list[dict], config: Config) -> None:
    print("\n" + "═" * 62)
    print("  🐢  UAE Turtle Trader — Top Picks")
    print("═" * 62)
    for i, p in enumerate(picks, 1):
        sig = p.get("signal", "NONE")
        icon = "🚀" if sig == "BREAKOUT" else "⚡" if sig == "NEAR" else "·"
        print(
            f"  {i}. [{p['exchange']:3}] {p['ticker']:<12} {icon} {sig:<9} "
            f"close={p['last_close']:.4f}  trigger={p['gtt_trigger']:.4f}  "
            f"target={p['target_price']:.4f}  stop={p['stop_loss']:.4f}  "
            f"qty={p['shares']}  net≈AED{p['net_pnl']:.0f}  R/R={p['rr']:.2f}×"
        )
    print("═" * 62 + "\n")


# ── Main flow ─────────────────────────────────────────────────────────────────

async def main(config: Config) -> None:
    log.info("Starting scan — Turtle System %d-day", config.turtle_system)

    # 1. Scrape official sources
    log.info("Scraping DFM…")
    dfm_data = await scrape_dfm(config)

    log.info("Scraping ADX…")
    adx_data = await scrape_adx(config)

    all_data: dict[str, list[dict]] = {**dfm_data, **adx_data}
    log.info("Total tickers loaded: %d", len(all_data))

    # 2. Run Turtle logic on each stock
    results: list[dict] = []
    for full_ticker, history in all_data.items():
        exchange = "DFM" if full_ticker.startswith("DFM_") else "ADX"
        ticker   = full_ticker.split("_", 1)[1]

        signal = get_signal(
            history,
            days              = config.turtle_system,
            trade_size_aed    = config.trade_size_aed,
            profit_target_aed = config.profit_target_aed,
            exchange          = exchange,
        )

        if signal is None:
            log.debug("%s: insufficient history (%d rows), skipping", full_ticker, len(history))
            continue

        # Attach metadata
        last_row    = history[-1]
        value_aed   = float(last_row.get("value_aed", 0))
        below_vol   = value_aed < config.min_volume_aed

        entry: dict[str, Any] = {
            **signal,
            "ticker":          ticker,
            "exchange":        exchange,
            "name":            "",          # could enrich from a lookup file later
            "value_aed":       value_aed,
            "below_min_volume": below_vol,
        }
        entry["score"] = score_signal(entry)
        results.append(entry)

    log.info("Signals computed: %d stocks", len(results))

    # 3. Curate top picks
    picks = curate_picks(results, config)

    # 4. Terminal summary
    print_summary(picks, config)

    # 5. Render HTML report
    report_path = render_report(results, picks, config)
    log.info("Report written: %s", report_path)

    # 6. Auto-open in browser
    if config.auto_open_report:
        open_report(report_path)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="UAE Turtle Trader scanner")
    p.add_argument("--system",     type=int,   default=None,  help="Turtle system (20 or 55)")
    p.add_argument("--trade",      type=float, default=None,  help="Trade size in AED")
    p.add_argument("--no-browser", action="store_true",       help="Skip auto-open report")
    p.add_argument("--debug",      action="store_true",       help="Show browser window")
    p.add_argument("--config",     default="config.toml",     help="Config file path")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    overrides: dict = {}
    if args.system:
        overrides["turtle_system"] = args.system
    if args.trade:
        overrides["trade_size_aed"] = args.trade
    if args.no_browser:
        overrides["auto_open_report"] = False
    if args.debug:
        overrides["headless"] = False

    config = load_config(args.config, overrides)

    try:
        asyncio.run(main(config))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
