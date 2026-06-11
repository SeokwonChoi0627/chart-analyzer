import pandas as pd

from core.backtest import run_backtest
from core.indicators import compute_all


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


def _uptrend_df(n=190):
    return _make_df([100 + i * 0.5 for i in range(n)])


def test_result_structure():
    enriched = compute_all(_uptrend_df())
    result = run_backtest(enriched, horizons=(5, 20))
    assert set(result.keys()) == {"horizons", "total_signals", "evaluated_bars"}
    assert set(result["horizons"].keys()) == {5, 20}


def test_bucket_has_required_stats():
    enriched = compute_all(_uptrend_df())
    result = run_backtest(enriched)
    for h, buckets in result["horizons"].items():
        for verdict, stats in buckets.items():
            assert set(stats.keys()) == {"count", "win_rate", "avg_return"}
            assert stats["count"] >= 1


def test_uptrend_buy_signals_always_win():
    """단조 상승 데이터에서는 모든 매수 신호의 forward return이 양수 → 승률 100%."""
    enriched = compute_all(_uptrend_df())
    result = run_backtest(enriched)
    assert result["total_signals"] > 0
    buy_buckets = [
        stats
        for buckets in result["horizons"].values()
        for verdict, stats in buckets.items()
        if "매수" in verdict
    ]
    assert buy_buckets, "상승 추세에서 매수 신호가 하나도 없음"
    for stats in buy_buckets:
        assert stats["win_rate"] == 100.0
        assert stats["avg_return"] > 0


def test_insufficient_data_returns_empty():
    enriched = compute_all(_uptrend_df(n=50))
    result = run_backtest(enriched)
    assert result["total_signals"] == 0
    assert all(not b for b in result["horizons"].values())


def test_empty_df_returns_empty():
    result = run_backtest(pd.DataFrame())
    assert result["total_signals"] == 0
