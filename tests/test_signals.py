import pandas as pd
from core.indicators import compute_all
from core.signals import generate_signal, classify


def _trend_up_df(n=120):
    closes = [100 + i for i in range(n)]
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "open": closes, "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes], "close": closes,
        "volume": [1000] * n,
    }, index=idx)


def _trend_down_df(n=120):
    closes = [300 - i for i in range(n)]
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "open": closes, "high": [c + 1 for c in closes],
        "low": [c - 1 for c in closes], "close": closes,
        "volume": [1000] * n,
    }, index=idx)


def test_classify_thresholds():
    assert classify(6.0) == "강력 매수"
    assert classify(3.0) == "매수 고려"
    assert classify(0.0) == "중립/관망"
    assert classify(-3.0) == "매도 고려"
    assert classify(-6.0) == "강력 매도"


def test_uptrend_gives_positive_score():
    df = compute_all(_trend_up_df())
    result = generate_signal(df)
    assert result["score"] > 0
    assert "매수" in result["verdict"]
    assert len(result["reasons"]) >= 1


def test_downtrend_gives_negative_score():
    df = compute_all(_trend_down_df())
    result = generate_signal(df)
    assert result["score"] < 0
    assert "매도" in result["verdict"]


def test_reasons_have_required_keys():
    df = compute_all(_trend_up_df())
    result = generate_signal(df)
    for r in result["reasons"]:
        assert set(r.keys()) == {"indicator", "signal", "score", "note"}
