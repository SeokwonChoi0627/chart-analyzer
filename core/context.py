"""시장 심리 · 밸류에이션 컨텍스트 경고.

기술적 신호에 시장 분위기(CNN Fear & Greed)와 재무 상태(적자 여부)를
교차 검증해 맥락 코멘트를 생성한다. 점수에는 반영하지 않고 표시만 한다.
"""

_FEAR_THRESHOLD = 25   # 이하 = 극단적 공포
_GREED_THRESHOLD = 75  # 이상 = 극단적 탐욕


def sentiment_context(fg_score: float | None, daily_score: float) -> dict | None:
    """공포·탐욕 지수와 일봉 점수를 교차해 맥락 코멘트 생성.

    Returns: {"level": "기회"|"주의", "message": str} 또는 None(특이사항 없음).
    """
    if fg_score is None:
        return None

    is_buy = daily_score >= 2.0
    is_sell = daily_score <= -2.0

    if fg_score <= _FEAR_THRESHOLD:
        if is_buy:
            return {
                "level": "기회",
                "message": (
                    f"시장 전체가 극단적 공포 구간(F&G {fg_score:.0f})입니다. "
                    "공포 구간의 매수 신호는 역사적으로 적중률이 높았습니다 — 분할 매수 우호적."
                ),
            }
        return {
            "level": "주의",
            "message": (
                f"시장 전체가 극단적 공포 구간(F&G {fg_score:.0f})입니다. "
                "패닉 구간에서는 신호 변동성이 커집니다 — 포지션 축소·관망 권장."
            ),
        }

    if fg_score >= _GREED_THRESHOLD:
        if is_buy:
            return {
                "level": "주의",
                "message": (
                    f"시장 전체가 극단적 탐욕 구간(F&G {fg_score:.0f})입니다. "
                    "과열 국면의 매수 신호는 추격 매수 위험이 큽니다 — 비중 축소·눌림목 대기."
                ),
            }
        if is_sell:
            return {
                "level": "기회",
                "message": (
                    f"시장 전체가 극단적 탐욕 구간(F&G {fg_score:.0f})입니다. "
                    "과열 국면의 매도 신호는 차익 실현 타이밍일 수 있습니다."
                ),
            }
        return {
            "level": "주의",
            "message": (
                f"시장 전체가 극단적 탐욕 구간(F&G {fg_score:.0f})입니다. "
                "신규 진입은 보수적으로 접근하세요."
            ),
        }

    return None


def _parse_per(fin: dict) -> float | None:
    """fin dict에서 PER 숫자 추출. '12.3배' → 12.3, 실패 시 None."""
    candidates = [
        (fin.get("valuation") or {}).get("PER(후행)"),
        fin.get("per"),
    ]
    for raw in candidates:
        if not raw or raw == "—":
            continue
        try:
            return float(str(raw).replace("배", "").replace(",", "").strip())
        except ValueError:
            continue
    return None


def valuation_warning(fin: dict | None, verdict: str) -> str | None:
    """매수 판정인데 적자 기업(PER 음수)이면 경고 문구 반환."""
    if not fin or "매수" not in verdict:
        return None
    per = _parse_per(fin)
    if per is not None and per < 0:
        return (
            f"PER {per:.1f}배 — 적자 기업입니다. "
            "기술적 매수 신호가 떠도 펀더멘털 리스크 등급이 다릅니다. 비중 관리 필수."
        )
    return None
