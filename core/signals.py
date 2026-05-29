import pandas as pd

W_MA = 3.0
W_MACD = 2.0
W_VOL = 2.0
W_RSI = 1.5
W_BB = 1.0


def classify(score: float) -> str:
    """점수에 따른 매수/매도 판정."""
    if score >= 5:
        return "강력 매수"
    if score >= 2:
        return "매수 고려"
    if score > -2:
        return "중립/관망"
    if score > -5:
        return "매도 고려"
    return "강력 매도"


def _safe(val) -> bool:
    """NaN/None이 아닌 유효 숫자인지."""
    return val is not None and pd.notna(val)


def generate_signal(df: pd.DataFrame) -> dict:
    """지표가 채워진 DataFrame의 마지막 행 기준 매수/매도 신호 생성."""
    if df.empty:
        return {"score": 0.0, "verdict": "중립/관망", "reasons": []}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    reasons = []
    score = 0.0

    # 1) 이평선 정배열/역배열 (±3)
    if _safe(last.get("sma5")) and _safe(last.get("sma20")) and _safe(last.get("sma60")):
        if last["sma5"] > last["sma20"] > last["sma60"]:
            score += W_MA
            reasons.append({"indicator": "이평선", "signal": "매수",
                            "score": W_MA, "note": "정배열(5>20>60), 상승추세"})
        elif last["sma5"] < last["sma20"] < last["sma60"]:
            score -= W_MA
            reasons.append({"indicator": "이평선", "signal": "매도",
                            "score": -W_MA, "note": "역배열(5<20<60), 하락추세"})

    # 2) MACD 교차 (±2)
    if _safe(last.get("macd")) and _safe(last.get("macd_signal")) \
            and _safe(prev.get("macd")) and _safe(prev.get("macd_signal")):
        crossed_up = prev["macd"] <= prev["macd_signal"] and last["macd"] > last["macd_signal"]
        crossed_down = prev["macd"] >= prev["macd_signal"] and last["macd"] < last["macd_signal"]
        if crossed_up:
            score += W_MACD
            reasons.append({"indicator": "MACD", "signal": "매수",
                            "score": W_MACD, "note": "시그널선 상향 돌파(골든크로스)"})
        elif crossed_down:
            score -= W_MACD
            reasons.append({"indicator": "MACD", "signal": "매도",
                            "score": -W_MACD, "note": "시그널선 하향 돌파(데드크로스)"})
        elif last["macd"] > last["macd_signal"]:
            score += W_MACD / 2
            reasons.append({"indicator": "MACD", "signal": "매수",
                            "score": W_MACD / 2, "note": "MACD가 시그널선 위(상승 우위)"})
        else:
            score -= W_MACD / 2
            reasons.append({"indicator": "MACD", "signal": "매도",
                            "score": -W_MACD / 2, "note": "MACD가 시그널선 아래(하락 우위)"})

    # 3) RSI (±1.5)
    if _safe(last.get("rsi")):
        rsi = last["rsi"]
        if rsi <= 30:
            score += W_RSI
            reasons.append({"indicator": "RSI", "signal": "매수",
                            "score": W_RSI, "note": f"RSI {rsi:.0f} → 과매도 반등 기대"})
        elif rsi >= 70:
            score -= W_RSI
            reasons.append({"indicator": "RSI", "signal": "매도",
                            "score": -W_RSI, "note": f"RSI {rsi:.0f} → 과매수 구간"})

    # 4) 볼린저밴드 (±1)
    if _safe(last.get("bb_lower")) and _safe(last.get("bb_upper")):
        if last["close"] <= last["bb_lower"]:
            score += W_BB
            reasons.append({"indicator": "볼린저", "signal": "매수",
                            "score": W_BB, "note": "하단 밴드 터치 → 반등 기대"})
        elif last["close"] >= last["bb_upper"]:
            score -= W_BB
            reasons.append({"indicator": "볼린저", "signal": "매도",
                            "score": -W_BB, "note": "상단 밴드 터치 → 과열"})

    # 5) 거래량 동반 (±2)
    if _safe(last.get("vol_ratio")):
        vr = last["vol_ratio"]
        rose = last["close"] >= prev["close"]
        if vr >= 1.5 and rose:
            score += W_VOL
            reasons.append({"indicator": "거래량", "signal": "매수",
                            "score": W_VOL, "note": f"거래량 {vr:.1f}배 급증 + 상승"})
        elif vr >= 1.5 and not rose:
            score -= W_VOL
            reasons.append({"indicator": "거래량", "signal": "매도",
                            "score": -W_VOL, "note": f"거래량 {vr:.1f}배 급증 + 하락"})

    return {"score": round(score, 2), "verdict": classify(score), "reasons": reasons}


# ── 15분봉 단기 신호 ──────────────────────────────────────────────────────────

_W_INTRA_RSI  = 1.5
_W_INTRA_MACD = 1.0
_W_INTRA_VOL  = 0.5   # 총 범위 ±3.0


def _classify_intraday(score: float) -> str:
    if score >= 2.0:
        return "단기 매수 타이밍"
    if score >= 0.5:
        return "단기 상승 기조"
    if score > -0.5:
        return "단기 중립"
    if score > -2.0:
        return "단기 하락 기조"
    return "단기 매도 타이밍"


def generate_intraday_signal(df: pd.DataFrame) -> dict:
    """
    15분봉 compute_all 결과를 받아 단기 보조 신호 생성.
    점수 범위: ±3.0 (RSI ±1.5 / MACD ±1.0 / 거래량 ±0.5)
    """
    if df.empty or len(df) < 26:
        return {"score": 0.0, "verdict": "데이터 부족", "reasons": [],
                "last_price": None, "last_time": ""}

    last = df.iloc[-1]
    score = 0.0
    reasons: list[dict] = []

    # 1) RSI (±1.5)
    rsi = last.get("rsi")
    if _safe(rsi):
        if rsi <= 30:
            score += _W_INTRA_RSI
            reasons.append({"indicator": "RSI(15분)", "signal": "과매도",
                             "score": _W_INTRA_RSI,
                             "note": f"RSI {rsi:.0f} → 단기 반등 구간"})
        elif rsi >= 70:
            score -= _W_INTRA_RSI
            reasons.append({"indicator": "RSI(15분)", "signal": "과매수",
                             "score": -_W_INTRA_RSI,
                             "note": f"RSI {rsi:.0f} → 단기 과열 구간"})

    # 2) MACD 히스토그램 방향 (±1.0)
    hist = last.get("macd_hist")
    if _safe(hist):
        if hist > 0:
            score += _W_INTRA_MACD
            reasons.append({"indicator": "MACD(15분)", "signal": "상승",
                             "score": _W_INTRA_MACD,
                             "note": f"히스토그램 {hist:+.4f} → 단기 상승 우위"})
        elif hist < 0:
            score -= _W_INTRA_MACD
            reasons.append({"indicator": "MACD(15분)", "signal": "하락",
                             "score": -_W_INTRA_MACD,
                             "note": f"히스토그램 {hist:+.4f} → 단기 하락 우위"})

    # 3) 거래량 동반 (±0.5)
    vr = last.get("vol_ratio")
    if _safe(vr) and vr >= 1.5:
        if last["close"] >= last["open"]:
            score += _W_INTRA_VOL
            reasons.append({"indicator": "거래량(15분)", "signal": "급증+양봉",
                             "score": _W_INTRA_VOL,
                             "note": f"거래량 {vr:.1f}배 급증 · 양봉"})
        else:
            score -= _W_INTRA_VOL
            reasons.append({"indicator": "거래량(15분)", "signal": "급증+음봉",
                             "score": -_W_INTRA_VOL,
                             "note": f"거래량 {vr:.1f}배 급증 · 음봉"})

    last_price = float(last["close"]) if _safe(last.get("close")) else None
    last_time = str(df.index[-1])[:16]

    return {
        "score":       round(score, 2),
        "verdict":     _classify_intraday(score),
        "reasons":     reasons,
        "last_price":  last_price,
        "last_time":   last_time,
    }
