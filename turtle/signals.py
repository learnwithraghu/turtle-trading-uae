"""
Turtle Trading signal generator.

System 1: 20-day channel breakout (default)
System 2: 55-day channel breakout

Signal definition:
  - BREAKOUT : last_close >= N-day high
  - NEAR     : 0 < pct_to_high <= 2.0 %

GTT order parameters:
  - Trigger     : period_high × 1.001  (0.1 % above high to confirm breakout)
  - ATR         : 14-day simple average of (high - low)
  - Stop Loss   : gtt_trigger - 2 × ATR
  - Target      : back-solved so net P&L after round-trip commissions = profit_target_aed
  - Shares      : floor(trade_size_aed / gtt_trigger)
  - R/R ratio   : (target - trigger) / (trigger - stop_loss)
"""

from __future__ import annotations

import math
from typing import TypedDict

from turtle.commission import solve_target_price, calc_net_pnl


class SignalResult(TypedDict):
    # Price data
    last_close:   float
    period_high:  float
    period_low:   float
    atr:          float
    # Signal
    is_breakout:  bool
    is_near:      bool
    pct_to_high:  float   # % distance from last_close to period_high (positive = below high)
    signal:       str     # "BREAKOUT" | "NEAR" | "NONE"
    # GTT order
    gtt_trigger:  float
    target_price: float
    stop_loss:    float
    shares:       int
    net_pnl:      float
    rr:           float   # reward / risk ratio


def get_signal(
    history:            list[dict],
    days:               int   = 20,
    trade_size_aed:     float = 5000.0,
    profit_target_aed:  float = 150.0,
    exchange:           str   = "DFM",
) -> SignalResult | None:
    """
    Compute Turtle Trading signal for a single stock.

    Parameters
    ----------
    history : list[dict]
        OHLCV rows sorted oldest→newest. Each row must have keys:
        ``date``, ``high``, ``low``, ``close``.
    days : int
        Channel period (20 for System 1, 55 for System 2).
    trade_size_aed : float
        Capital allocated per trade.
    profit_target_aed : float
        Desired net profit after round-trip commissions.
    exchange : str
        ``"DFM"`` or ``"ADX"`` — determines commission schedule.

    Returns
    -------
    SignalResult or None
        ``None`` if there is insufficient history (< ``days`` rows).
    """
    if len(history) < days:
        return None

    window      = history[-days:]
    last_row    = history[-1]
    last_close  = float(last_row["close"])

    period_high = max(float(r["high"]) for r in window)
    period_low  = min(float(r["low"])  for r in window)

    # ── ATR (14-day simple average true range) ────────────────────────────────
    atr_window  = history[-14:]
    atr         = _calc_atr(atr_window)

    # ── Breakout / Near ───────────────────────────────────────────────────────
    pct_to_high = ((period_high - last_close) / period_high) * 100.0  # + = below high
    is_breakout = last_close >= period_high
    is_near     = not is_breakout and 0.0 < pct_to_high <= 2.0

    if is_breakout:
        signal = "BREAKOUT"
    elif is_near:
        signal = "NEAR"
    else:
        signal = "NONE"

    # ── GTT parameters ────────────────────────────────────────────────────────
    gtt_trigger = round(period_high * 1.001, 4)
    stop_loss   = round(gtt_trigger - 2 * atr, 4)

    shares = math.floor(trade_size_aed / gtt_trigger) if gtt_trigger > 0 else 0

    if shares < 1:
        target_price = gtt_trigger  # degenerate case; will be filtered out
        net_pnl_val  = 0.0
        rr           = 0.0
    else:
        target_price = round(
            solve_target_price(gtt_trigger, shares, exchange, profit_target_aed), 4
        )
        net_pnl_val  = round(calc_net_pnl(gtt_trigger, target_price, shares, exchange), 2)
        risk         = gtt_trigger - stop_loss
        reward       = target_price - gtt_trigger
        rr           = round(reward / risk, 2) if risk > 0 else 0.0

    return SignalResult(
        last_close   = last_close,
        period_high  = period_high,
        period_low   = period_low,
        atr          = round(atr, 4),
        is_breakout  = is_breakout,
        is_near      = is_near,
        pct_to_high  = round(pct_to_high, 3),
        signal       = signal,
        gtt_trigger  = gtt_trigger,
        target_price = target_price,
        stop_loss    = stop_loss,
        shares       = shares,
        net_pnl      = net_pnl_val,
        rr           = rr,
    )


def score_signal(result: dict) -> float:
    """
    Compute a numeric score for ranking / curation.

    Scoring:
      +200   if BREAKOUT
      +up to 80  if NEAR  (closer = higher; max at pct_to_high ≈ 0)
      +up to 40  for volume (log-scaled, capped at AED 10 M+)
      +20    if R/R > 1.5
      -100   if volume below min_volume_aed (caller sets this flag)
    """
    score = 0.0
    if result.get("signal") == "BREAKOUT":
        score += 200
    elif result.get("signal") == "NEAR":
        pct = result.get("pct_to_high", 2.0)
        score += (2.0 - pct) * 40   # 0→80, 2→0

    value_aed = result.get("value_aed", 0)
    if value_aed > 0:
        import math as _math
        # log10(500_000) ≈ 5.7, log10(10_000_000) ≈ 7.0 → scale to 0–40
        capped = min(value_aed, 10_000_000)
        score += (_math.log10(max(capped, 1)) / 7.0) * 40

    if result.get("rr", 0) > 1.5:
        score += 20

    if result.get("below_min_volume", False):
        score -= 100

    return score


# ── Internal helpers ──────────────────────────────────────────────────────────

def _calc_atr(window: list[dict]) -> float:
    """Simple ATR: average of (high - low) over the window."""
    if not window:
        return 0.0
    true_ranges = [float(r["high"]) - float(r["low"]) for r in window]
    return sum(true_ranges) / len(true_ranges)
