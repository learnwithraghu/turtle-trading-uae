from __future__ import annotations

from datetime import datetime, timezone
import os

from flask import Flask, jsonify, render_template

from calculator import (
    BUY_VALUE_AFTER_BUY_FEE,
    EFFECTIVE_RATE_PER_SIDE,
    INVESTMENT_AED,
    NET_TARGET_RETURN,
    TARGET_PRICE_MULTIPLIER,
    compute_position,
)
from stocks import build_all_signals

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/signals")
def api_signals():
    try:
        signals = build_all_signals(top_n=5)
    except Exception as exc:
        return (
            jsonify(
                {
                    "meta": {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "strategy": "Turtle System 1 (20-day breakout)",
                    },
                    "error": f"Failed to build signals: {exc}",
                    "data": {"dfm": [], "adx": []},
                }
            ),
            500,
        )

    payload = {}
    for exchange in ["dfm", "adx"]:
        enriched = []
        for item in signals.get(exchange, []):
            gtt = compute_position(entry_price=item["high_20"], atr14=item["atr14"])
            enriched.append(
                {
                    **item,
                    "gtt": gtt,
                }
            )
        payload[exchange] = enriched

    return jsonify(
        {
            "meta": {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "investment_aed": INVESTMENT_AED,
                "net_target_return_pct": round(NET_TARGET_RETURN * 100, 2),
                "effective_fee_per_side_pct": round(EFFECTIVE_RATE_PER_SIDE * 100, 4),
                "buy_value_after_fee": round(BUY_VALUE_AFTER_BUY_FEE, 2),
                "target_price_multiplier": round(TARGET_PRICE_MULTIPLIER, 6),
                "strategy": "Turtle System 1 (20-day breakout)",
            },
            "data": payload,
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
