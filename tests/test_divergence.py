import pandas as pd

from core.signals import detect_divergence


def _make_df(closes, rsi):
    n = len(closes)
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "open": closes,
        "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes],
        "close": closes,
        "volume": [1000] * n,
        "rsi": rsi,
    }, index=idx)


def _bearish_df():
    """주가 고점은 높아지는데(110→115) RSI 고점은 낮아짐(70→62)."""
    closes = [100 + i for i in range(11)]              # 100..110 (피크 idx 10)
    closes += [110 - i for i in range(1, 11)]          # 109..100
    closes += [100 + 1.5 * i for i in range(1, 11)]    # 101.5..115 (피크 idx 30)
    closes += [115 - i for i in range(1, 6)]           # 114..110

    rsi = [50 + 2 * i for i in range(11)]              # 50..70
    rsi += [70 - 2 * i for i in range(1, 11)]          # 68..50
    rsi += [50 + 1.2 * i for i in range(1, 11)]        # 51.2..62
    rsi += [62 - 2 * i for i in range(1, 6)]           # 60..52
    return _make_df(closes, rsi)


def _bullish_df():
    """주가 저점은 낮아지는데(90→85) RSI 저점은 높아짐(30→38)."""
    closes = [100 - i for i in range(11)]              # 100..90 (저점 idx 10)
    closes += [90 + i for i in range(1, 11)]           # 91..100
    closes += [100 - 1.5 * i for i in range(1, 11)]    # 98.5..85 (저점 idx 30)
    closes += [85 + i for i in range(1, 6)]            # 86..90

    rsi = [50 - 2 * i for i in range(11)]              # 50..30
    rsi += [30 + 2 * i for i in range(1, 11)]          # 32..50
    rsi += [50 - 1.2 * i for i in range(1, 11)]        # 48.8..38
    rsi += [38 + 2 * i for i in range(1, 6)]           # 40..48
    return _make_df(closes, rsi)


def test_bearish_divergence_detected():
    frac, label, note = detect_divergence(_bearish_df())
    assert frac == -1.0
    assert "하락" in label


def test_bullish_divergence_detected():
    frac, label, note = detect_divergence(_bullish_df())
    assert frac == 1.0
    assert "상승" in label


def test_monotonic_trend_has_no_divergence():
    closes = [100 + i for i in range(40)]
    rsi = [50 + i * 0.5 for i in range(40)]
    frac, label, _ = detect_divergence(_make_df(closes, rsi))
    assert frac == 0.0


def test_insufficient_data_is_neutral():
    closes = [100, 101, 102]
    rsi = [50, 51, 52]
    frac, label, _ = detect_divergence(_make_df(closes, rsi))
    assert frac == 0.0


def test_missing_rsi_column_is_neutral():
    closes = [100 + i for i in range(40)]
    df = _make_df(closes, [50] * 40).drop(columns=["rsi"])
    frac, _, _ = detect_divergence(df)
    assert frac == 0.0
