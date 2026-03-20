"""
ENBD Securities commission calculator.

Schedule source: emiratesnbdsecurities.com/en/schedule-of-fees

DFM (per side):
  Broker fee:       0.125% + VAT 5%  → 0.13125%
  Market fee:       0.050% + VAT 5%  → 0.05250%
  SCA fee:          0.050%            → 0.05000%
  CDS fee:          0.050% + VAT 5%  → 0.05250%
  Transaction fee:  AED 10.50 flat
  ─────────────────────────────────────────
  Total rate:       0.28625% + AED 10.50

ADX (per side):
  Broker fee:       0.125% + VAT 5%  → 0.13125%
  Other fees:       0.025% + VAT 5%  → 0.02625%
  ─────────────────────────────────────────
  Total rate:       0.15750%
"""

from __future__ import annotations

VAT = 0.05

# ── DFM ──────────────────────────────────────────────────────────────────────
DFM_BROKER_RATE  = 0.00125 * (1 + VAT)   # 0.13125 %
DFM_MARKET_RATE  = 0.00050 * (1 + VAT)   # 0.05250 %
DFM_SCA_RATE     = 0.00050               # 0.05000 % (no VAT)
DFM_CDS_RATE     = 0.00050 * (1 + VAT)   # 0.05250 %
DFM_FLAT_FEE     = 10.50                 # AED flat per transaction

DFM_TOTAL_RATE   = DFM_BROKER_RATE + DFM_MARKET_RATE + DFM_SCA_RATE + DFM_CDS_RATE
# 0.28625 %

# ── ADX ──────────────────────────────────────────────────────────────────────
ADX_BROKER_RATE  = 0.00125 * (1 + VAT)   # 0.13125 %
ADX_OTHER_RATE   = 0.00025 * (1 + VAT)   # 0.02625 %

ADX_TOTAL_RATE   = ADX_BROKER_RATE + ADX_OTHER_RATE
# 0.15750 %


def calc_commission(trade_aed: float, exchange: str) -> float:
    """
    Return the one-side commission in AED for a trade of ``trade_aed``.

    Parameters
    ----------
    trade_aed : float
        Gross trade value in AED (price × shares).
    exchange : str
        ``"DFM"`` or ``"ADX"`` (case-insensitive).

    Returns
    -------
    float
        Commission in AED.

    Raises
    ------
    ValueError
        If ``exchange`` is not ``"DFM"`` or ``"ADX"``.
    """
    exchange = exchange.upper()
    if exchange == "DFM":
        return trade_aed * DFM_TOTAL_RATE + DFM_FLAT_FEE
    elif exchange == "ADX":
        return trade_aed * ADX_TOTAL_RATE
    else:
        raise ValueError(f"Unknown exchange: {exchange!r}. Expected 'DFM' or 'ADX'.")


def calc_round_trip_commission(trade_aed: float, exchange: str) -> float:
    """Return total commission for both buy AND sell sides of a trade."""
    return calc_commission(trade_aed, exchange) * 2


def solve_target_price(
    entry_price: float,
    shares: int,
    exchange: str,
    net_profit_target_aed: float,
) -> float:
    """
    Back-solve the exit price such that net P&L after round-trip commissions
    equals ``net_profit_target_aed``.

    Derivation
    ----------
    Let:
      B  = entry trade value  = entry_price × shares
      T  = target trade value = target_price × shares
      r  = commission rate
      f  = flat fee per side (DFM only, else 0)

    Buy commission  = B × r + f
    Sell commission = T × r + f

    Net P&L = (T - B) - (B×r + f) - (T×r + f)
            = T(1 - r) - B(1 + r) - 2f
            = net_profit_target_aed

    Solving for T:
      T = (net_profit_target_aed + B×(1 + r) + 2f) / (1 - r)

    target_price = T / shares
    """
    exchange = exchange.upper()
    if exchange == "DFM":
        r = DFM_TOTAL_RATE
        f = DFM_FLAT_FEE
    elif exchange == "ADX":
        r = ADX_TOTAL_RATE
        f = 0.0
    else:
        raise ValueError(f"Unknown exchange: {exchange!r}")

    buy_value = entry_price * shares
    target_value = (net_profit_target_aed + buy_value * (1 + r) + 2 * f) / (1 - r)
    return target_value / shares


def calc_net_pnl(
    entry_price: float,
    exit_price: float,
    shares: int,
    exchange: str,
) -> float:
    """
    Calculate net P&L after round-trip commissions.

    P&L = gross gain - buy commission - sell commission
    """
    buy_value  = entry_price * shares
    sell_value = exit_price  * shares
    buy_comm   = calc_commission(buy_value,  exchange)
    sell_comm  = calc_commission(sell_value, exchange)
    return (sell_value - buy_value) - buy_comm - sell_comm
