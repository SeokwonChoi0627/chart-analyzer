import pandas as pd
import pytest

from core.screener import scan_symbols


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


def _fake_fetch(symbol):
    if symbol == "UP":
        return _make_df([100 + i for i in range(120)]), "테스트"
    if symbol == "DOWN":
        return _make_df([300 - i for i in range(120)]), "테스트"
    raise ValueError(f"'{symbol}' 데이터를 가져오지 못했습니다")


def test_scans_all_symbols():
    results = scan_symbols(["UP", "DOWN", "ERR"], fetch_fn=_fake_fetch)
    assert len(results) == 3


def test_sorted_by_score_desc_with_errors_last():
    results = scan_symbols(["ERR", "DOWN", "UP"], fetch_fn=_fake_fetch)
    assert results[0]["symbol"] == "UP"
    assert results[1]["symbol"] == "DOWN"
    assert results[2]["symbol"] == "ERR"


def test_success_row_fields():
    row = scan_symbols(["UP"], fetch_fn=_fake_fetch)[0]
    assert row["score"] > 0
    assert "매수" in row["verdict"]
    assert row["close"] > 0
    assert row["error"] is None
    assert row["regime"]


def test_error_row_fields():
    row = scan_symbols(["ERR"], fetch_fn=_fake_fetch)[0]
    assert row["score"] is None
    assert row["verdict"] == "조회 실패"
    assert row["error"]


def test_deduplicates_and_skips_blank():
    results = scan_symbols(["UP", "UP", "  ", ""], fetch_fn=_fake_fetch)
    assert len(results) == 1


def test_nan_last_close_becomes_error_row():
    def _nan_fetch(symbol):
        df = _make_df([100 + i for i in range(120)])
        df.iloc[-1, df.columns.get_loc("close")] = float("nan")
        return df, "테스트"

    row = scan_symbols(["NAN"], fetch_fn=_nan_fetch)[0]
    assert row["error"] is not None
    assert row["score"] is None
