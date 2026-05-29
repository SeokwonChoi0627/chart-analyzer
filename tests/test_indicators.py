import pandas as pd
import numpy as np
from core.indicators import add_sma, add_rsi


def _make_df(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({
        "open": closes, "high": closes, "low": closes,
        "close": closes, "volume": [1000] * len(closes),
    }, index=idx)


def test_add_sma_creates_columns():
    df = _make_df(list(range(1, 11)))
    out = add_sma(df, windows=(5, 20, 60))
    assert "sma5" in out.columns
    assert "sma20" in out.columns
    assert "sma60" in out.columns


def test_sma5_value():
    df = _make_df([10, 20, 30, 40, 50])
    out = add_sma(df, windows=(5,))
    assert out["sma5"].iloc[-1] == 30.0


def test_sma_does_not_mutate_input():
    df = _make_df([1, 2, 3, 4, 5])
    add_sma(df, windows=(5,))
    assert "sma5" not in df.columns


def test_add_rsi_column_and_range():
    closes = list(range(1, 30))
    df = _make_df(closes)
    out = add_rsi(df, period=14)
    assert "rsi" in out.columns
    last = out["rsi"].iloc[-1]
    assert 0 <= last <= 100
    assert last > 70


def test_rsi_all_down_is_low():
    closes = list(range(30, 1, -1))
    df = _make_df(closes)
    out = add_rsi(df, period=14)
    assert out["rsi"].iloc[-1] < 30
