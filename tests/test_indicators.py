import pandas as pd
import numpy as np
from core.indicators import add_sma, add_rsi, add_macd, add_bollinger, add_volume_ratio, compute_all


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


def test_add_macd_columns():
    closes = list(range(1, 60))
    df = _make_df(closes)
    out = add_macd(df, fast=12, slow=26, signal=9)
    assert "macd" in out.columns
    assert "macd_signal" in out.columns
    assert "macd_hist" in out.columns


def test_macd_hist_is_macd_minus_signal():
    closes = list(range(1, 60))
    df = _make_df(closes)
    out = add_macd(df)
    row = out.iloc[-1]
    assert abs(row["macd_hist"] - (row["macd"] - row["macd_signal"])) < 1e-9


def test_add_bollinger_columns_and_order():
    closes = [100, 102, 98, 101, 99, 103, 97, 100, 105, 95,
              100, 102, 98, 101, 99, 103, 97, 100, 105, 95]
    df = _make_df(closes)
    out = add_bollinger(df, window=20, num_std=2)
    assert "bb_mid" in out.columns
    assert "bb_upper" in out.columns
    assert "bb_lower" in out.columns
    row = out.iloc[-1]
    assert row["bb_lower"] < row["bb_mid"] < row["bb_upper"]


def test_add_volume_ratio():
    idx = pd.date_range("2024-01-01", periods=21, freq="D")
    vols = [1000] * 20 + [3000]
    df = pd.DataFrame({
        "open": [10]*21, "high": [10]*21, "low": [10]*21,
        "close": [10]*21, "volume": vols,
    }, index=idx)
    out = add_volume_ratio(df, window=20)
    assert "vol_ratio" in out.columns
    assert abs(out["vol_ratio"].iloc[-1] - 3.0) < 1e-9


def test_compute_all_adds_every_indicator():
    closes = list(range(1, 80))
    df = _make_df(closes)
    out = compute_all(df)
    for col in ["sma5", "sma20", "sma60", "rsi", "macd",
                "macd_signal", "macd_hist", "bb_upper", "bb_lower", "vol_ratio"]:
        assert col in out.columns
