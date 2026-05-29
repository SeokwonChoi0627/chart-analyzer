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
