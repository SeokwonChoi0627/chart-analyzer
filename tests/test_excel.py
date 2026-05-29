import pandas as pd
import pytest
from core.data.excel import parse_ohlcv_frame


def test_korean_columns_mapped():
    raw = pd.DataFrame({
        "일자": ["2024-01-01", "2024-01-02"],
        "시가": [100, 102],
        "고가": [105, 106],
        "저가": [99, 101],
        "종가": [103, 104],
        "거래량": [1000, 1200],
    })
    out = parse_ohlcv_frame(raw)
    assert list(out.columns) == ["open", "high", "low", "close", "volume"]
    assert isinstance(out.index, pd.DatetimeIndex)
    assert out["close"].iloc[0] == 103
    assert out.index[0] < out.index[1]


def test_english_columns_mapped():
    raw = pd.DataFrame({
        "Date": ["2024-01-02", "2024-01-01"],
        "Open": [102, 100], "High": [106, 105],
        "Low": [101, 99], "Close": [104, 103],
        "Volume": [1200, 1000],
    })
    out = parse_ohlcv_frame(raw)
    assert out.index[0] < out.index[1]
    assert out["close"].iloc[0] == 103


def test_missing_required_column_raises():
    raw = pd.DataFrame({"일자": ["2024-01-01"], "종가": [100]})
    with pytest.raises(ValueError) as exc:
        parse_ohlcv_frame(raw)
    assert "필수" in str(exc.value) or "컬럼" in str(exc.value)
