import pandas as pd

from core.risk import compute_risk_levels, evaluate_position, trailing_stop_from_df


def test_basic_levels_from_atr():
    r = compute_risk_levels(entry=10000, atr=500)
    assert r["stop"] == 9000        # entry − 2×ATR
    assert r["target1"] == 11500    # entry + 3×ATR
    assert r["target2"] == 12000    # entry + 4×ATR


def test_risk_reward_ratios():
    r = compute_risk_levels(entry=10000, atr=500)
    assert r["rr1"] == 1.5          # (3×ATR) / (2×ATR)
    assert r["rr2"] == 2.0          # (4×ATR) / (2×ATR)


def test_percentages():
    r = compute_risk_levels(entry=10000, atr=500)
    assert r["stop_pct"] == -10.0
    assert r["target1_pct"] == 15.0
    assert r["target2_pct"] == 20.0


def test_invalid_entry_returns_none():
    assert compute_risk_levels(entry=0, atr=500) is None
    assert compute_risk_levels(entry=-100, atr=500) is None


def test_invalid_atr_returns_none():
    assert compute_risk_levels(entry=10000, atr=0) is None
    assert compute_risk_levels(entry=10000, atr=-5) is None


def test_stop_below_zero_returns_none():
    """변동성이 진입가의 절반을 넘으면(2×ATR ≥ entry) 손절가가 음수 — 무효."""
    assert compute_risk_levels(entry=100, atr=60) is None


# ── trailing_stop_from_df (샹들리에 엑시트) ───────────────────────────────────

def _df_with_atr(highs, atr):
    n = len(highs)
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "open": highs, "high": highs,
        "low": [h - 2 for h in highs], "close": [h - 1 for h in highs],
        "volume": [1000] * n, "atr": [atr] * n,
    }, index=idx)


def test_trailing_stop_is_recent_high_minus_3atr():
    df = _df_with_atr([100, 110, 120, 115, 112], atr=5)
    # 최근 고점 120 − 3×5 = 105
    assert trailing_stop_from_df(df, lookback=22) == 105.0


def test_trailing_stop_respects_lookback_window():
    highs = [200] + [100] * 30  # 고점 200은 lookback 밖
    df = _df_with_atr(highs, atr=5)
    assert trailing_stop_from_df(df, lookback=22) == 85.0  # 100 − 15


def test_trailing_stop_invalid_inputs():
    assert trailing_stop_from_df(pd.DataFrame()) is None
    df = _df_with_atr([100, 110], atr=5).drop(columns=["atr"])
    assert trailing_stop_from_df(df) is None


# ── evaluate_position (보유 포지션 평가) ──────────────────────────────────────

def test_position_pnl_and_fixed_levels():
    pos = evaluate_position(entry=10000, current=10500, atr=500)
    assert pos["pnl_pct"] == 5.0
    assert pos["stop"] == 9000
    assert pos["target1"] == 11500
    assert pos["effective_stop"] == 9000  # 트레일링 없으면 고정 손절


def test_effective_stop_takes_higher_of_fixed_and_trailing():
    pos = evaluate_position(entry=10000, current=12000, atr=500, trailing_stop=10800)
    assert pos["effective_stop"] == 10800  # 트레일링이 더 높음 → 이익 보호
    pos2 = evaluate_position(entry=10000, current=10100, atr=500, trailing_stop=8500)
    assert pos2["effective_stop"] == 9000  # 고정 손절이 더 높음


def test_position_status_stop_hit():
    pos = evaluate_position(entry=10000, current=8900, atr=500)
    assert pos["status"] == "손절 이탈"


def test_position_status_targets():
    assert evaluate_position(10000, 11600, 500)["status"] == "1차 목표 도달"
    assert evaluate_position(10000, 12100, 500)["status"] == "2차 목표 도달"
    assert evaluate_position(10000, 10500, 500)["status"] == "보유 유지"


def test_position_trailing_stop_hit_in_profit_is_protective_exit():
    """수익 구간에서 트레일링 스탑 이탈 — 손절이 아니라 이익보호 청산."""
    pos = evaluate_position(entry=10000, current=10700, atr=500, trailing_stop=10800)
    assert pos["status"] == "이익보호 청산"


def test_position_invalid_inputs():
    assert evaluate_position(entry=0, current=100, atr=5) is None
    assert evaluate_position(entry=100, current=0, atr=5) is None
