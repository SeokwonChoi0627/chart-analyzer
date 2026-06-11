from core.risk import compute_risk_levels


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
