import pandas as pd

from core.data.base import clean_ohlcv, detect_market


def test_korean_6digit_code():
    assert detect_market("005930") == "KR"


def test_korean_hangul_name():
    assert detect_market("삼성전자") == "KR"


def test_us_ticker_uppercase():
    assert detect_market("AAPL") == "US"


def test_us_ticker_lowercase_normalized():
    assert detect_market("aapl") == "US"


def test_strips_whitespace():
    assert detect_market("  005930  ") == "KR"


# ── clean_ohlcv: 미완성 봉(close NaN) 제거 ────────────────────────────────────

def _ohlcv(closes):
    n = len(closes)
    idx = pd.date_range("2026-06-01", periods=n, freq="D")
    return pd.DataFrame({
        "open": [100.0] * n, "high": [101.0] * n,
        "low": [99.0] * n, "close": closes,
        "volume": [1000] * n,
    }, index=idx)


def test_clean_drops_trailing_nan_close():
    """미국장 미마감 시 FDR이 close=NaN 미완성 봉을 반환하는 케이스."""
    df = _ohlcv([100.0, 101.0, float("nan")])
    cleaned = clean_ohlcv(df)
    assert len(cleaned) == 2
    assert not cleaned["close"].isna().any()


def test_clean_drops_middle_nan_close():
    df = _ohlcv([100.0, float("nan"), 102.0])
    assert len(clean_ohlcv(df)) == 2


def test_clean_keeps_valid_rows_unchanged():
    df = _ohlcv([100.0, 101.0, 102.0])
    cleaned = clean_ohlcv(df)
    assert len(cleaned) == 3
    assert len(df) == 3  # 원본 불변


def test_clean_handles_empty_df():
    assert clean_ohlcv(pd.DataFrame()).empty
