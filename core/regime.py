"""시장 국면(레짐) 판별: ADX 기반 추세장/횡보장 구분.

- ADX ≥ 25 : 추세장 → 추세 추종 지표(이평선·MACD)가 유리
- ADX < 20 : 횡보장 → 평균 회귀 지표(RSI·볼린저)가 유리
- 20 ≤ ADX < 25 : 전환 구간 (가중치 보정 없음)
"""
import pandas as pd

ADX_TREND_THRESHOLD = 25.0
ADX_RANGE_THRESHOLD = 20.0

# 신호 가중치 보정이 적용되는 국면 (전환 구간·판별 불가는 표준 가중치)
WEIGHTED_REGIMES = ("추세장", "횡보장")

_REGIME_DESC = {
    "추세장":   "추세가 뚜렷한 구간 — 이평선·MACD 신호 가중, 추세 추종 우선",
    "횡보장":   "방향성 없는 박스권 — RSI·볼린저 신호 가중, 박스 하단 매수/상단 매도 우선",
    "전환 구간": "추세 형성 초기 또는 소멸 구간 — 가중치 보정 없이 표준 판정",
    "판별 불가": "ADX 계산 불가 (데이터 부족)",
}


def detect_regime(df: pd.DataFrame) -> dict:
    """ADX로 시장 국면 판별.

    Returns: {"regime": str, "adx": float | None, "desc": str}
    """
    if df.empty or "adx" not in df.columns:
        return {"regime": "판별 불가", "adx": None, "desc": _REGIME_DESC["판별 불가"]}

    adx_val = df["adx"].iloc[-1]
    if pd.isna(adx_val):
        return {"regime": "판별 불가", "adx": None, "desc": _REGIME_DESC["판별 불가"]}

    adx_val = float(adx_val)
    if adx_val >= ADX_TREND_THRESHOLD:
        regime = "추세장"
    elif adx_val < ADX_RANGE_THRESHOLD:
        regime = "횡보장"
    else:
        regime = "전환 구간"

    return {"regime": regime, "adx": round(adx_val, 1), "desc": _REGIME_DESC[regime]}
