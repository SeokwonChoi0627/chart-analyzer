import math

import pandas as pd

from core.indicators import compute_all
from core.regime import detect_regime


def _make_df(closes):
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000] * n,
    }, index=idx)


def _trend_df(n=120):
    return _make_df([100 + i for i in range(n)])


def _range_df(n=120):
    return _make_df([100 + 5 * math.sin(i * 2 * math.pi / 10) for i in range(n)])


def test_compute_all_adds_adx_column():
    df = compute_all(_trend_df())
    assert "adx" in df.columns
    assert pd.notna(df["adx"].iloc[-1])


def test_strong_trend_detected():
    df = compute_all(_trend_df())
    result = detect_regime(df)
    assert result["regime"] == "추세장"
    assert result["adx"] >= 25


def test_range_market_detected():
    df = compute_all(_range_df())
    result = detect_regime(df)
    assert result["regime"] == "횡보장"
    assert result["adx"] < 20


def test_insufficient_data_returns_unknown():
    df = _trend_df(n=5)  # ADX 계산 불가
    enriched = compute_all(df)
    result = detect_regime(enriched)
    assert result["regime"] == "판별 불가"
    assert result["adx"] is None


def test_missing_adx_column_returns_unknown():
    df = _trend_df()  # compute_all 미적용 → adx 컬럼 없음
    result = detect_regime(df)
    assert result["regime"] == "판별 불가"
