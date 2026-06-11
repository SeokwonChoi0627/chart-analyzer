"""ATR 기반 리스크 관리: 손절가 · 목표가 · 트레일링 스탑 · 보유 포지션 평가."""
import pandas as pd

# 손절: 진입가 − STOP_ATR_MULT × ATR / 목표: 진입가 + TARGET_ATR_MULT × ATR
STOP_ATR_MULT = 2.0
TARGET1_ATR_MULT = 3.0
TARGET2_ATR_MULT = 4.0

# 트레일링 스탑 (샹들리에 엑시트): 최근 고점 − TRAIL_ATR_MULT × ATR
TRAIL_ATR_MULT = 3.0
TRAIL_LOOKBACK = 22  # 약 1개월 거래일


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


def trailing_stop_from_df(df: pd.DataFrame, lookback: int = TRAIL_LOOKBACK,
                          atr_mult: float = TRAIL_ATR_MULT) -> float | None:
    """샹들리에 엑시트: 최근 lookback봉 최고가 − atr_mult × 현재 ATR.

    주가가 오르면 청산선도 따라 올라가 이익을 보호한다 (위로만 이동).
    """
    if df is None or df.empty or "high" not in df.columns or "atr" not in df.columns:
        return None
    atr = df["atr"].iloc[-1]
    if pd.isna(atr) or float(atr) <= 0:
        return None
    highs = df["high"].dropna().tail(lookback)
    if highs.empty:
        return None
    return round(float(highs.max()) - atr_mult * float(atr), 4)


def evaluate_position(entry: float, current: float, atr: float,
                      trailing_stop: float | None = None) -> dict | None:
    """보유 포지션 평가: 매수가 고정 기준 손절/목표 + 트레일링 스탑 결합.

    권장 청산선(effective_stop)은 고정 손절과 트레일링 스탑 중 높은 쪽 —
    주가가 오를수록 청산선이 따라 올라가 수익을 지킨다.

    Returns: compute_risk_levels 결과 + {pnl_pct, trailing_stop,
             effective_stop, status}. 입력 무효 시 None.
    status: "손절 이탈" | "이익보호 청산" | "1차 목표 도달" | "2차 목표 도달" | "보유 유지"
    """
    if current is None or current <= 0:
        return None
    base = compute_risk_levels(entry, atr)
    if base is None:
        return None

    effective_stop = base["stop"]
    if trailing_stop is not None and trailing_stop > effective_stop:
        effective_stop = trailing_stop

    if current <= effective_stop:
        # 수익 구간에서 트레일링 이탈은 손절이 아니라 이익 보호 청산
        status = "이익보호 청산" if current >= entry else "손절 이탈"
    elif current >= base["target2"]:
        status = "2차 목표 도달"
    elif current >= base["target1"]:
        status = "1차 목표 도달"
    else:
        status = "보유 유지"

    return {
        **base,
        "pnl_pct":        round((current - entry) / entry * 100, 2),
        "trailing_stop":  trailing_stop,
        "effective_stop": round(effective_stop, 4),
        "status":         status,
    }
