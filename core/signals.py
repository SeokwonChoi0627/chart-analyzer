import pandas as pd

# ── 일봉 가중치 ───────────────────────────────────────────────────────────────
W_MA     = 3.0
W_MACD   = 2.0
W_VOL    = 2.0
W_RSI    = 1.5
W_BB     = 1.0
W_CANDLE = 1.5   # 캔들 패턴 (인걸프 ±1.5 / 망치·슈팅스타 ±1.05)

# ── 15분봉 가중치 (최대 ±4.5) ─────────────────────────────────────────────────
_W_INTRA_RSI    = 1.5
_W_INTRA_MACD   = 1.0
_W_INTRA_VOL    = 0.5
_W_INTRA_SMA    = 0.5
_W_INTRA_BB     = 0.5
_W_INTRA_CANDLE = 0.5


def classify(score: float) -> str:
    """점수에 따른 매수/매도 판정."""
    if score >= 5:   return "강력 매수"
    if score >= 2:   return "매수 고려"
    if score > -2:   return "중립/관망"
    if score > -5:   return "매도 고려"
    return "강력 매도"


def _safe(val) -> bool:
    """NaN/None이 아닌 유효 숫자인지."""
    return val is not None and pd.notna(val)


def _f(row, key: str) -> float:
    """Series에서 float 추출. 없거나 NaN이면 0.0."""
    v = row.get(key) if hasattr(row, "get") else None
    return float(v) if _safe(v) else 0.0


# ── 캔들 패턴 감지 (일봉/15분봉 공용) ─────────────────────────────────────────

def _detect_candle(last, prev) -> tuple[float, str, str]:
    """
    마지막 2봉 기준 캔들 패턴 감지.
    Returns: (strength_fraction, signal_label, note)
      strength_fraction ∈ [-1.0, +1.0]
      실제 점수 = fraction × 호출측 weight
    """
    try:
        o  = _f(last, "open");  h  = _f(last, "high")
        l  = _f(last, "low");   c  = _f(last, "close")
        po = _f(prev, "open");  pc = _f(prev, "close")
    except Exception:
        return 0.0, "중립", "데이터 오류"

    rng = h - l
    if rng <= 0:
        return 0.0, "중립", "패턴 없음"

    body       = abs(c - o)
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l
    body_pct   = body / rng

    # ① 불리시 인걸프: 현재 양봉이 이전 음봉 몸통 완전 포함
    if c > o and pc < po and o <= pc and c >= po:
        return 1.0, "상승 인걸프", "이전 음봉 완전 포함 → 강력 매수 반전"

    # ② 베어리시 인걸프: 현재 음봉이 이전 양봉 몸통 완전 포함
    if c < o and pc > po and c <= po and o >= pc:
        return -1.0, "하락 인걸프", "이전 양봉 완전 포함 → 강력 매도 반전"

    # ③ 망치형: 아래꼬리 ≥ 2× 몸통, 위꼬리 ≤ 0.5× 몸통
    if body_pct >= 0.1 and lower_wick >= body * 2 and upper_wick <= body * 0.5:
        return 0.7, "망치형", "긴 아래꼬리 → 매수세 유입, 반등 기대"

    # ④ 슈팅스타: 위꼬리 ≥ 2× 몸통, 아래꼬리 ≤ 0.5× 몸통
    if body_pct >= 0.1 and upper_wick >= body * 2 and lower_wick <= body * 0.5:
        return -0.7, "슈팅스타", "긴 위꼬리 → 매도세 유입, 하락 경고"

    # ⑤ 도지: 몸통이 전체 범위의 10% 이하
    if body_pct <= 0.1:
        return 0.0, "도지", "몸통 극소 → 방향성 불명확 (중립)"

    return 0.0, "중립", "특이 패턴 없음"


# ── 일봉 지표 평가 헬퍼 ───────────────────────────────────────────────────────

def _eval_ma(last) -> tuple[float, str, str]:
    s5  = last.get("sma5")
    s20 = last.get("sma20")
    s60 = last.get("sma60")
    if not (_safe(s5) and _safe(s20) and _safe(s60)):
        return 0.0, "데이터 없음", "이평선 계산 불가 (데이터 부족)"
    if float(s5) > float(s20) > float(s60):
        return W_MA, "매수", f"정배열(5>{s20:.0f}>60) — 상승추세"
    if float(s5) < float(s20) < float(s60):
        return -W_MA, "매도", f"역배열(5<{s20:.0f}<60) — 하락추세"
    return 0.0, "중립", f"SMA5={float(s5):.0f} / SMA20={float(s20):.0f} / SMA60={float(s60):.0f} — 정/역배열 미해당"


def _eval_macd(last, prev) -> tuple[float, str, str]:
    m   = last.get("macd");        ms  = last.get("macd_signal")
    pm  = prev.get("macd");        pms = prev.get("macd_signal")
    if not (_safe(m) and _safe(ms) and _safe(pm) and _safe(pms)):
        return 0.0, "데이터 없음", "MACD 계산 불가"
    m, ms, pm, pms = float(m), float(ms), float(pm), float(pms)
    if pm <= pms and m > ms:
        return W_MACD, "매수", "시그널선 상향 돌파 (골든크로스)"
    if pm >= pms and m < ms:
        return -W_MACD, "매도", "시그널선 하향 돌파 (데드크로스)"
    if m > ms:
        return W_MACD / 2, "매수", f"MACD {m:+.4f} > 시그널 {ms:+.4f} — 상승 우위"
    return -W_MACD / 2, "매도", f"MACD {m:+.4f} < 시그널 {ms:+.4f} — 하락 우위"


def _eval_rsi(last) -> tuple[float, str, str]:
    rsi = last.get("rsi")
    if not _safe(rsi):
        return 0.0, "데이터 없음", "RSI 계산 불가"
    rsi = float(rsi)
    if rsi <= 30:
        return W_RSI, "매수", f"RSI {rsi:.0f} — 과매도, 반등 기대"
    if rsi >= 70:
        return -W_RSI, "매도", f"RSI {rsi:.0f} — 과매수 구간"
    return 0.0, "중립", f"RSI {rsi:.0f} — 중립 구간 (30~70)"


def _eval_bb(last) -> tuple[float, str, str]:
    bbl = last.get("bb_lower");  bbu = last.get("bb_upper")
    c   = last.get("close")
    if not (_safe(bbl) and _safe(bbu) and _safe(c)):
        return 0.0, "데이터 없음", "볼린저밴드 계산 불가"
    bbl, bbu, c = float(bbl), float(bbu), float(c)
    if c <= bbl:
        return W_BB, "매수", f"종가({c:.0f}) ≤ 하단밴드({bbl:.0f}) — 반등 기대"
    if c >= bbu:
        return -W_BB, "매도", f"종가({c:.0f}) ≥ 상단밴드({bbu:.0f}) — 과열"
    return 0.0, "중립", f"밴드 내부 ({bbl:.0f} ~ {bbu:.0f})"


def _eval_vol(last, prev) -> tuple[float, str, str]:
    vr = last.get("vol_ratio")
    if not _safe(vr):
        return 0.0, "데이터 없음", "거래량 비율 계산 불가"
    vr   = float(vr)
    rose = _f(last, "close") >= _f(prev, "close")
    if vr >= 1.5 and rose:
        return W_VOL, "매수", f"거래량 {vr:.1f}배 급증 + 상승"
    if vr >= 1.5 and not rose:
        return -W_VOL, "매도", f"거래량 {vr:.1f}배 급증 + 하락"
    return 0.0, "중립", f"거래량 {vr:.1f}배 — 급증 기준(1.5배) 미달"


# ── 일봉 종합 신호 ─────────────────────────────────────────────────────────────

def generate_signal(df: pd.DataFrame) -> dict:
    """지표가 채워진 DataFrame의 마지막 행 기준 매수/매도 신호 생성.
    모든 지표를 항상 reasons에 포함(점수 0도 표시)."""
    if df.empty:
        return {"score": 0.0, "verdict": "중립/관망", "reasons": []}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    score = 0.0
    reasons: list[dict] = []

    for label, result in [
        ("이평선",    _eval_ma(last)),
        ("MACD",      _eval_macd(last, prev)),
        ("RSI",       _eval_rsi(last)),
        ("볼린저밴드", _eval_bb(last)),
        ("거래량",    _eval_vol(last, prev)),
    ]:
        s, sig, note = result
        score += s
        reasons.append({"indicator": label, "signal": sig,
                         "score": round(s, 2), "note": note})

    # 캔들 패턴
    frac, sig, note = _detect_candle(last, prev)
    cs = round(frac * W_CANDLE, 2)
    score += cs
    reasons.append({"indicator": "캔들패턴", "signal": sig, "score": cs, "note": note})

    return {"score": round(score, 2), "verdict": classify(score), "reasons": reasons}


# ── 15분봉 단기 신호 ──────────────────────────────────────────────────────────

def _classify_intraday(score: float) -> str:
    if score >= 2.0:   return "단기 매수 타이밍"
    if score >= 0.5:   return "단기 상승 기조"
    if score > -0.5:   return "단기 중립"
    if score > -2.0:   return "단기 하락 기조"
    return "단기 매도 타이밍"


def generate_intraday_signal(df: pd.DataFrame) -> dict:
    """15분봉 compute_all 결과를 받아 단기 보조 신호 생성.
    점수 범위: ±4.5 (RSI ±1.5 / MACD ±1.0 / 거래량·이평선·BB·캔들 각 ±0.5)
    모든 지표를 항상 reasons에 포함."""
    if df.empty or len(df) < 26:
        return {"score": 0.0, "verdict": "데이터 부족", "reasons": [],
                "last_price": None, "last_time": ""}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    score = 0.0
    reasons: list[dict] = []

    # 1) RSI (±1.5)
    rsi = last.get("rsi")
    if _safe(rsi):
        rsi = float(rsi)
        if rsi <= 30:
            s, sig, note = _W_INTRA_RSI, "과매도", f"RSI {rsi:.0f} → 단기 반등 구간"
        elif rsi >= 70:
            s, sig, note = -_W_INTRA_RSI, "과매수", f"RSI {rsi:.0f} → 단기 과열 구간"
        else:
            s, sig, note = 0.0, "중립", f"RSI {rsi:.0f} → 중립 구간 (30~70)"
    else:
        s, sig, note = 0.0, "데이터 없음", "RSI 계산 불가"
    score += s
    reasons.append({"indicator": "RSI(15분)", "signal": sig, "score": s, "note": note})

    # 2) MACD 히스토그램 방향 (±1.0)
    hist = last.get("macd_hist")
    if _safe(hist):
        hist = float(hist)
        if hist > 0:
            s, sig, note = _W_INTRA_MACD, "상승", f"히스토그램 {hist:+.4f} → 단기 상승 우위"
        elif hist < 0:
            s, sig, note = -_W_INTRA_MACD, "하락", f"히스토그램 {hist:+.4f} → 단기 하락 우위"
        else:
            s, sig, note = 0.0, "중립", "히스토그램 0 — 추세 전환점"
    else:
        s, sig, note = 0.0, "데이터 없음", "MACD 계산 불가"
    score += s
    reasons.append({"indicator": "MACD(15분)", "signal": sig, "score": s, "note": note})

    # 3) 거래량 동반 (±0.5)
    vr = last.get("vol_ratio")
    if _safe(vr):
        vr = float(vr)
        if vr >= 1.5:
            if _f(last, "close") >= _f(last, "open"):
                s, sig, note = _W_INTRA_VOL, "급증+양봉", f"거래량 {vr:.1f}배 급증 · 양봉"
            else:
                s, sig, note = -_W_INTRA_VOL, "급증+음봉", f"거래량 {vr:.1f}배 급증 · 음봉"
        else:
            s, sig, note = 0.0, "중립", f"거래량 {vr:.1f}배 — 급증 기준 미달"
    else:
        s, sig, note = 0.0, "데이터 없음", "거래량 비율 계산 불가"
    score += s
    reasons.append({"indicator": "거래량(15분)", "signal": sig, "score": s, "note": note})

    # 4) 이평선 SMA5 vs SMA20 (±0.5)
    s5  = last.get("sma5")
    s20 = last.get("sma20")
    if _safe(s5) and _safe(s20):
        s5f, s20f = float(s5), float(s20)
        if s5f > s20f:
            s, sig, note = _W_INTRA_SMA, "정배열", f"SMA5({s5f:.0f}) > SMA20({s20f:.0f})"
        elif s5f < s20f:
            s, sig, note = -_W_INTRA_SMA, "역배열", f"SMA5({s5f:.0f}) < SMA20({s20f:.0f})"
        else:
            s, sig, note = 0.0, "중립", f"SMA5 = SMA20 ({s5f:.0f})"
    else:
        s, sig, note = 0.0, "데이터 없음", "이평선 계산 불가"
    score += s
    reasons.append({"indicator": "이평선(15분)", "signal": sig, "score": s, "note": note})

    # 5) 볼린저밴드 (±0.5)
    bbl = last.get("bb_lower");  bbu = last.get("bb_upper")
    c   = last.get("close")
    if _safe(bbl) and _safe(bbu) and _safe(c):
        bbl, bbu, cv = float(bbl), float(bbu), float(c)
        if cv <= bbl:
            s, sig, note = _W_INTRA_BB, "하단터치", f"종가({cv:.0f}) ≤ 하단밴드({bbl:.0f})"
        elif cv >= bbu:
            s, sig, note = -_W_INTRA_BB, "상단터치", f"종가({cv:.0f}) ≥ 상단밴드({bbu:.0f})"
        else:
            s, sig, note = 0.0, "중립", f"밴드 내부 ({bbl:.0f}~{bbu:.0f})"
    else:
        s, sig, note = 0.0, "데이터 없음", "볼린저밴드 계산 불가"
    score += s
    reasons.append({"indicator": "볼린저(15분)", "signal": sig, "score": s, "note": note})

    # 6) 캔들 패턴 (±0.5)
    frac, sig, note = _detect_candle(last, prev)
    s = round(frac * _W_INTRA_CANDLE, 2)
    score += s
    reasons.append({"indicator": "캔들패턴(15분)", "signal": sig, "score": s, "note": note})

    last_price = float(last["close"]) if _safe(last.get("close")) else None
    last_time  = str(df.index[-1])[:16]

    return {
        "score":      round(score, 2),
        "verdict":    _classify_intraday(score),
        "reasons":    reasons,
        "last_price": last_price,
        "last_time":  last_time,
    }
