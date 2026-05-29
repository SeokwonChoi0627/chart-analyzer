import pandas as pd
from datetime import date
from core.cache import OhlcvCache


def _df():
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    return pd.DataFrame({
        "open": [1, 2, 3], "high": [1, 2, 3], "low": [1, 2, 3],
        "close": [1, 2, 3], "volume": [10, 20, 30],
    }, index=idx)


def test_save_and_load_roundtrip(tmp_path):
    cache = OhlcvCache(str(tmp_path / "test.db"))
    cache.save("005930", _df())
    loaded = cache.load("005930", max_age_date=date.today())
    assert loaded is not None
    assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]
    assert len(loaded) == 3
    assert loaded["close"].iloc[-1] == 3


def test_load_missing_returns_none(tmp_path):
    cache = OhlcvCache(str(tmp_path / "test.db"))
    assert cache.load("999999", max_age_date=date.today()) is None


def test_stale_cache_returns_none(tmp_path):
    from datetime import timedelta
    cache = OhlcvCache(str(tmp_path / "test.db"))
    cache.save("005930", _df())
    future = date.today() + timedelta(days=1)
    assert cache.load("005930", max_age_date=future) is None
