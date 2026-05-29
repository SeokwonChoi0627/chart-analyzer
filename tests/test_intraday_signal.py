"""15분봉 단기 신호 엔진 테스트."""
import pandas as pd
import numpy as np
import pytest
from core.signals import generate_intraday_signal, _classify_intraday
from core.indicators import compute_all


def _make_15m(n: int = 60, trend: str = "up") -> pd.DataFrame:
    """n개 15분봉 OHLCV DataFrame 생성."""
    np.random.seed(42)
    idx = pd.date_range("2026-05-29 09:00", periods=n, freq="15min")
    if trend == "up":
        close = 100 + np.cumsum(np.random.uniform(0.1, 0.5, n))
    elif trend == "down":
        close = 200 - np.cumsum(np.random.uniform(0.1, 0.5, n))
    else:
        close = 150 + np.random.uniform(-0.2, 0.2, n)

    return pd.DataFrame(
        {
            "open":   close - np.random.uniform(0.1, 0.3, n),
            "high":   close + np.random.uniform(0.1, 0.5, n),
            "low":    close - np.random.uniform(0.1, 0.5, n),
            "close":  close,
            "volume": np.random.randint(1000, 5000, n).astype(float),
        },
        index=idx,
    )


# ── _classify_intraday ────────────────────────────────────────────────────────

def test_classify_intraday_thresholds():
    assert _classify_intraday(2.5)  == "단기 매수 타이밍"
    assert _classify_intraday(2.0)  == "단기 매수 타이밍"
    assert _classify_intraday(1.0)  == "단기 상승 기조"
    assert _classify_intraday(0.0)  == "단기 중립"
    assert _classify_intraday(-0.4) == "단기 중립"
    assert _classify_intraday(-1.0) == "단기 하락 기조"
    assert _classify_intraday(-2.0) == "단기 매도 타이밍"
    assert _classify_intraday(-3.0) == "단기 매도 타이밍"


# ── generate_intraday_signal ──────────────────────────────────────────────────

def test_intraday_signal_empty_returns_data_insufficient():
    result = generate_intraday_signal(pd.DataFrame())
    assert result["verdict"] == "데이터 부족"
    assert result["score"] == 0.0


def test_intraday_signal_too_short_returns_data_insufficient():
    df = _make_15m(n=10)
    result = generate_intraday_signal(compute_all(df))
    assert result["verdict"] == "데이터 부족"


def test_intraday_signal_oversold_rsi_gives_positive():
    """급락 후 RSI 과매도 → 양수 점수."""
    n = 80
    idx = pd.date_range("2026-05-29 09:00", periods=n, freq="15min")
    # 60봉 급락 → RSI 30 이하 유도, 이후 20봉 횡보
    close = np.concatenate([np.linspace(200, 50, 60), np.linspace(50, 51, 20)])
    df = pd.DataFrame(
        {"open": close - 0.1, "high": close + 0.2,
         "low": close - 0.2, "close": close,
         "volume": np.ones(n) * 1000.0},
        index=idx,
    )
    result = generate_intraday_signal(compute_all(df))
    assert result["score"] > 0, f"과매도 RSI에서 양수 기대, 실제={result['score']}"


def test_intraday_signal_overbought_rsi_gives_negative():
    """급등 후 RSI 과매수 → 음수 점수."""
    n = 80
    idx = pd.date_range("2026-05-29 09:00", periods=n, freq="15min")
    # 60봉 급등 → RSI 70 이상 유도, 이후 20봉 횡보
    close = np.concatenate([np.linspace(50, 200, 60), np.linspace(200, 199, 20)])
    df = pd.DataFrame(
        {"open": close - 0.1, "high": close + 0.2,
         "low": close - 0.2, "close": close,
         "volume": np.ones(n) * 1000.0},
        index=idx,
    )
    result = generate_intraday_signal(compute_all(df))
    assert result["score"] < 0, f"과매수 RSI에서 음수 기대, 실제={result['score']}"


def test_intraday_signal_has_required_keys():
    df = _make_15m(n=60)
    result = generate_intraday_signal(compute_all(df))
    for key in ("score", "verdict", "reasons", "last_price", "last_time"):
        assert key in result, f"'{key}' 키 누락"


def test_intraday_signal_reasons_have_required_keys():
    df = _make_15m(n=80, trend="up")
    result = generate_intraday_signal(compute_all(df))
    for r in result["reasons"]:
        for key in ("indicator", "signal", "score", "note"):
            assert key in r, f"reason 항목에 '{key}' 키 누락"
