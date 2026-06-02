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
    """RSI 과매도 탈출(30선 상향 돌파) → 양수 점수.

    개선된 로직: RSI가 30 이하에서 30 초과로 돌파하는 시점에 강한 매수 신호.
    20봉 횡보 후 RSI가 이미 30~50 사이로 회복되면 과매도 구간이 아니므로 점수 0이 정상.
    따라서 급락 직후(RSI가 막 30선을 상향 돌파하는 시점)를 테스트한다.
    """
    n = 40
    idx = pd.date_range("2026-05-29 09:00", periods=n, freq="15min")
    # 30봉 급락(RSI 30 이하) → 마지막 10봉 소폭 반등(RSI 30선 돌파 유도)
    close = np.concatenate([np.linspace(200, 50, 30), np.linspace(50, 65, 10)])
    df = pd.DataFrame(
        {"open": close - 0.1, "high": close + 0.2,
         "low": close - 0.2, "close": close,
         "volume": np.ones(n) * 1000.0},
        index=idx,
    )
    result = generate_intraday_signal(compute_all(df))
    # RSI 30선 돌파 또는 과매도 잔류 → 양수 점수 기대
    assert result["score"] > 0, f"과매도 탈출 구간에서 양수 기대, 실제={result['score']}"


def test_intraday_signal_overbought_rsi_gives_negative():
    """RSI 과매수 해소(70선 하향 돌파) → 음수 점수.

    개선된 로직: RSI가 70 이상에서 70 미만으로 돌파하는 시점에 강한 매도 신호.
    급등 직후(RSI가 막 70선을 하향 돌파하는 시점)를 테스트한다.
    """
    n = 40
    idx = pd.date_range("2026-05-29 09:00", periods=n, freq="15min")
    # 30봉 급등(RSI 70 이상) → 마지막 10봉 소폭 하락(RSI 70선 하향 돌파 유도)
    close = np.concatenate([np.linspace(50, 200, 30), np.linspace(200, 185, 10)])
    df = pd.DataFrame(
        {"open": close - 0.1, "high": close + 0.2,
         "low": close - 0.2, "close": close,
         "volume": np.ones(n) * 1000.0},
        index=idx,
    )
    result = generate_intraday_signal(compute_all(df))
    # RSI 70선 하향 돌파 또는 과매수 잔류 → 음수 점수 기대
    assert result["score"] < 0, f"과매수 해소 구간에서 음수 기대, 실제={result['score']}"


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
