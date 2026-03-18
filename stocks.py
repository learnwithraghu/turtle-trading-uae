from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
import logging
from typing import Dict, List

import numpy as np
import pandas as pd
import yfinance as yf

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

DFM_TICKERS = {
    "EMAAR.DU": "Emaar Properties",
    "DEWA.DU": "Dubai Electricity & Water Authority",
    "DIB.DU": "Dubai Islamic Bank",
    "SALIK.DU": "Salik",
    "TECOM.DU": "TECOM Group",
    "DFM.DU": "Dubai Financial Market",
    "AIRARABIA.DU": "Air Arabia",
    "AMANAT.DU": "Amanat Holdings",
    "CBD.DU": "Commercial Bank of Dubai",
    "SPINNEYS.DU": "Spinneys",
    "PARKIN.DU": "Parkin",
    "ALANSARI.DU": "Al Ansari Financial Services",
    "EMAARDEV.DU": "Emaar Development",
    "TABREED.DU": "Tabreed",
    "DU.DU": "Emirates Integrated Telecom",
    "GFH.DU": "GFH Financial Group",
    "EIIB.DU": "Emirates Islamic Bank",
    "AJMANBANK.DU": "Ajman Bank",
}

ADX_TICKERS = {
    "FAB.AD": "First Abu Dhabi Bank",
    "ADCB.AD": "Abu Dhabi Commercial Bank",
    "ADIB.AD": "Abu Dhabi Islamic Bank",
    "IHC.AD": "International Holding Company",
    "ALDAR.AD": "Aldar Properties",
    "TAQA.AD": "TAQA",
    "NMDC.AD": "NMDC Group",
    "ADNOCGAS.AD": "ADNOC Gas",
    "ADNOCDIST.AD": "ADNOC Distribution",
    "ADPORTS.AD": "AD Ports Group",
    "ALPHADHABI.AD": "Alpha Dhabi Holding",
    "AGTHIA.AD": "Agthia",
    "JULPHAR.AD": "Julphar",
    "RAKBANK.AD": "RAKBank",
    "SIB.AD": "Sharjah Islamic Bank",
    "MODON.AD": "Modon Holding",
    "PUREHEALTH.AD": "PureHealth",
    "FERTIGLOBE.AD": "Fertiglobe",
}


@dataclass
class SignalRow:
    symbol: str
    name: str
    close: float
    high_20: float
    low_20: float
    atr14: float
    score: float
    signal_label: str


def _atr14(df: pd.DataFrame) -> float:
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    close = df["Close"].astype(float)

    prev_close = close.shift(1)
    tr_components = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    )
    tr = tr_components.max(axis=1)
    atr = tr.rolling(window=14, min_periods=14).mean()
    return float(atr.iloc[-1]) if not atr.empty and pd.notna(atr.iloc[-1]) else np.nan


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        # yfinance may return either (Price, Ticker) or (Ticker, Price).
        col_level_0 = raw.columns.get_level_values(0)
        col_level_1 = raw.columns.get_level_values(1)

        if ticker in col_level_0:
            sub = raw.xs(ticker, level=0, axis=1)
        elif ticker in col_level_1:
            sub = raw.xs(ticker, level=1, axis=1)
        else:
            return pd.DataFrame()
    else:
        sub = raw.copy()

    required_cols = ["High", "Low", "Close"]
    for col in required_cols:
        if col not in sub.columns:
            return pd.DataFrame()

    return sub.dropna(subset=required_cols)


def _compute_signal_for_ticker(ticker: str, name: str, raw: pd.DataFrame) -> SignalRow | None:
    df = _extract_ticker_frame(raw, ticker)
    if len(df) < 25:
        return None

    close = float(df["Close"].iloc[-1])
    high_20 = float(df["Close"].tail(20).max())
    low_20 = float(df["Close"].tail(20).min())
    atr14 = _atr14(df)

    if not np.isfinite(close) or not np.isfinite(high_20) or not np.isfinite(low_20):
        return None

    spread = max(1e-9, high_20 - low_20)
    score = ((close - low_20) / spread) * 100.0

    signal_label = "BREAKOUT" if close >= high_20 else "PRE-BREAKOUT" if score >= 80 else "WATCH"

    return SignalRow(
        symbol=ticker,
        name=name,
        close=round(close, 4),
        high_20=round(high_20, 4),
        low_20=round(low_20, 4),
        atr14=round(float(atr14), 4) if np.isfinite(atr14) else 0.0,
        score=round(score, 2),
        signal_label=signal_label,
    )


def fetch_exchange_signals(ticker_map: Dict[str, str], top_n: int = 5) -> List[dict]:
    rows: List[SignalRow] = []
    tickers = list(ticker_map.keys())

    def _download() -> pd.DataFrame:
        return yf.download(
            tickers=tickers,
            period="3mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            group_by="column",
            timeout=12,
        )

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            raw = executor.submit(_download).result(timeout=40)
    except FuturesTimeoutError:
        return []
    except Exception:
        return []

    if raw is None or raw.empty:
        return []

    for ticker, name in ticker_map.items():
        try:
            signal = _compute_signal_for_ticker(ticker, name, raw)
            if signal is not None:
                rows.append(signal)
        except Exception:
            # Skip broken or stale ticker payloads and continue.
            continue

    rows.sort(key=lambda x: x.score, reverse=True)
    return [r.__dict__ for r in rows[:top_n]]


def build_all_signals(top_n: int = 5) -> dict:
    return {
        "dfm": fetch_exchange_signals(DFM_TICKERS, top_n=top_n),
        "adx": fetch_exchange_signals(ADX_TICKERS, top_n=top_n),
    }
