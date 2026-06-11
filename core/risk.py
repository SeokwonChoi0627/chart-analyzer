"""ATR 기반 리스크 관리: 손절가 · 목표가 · 리스크/리워드 비율."""

# 손절: 진입가 − STOP_ATR_MULT × ATR / 목표: 진입가 + TARGET_ATR_MULT × ATR
STOP_ATR_MULT = 2.0
TARGET1_ATR_MULT = 3.0
TARGET2_ATR_MULT = 4.0


def compute_risk_levels(entry: float, atr: float) -> dict | None:
    """진입가와 ATR로 손절가/목표가/RR 비율 계산.

    Returns:
        {stop, target1, target2, rr1, rr2, stop_pct, target1_pct, target2_pct}
        entry 또는 atr이 유효하지 않으면 None.
    """
    if entry is None or atr is None or entry <= 0 or atr <= 0:
        return None

    risk = STOP_ATR_MULT * atr
    stop = entry - risk
    if stop <= 0:
        # 변동성이 진입가 대비 과도(2×ATR ≥ 진입가) — 리스크 산출 무의미
        return None
    target1 = entry + TARGET1_ATR_MULT * atr
    target2 = entry + TARGET2_ATR_MULT * atr

    return {
        "stop":        round(stop, 4),
        "target1":     round(target1, 4),
        "target2":     round(target2, 4),
        "rr1":         round(TARGET1_ATR_MULT / STOP_ATR_MULT, 2),
        "rr2":         round(TARGET2_ATR_MULT / STOP_ATR_MULT, 2),
        "stop_pct":    round((stop - entry) / entry * 100, 2),
        "target1_pct": round((target1 - entry) / entry * 100, 2),
        "target2_pct": round((target2 - entry) / entry * 100, 2),
    }
