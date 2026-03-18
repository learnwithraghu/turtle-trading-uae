from __future__ import annotations

import math

INVESTMENT_AED = 5000.0
NET_TARGET_RETURN = 0.0314
COMMISSION_RATE = 0.0015
VAT_RATE = 0.05

EFFECTIVE_RATE_PER_SIDE = COMMISSION_RATE * (1 + VAT_RATE)  # 0.1575%
TARGET_PRICE_MULTIPLIER = (
    (1 + NET_TARGET_RETURN) * (1 + EFFECTIVE_RATE_PER_SIDE) / (1 - EFFECTIVE_RATE_PER_SIDE)
)
BUY_VALUE_AFTER_BUY_FEE = INVESTMENT_AED / (1 + EFFECTIVE_RATE_PER_SIDE)


def round2(value: float) -> float:
    return round(float(value), 2)


def compute_position(entry_price: float, atr14: float) -> dict:
    if entry_price <= 0:
        return {
            "shares": 0,
            "buy_trigger": 0.0,
            "buy_limit": 0.0,
            "target_sell": 0.0,
            "stop_loss": 0.0,
            "invested_in_stock": 0.0,
            "buy_fee": 0.0,
            "total_cash_out": 0.0,
            "sell_fee_at_target": 0.0,
            "gross_sale_at_target": 0.0,
            "net_sale_after_sell_fee": 0.0,
            "net_profit": 0.0,
            "net_profit_pct": 0.0,
            "stop_loss_gross_sale": 0.0,
            "stop_loss_sell_fee": 0.0,
            "stop_loss_net_sale": 0.0,
            "risk_if_stop_hit": 0.0,
            "risk_if_stop_hit_pct": 0.0,
        }

    shares = max(0, math.floor(BUY_VALUE_AFTER_BUY_FEE / entry_price))
    invested_in_stock = shares * entry_price
    buy_fee = invested_in_stock * EFFECTIVE_RATE_PER_SIDE

    target_sell = entry_price * TARGET_PRICE_MULTIPLIER
    gross_sale = shares * target_sell
    sell_fee = gross_sale * EFFECTIVE_RATE_PER_SIDE
    net_sale = gross_sale - sell_fee

    total_cash_out = invested_in_stock + buy_fee
    net_profit = net_sale - total_cash_out
    net_profit_pct = (net_profit / INVESTMENT_AED * 100) if INVESTMENT_AED else 0.0

    stop_loss = max(0.0, entry_price - 2 * max(0.0, atr14))
    stop_loss_gross_sale = shares * stop_loss
    stop_loss_sell_fee = stop_loss_gross_sale * EFFECTIVE_RATE_PER_SIDE
    stop_loss_net_sale = stop_loss_gross_sale - stop_loss_sell_fee
    risk_if_stop_hit = max(0.0, total_cash_out - stop_loss_net_sale)
    risk_if_stop_hit_pct = (risk_if_stop_hit / INVESTMENT_AED * 100) if INVESTMENT_AED else 0.0

    return {
        "shares": shares,
        "buy_trigger": round2(entry_price),
        "buy_limit": round2(entry_price),
        "target_sell": round2(target_sell),
        "stop_loss": round2(stop_loss),
        "invested_in_stock": round2(invested_in_stock),
        "buy_fee": round2(buy_fee),
        "total_cash_out": round2(total_cash_out),
        "sell_fee_at_target": round2(sell_fee),
        "gross_sale_at_target": round2(gross_sale),
        "net_sale_after_sell_fee": round2(net_sale),
        "net_profit": round2(net_profit),
        "net_profit_pct": round2(net_profit_pct),
        "stop_loss_gross_sale": round2(stop_loss_gross_sale),
        "stop_loss_sell_fee": round2(stop_loss_sell_fee),
        "stop_loss_net_sale": round2(stop_loss_net_sale),
        "risk_if_stop_hit": round2(risk_if_stop_hit),
        "risk_if_stop_hit_pct": round2(risk_if_stop_hit_pct),
        "target_multiplier": TARGET_PRICE_MULTIPLIER,
    }
