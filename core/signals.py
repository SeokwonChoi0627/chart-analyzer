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

def _eval_ma(last, prev) -> tuple[float, str, str]:
    """
    이평선 정/역배열 + SMA20 기울기로 추세 강도 보정.
    - 정배열이라도 SMA20이 꺾이는 중이면 점수 절반 (후기 진입 경고)
    - 역배열이라도 SMA20이 반등 중이면 점수 절반 (바닥 탈출 가능성)
    """
    s5  = last.get("sma5")
    s20 = last.get("sma20")
    s60 = last.get("sma60")
    ps20 = prev.get("sma20")
    if not (_safe(s5) and _safe(s20) and _safe(s60)):
        return 0.0, "데이터 없음", "이평선 계산 불가 (데이터 부족)"

    s5f, s20f, s60f = float(s5), float(s20), float(s60)
    slope_up = _safe(ps20) and s20f > float(ps20)   # SMA20 상승 중
    slope_dn = _safe(ps20) and s20f < float(ps20)   # SMA20 하락 중

    if s5f > s20f > s60f:
        if slope_up:
            return W_MA, "매수", f"정배열 + SMA20 상승 — 추세 유효"
        else:
            return W_MA * 0.5, "매수(약)", f"정배열이나 SMA20 꺾임 — 상승 후기 주의"
    if s5f < s20f < s60f:
        if slope_dn:
            return -W_MA, "매도", f"역배열 + SMA20 하락 — 하락추세 유효"
        else:
            return -W_MA * 0.5, "매도(약)", f"역배열이나 SMA20 반등 — 바닥 탈출 가능성"
    return 0.0, "중립", f"SMA5={s5f:.0f} / SMA20={s20f:.0f} / SMA60={s60f:.0f} — 정/역배열 미해당"


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


def _eval_rsi(last, prev) -> tuple[float, str, str]:
    """
    RSI 단순 위치 → 30/70 돌파 시점 + 50선 방향 감지.
    - 30 하향 후 30 상향 돌파 = 강한 매수 (반등 확인)
    - 70 상향 후 70 하향 돌파 = 강한 매도 (과열 해소)
    - 50선 상향 돌파 = 중립 → 매수 전환 신호
    - 50선 하향 돌파 = 중립 → 매도 전환 신호
    - 기존처럼 30 이하 / 70 이상 단순 위치도 절반 점수로 유지
    """
    rsi  = last.get("rsi")
    prsi = prev.get("rsi")
    if not _safe(rsi):
        return 0.0, "데이터 없음", "RSI 계산 불가"
    rsi = float(rsi)

    if _safe(prsi):
        prsi = float(prsi)
        # 30선 상향 돌파 (과매도 탈출 = 반등 확인)
        if prsi <= 30 and rsi > 30:
            return W_RSI, "매수", f"RSI {prsi:.0f}→{rsi:.0f} — 과매도 탈출 (강한 반등 신호)"
        # 70선 하향 돌파 (과매수 해소 = 매도 확인)
        if prsi >= 70 and rsi < 70:
            return -W_RSI, "매도", f"RSI {prsi:.0f}→{rsi:.0f} — 과매수 해소 (강한 매도 신호)"
        # 50선 상향 돌파 (추세 전환 확인)
        if prsi < 50 and rsi >= 50:
            return W_RSI * 0.5, "매수", f"RSI {prsi:.0f}→{rsi:.0f} — 50선 상향 돌파 (상승 전환)"
        # 50선 하향 돌파 (추세 약화 확인)
        if prsi > 50 and rsi <= 50:
            return -W_RSI * 0.5, "매도", f"RSI {prsi:.0f}→{rsi:.0f} — 50선 하향 돌파 (하락 전환)"

    # 돌파 없을 때 단순 위치 (기존 로직, 절반 점수)
    if rsi <= 30:
        return W_RSI * 0.5, "매수", f"RSI {rsi:.0f} — 과매도 구간 (돌파 대기)"
    if rsi >= 70:
        return -W_RSI * 0.5, "매도", f"RSI {rsi:.0f} — 과매수 구간 (이탈 대기)"
    return 0.0, "중립", f"RSI {rsi:.0f} — 중립 구간 (30~70)"


def _eval_bb(last) -> tuple[float, str, str]:
    """
    볼린저밴드 %B로 밴드 내 위치를 연속값으로 활용.
    - %B ≤ 0     : 하단 이탈 → 강한 매수 (W_BB)
    - %B < 0.2   : 하단 근접 → 약한 매수 (W_BB × 0.5)
    - %B ≥ 1     : 상단 이탈 → 강한 매도 (-W_BB)
    - %B > 0.8   : 상단 근접 → 약한 매도 (-W_BB × 0.5)
    - 그 외       : 중립
    """
    bbl = last.get("bb_lower");  bbu = last.get("bb_upper")
    c   = last.get("close")
    if not (_safe(bbl) and _safe(bbu) and _safe(c)):
        return 0.0, "데이터 없음", "볼린저밴드 계산 불가"
    bbl, bbu, cv = float(bbl), float(bbu), float(c)
    band_width = bbu - bbl
    if band_width <= 0:
        return 0.0, "중립", "밴드폭 0 — 계산 불가"

    pct_b = (cv - bbl) / band_width  # %B

    if pct_b <= 0:
        return W_BB, "매수", f"%B {pct_b:.2f} — 하단밴드 이탈 ({cv:.0f} ≤ {bbl:.0f})"
    if pct_b < 0.2:
        return W_BB * 0.5, "매수(약)", f"%B {pct_b:.2f} — 하단 근접 (하단 {bbl:.0f})"
    if pct_b >= 1:
        return -W_BB, "매도", f"%B {pct_b:.2f} — 상단밴드 이탈 ({cv:.0f} ≥ {bbu:.0f})"
    if pct_b > 0.8:
        return -W_BB * 0.5, "매도(약)", f"%B {pct_b:.2f} — 상단 근접 (상단 {bbu:.0f})"
    return 0.0, "중립", f"%B {pct_b:.2f} — 밴드 중립 구간"


def _eval_vol(last, prev) -> tuple[float, str, str]:
    """
    거래량 4분면 판별.
    - 급증(≥1.5배) + 상승 : 강한 매수 (W_VOL)
    - 급증(≥1.5배) + 하락 : 강한 매도 (-W_VOL)
    - 저조(<0.7배) + 상승  : 약한 랠리 경고 (-W_VOL × 0.3)
    - 저조(<0.7배) + 하락  : 공포 매도 소진 가능 (+W_VOL × 0.3)
    - 그 외                : 중립
    """
    vr = last.get("vol_ratio")
    if not _safe(vr):
        return 0.0, "데이터 없음", "거래량 비율 계산 불가"
    vr   = float(vr)
    rose = _f(last, "close") >= _f(prev, "close")

    if vr >= 1.5 and rose:
        return W_VOL, "매수", f"거래량 {vr:.1f}배 급증 + 상승 — 강한 매수세"
    if vr >= 1.5 and not rose:
        return -W_VOL, "매도", f"거래량 {vr:.1f}배 급증 + 하락 — 강한 매도세"
    if vr < 0.7 and rose:
        return -W_VOL * 0.3, "주의", f"거래량 {vr:.1f}배 저조 + 상승 — 세력 없는 약한 랠리"
    if vr < 0.7 and not rose:
        return W_VOL * 0.3, "중립(약)", f"거래량 {vr:.1f}배 저조 + 하락 — 공포 매도 소진 가능"
    return 0.0, "중립", f"거래량 {vr:.1f}배 — 기준(1.5배) 미달"


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
        ("이평선",    _eval_ma(last, prev)),
        ("MACD",      _eval_macd(last, prev)),
        ("RSI",       _eval_rsi(last, prev)),
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


# ── 급등 과열 필터 ────────────────────────────────────────────────────────────

def is_overheated(df: pd.DataFrame, n: int = 10, threshold: float = 0.15) -> bool:
    """최근 n봉의 누적 수익률이 threshold를 초과하면 단기 과열로 판단."""
    if df.empty or len(df) < n + 1:
        return False
    closes = df["close"].dropna()
    if len(closes) < n + 1:
        return False
    base = float(closes.iloc[-(n + 1)])
    if base <= 0:
        return False
    cumret = (float(closes.iloc[-1]) - base) / base
    return cumret > threshold


# ── 15분봉 단기 신호 ──────────────────────────────────────────────────────────

def _classify_intraday(score: float) -> str:
    if score >= 2.0:   return "단기 매수 타이밍"
    if score >= 0.5:   return "단기 상승 기조"
    if score > -0.5:   return "단기 중립"
    if score > -2.0:   return "단기 하락 기조"
    return "단기 매도 타이밍"


def is_structural_break(
    df_15m: pd.DataFrame,
    daily_atr: float,
    lookback: int = 20,
    atr_mult: float = 1.5,
) -> bool:
    """최근 lookback봉 고점 대비 낙폭이 daily_atr × atr_mult 초과면 구조적 이탈."""
    if daily_atr <= 0 or df_15m.empty or len(df_15m) < 2:
        return False
    closes = df_15m["close"].dropna()
    if len(closes) < 2:
        return False
    recent_high = float(closes.iloc[-lookback:].max()) if len(closes) >= lookback else float(closes.max())
    current     = float(closes.iloc[-1])
    drawdown    = recent_high - current
    return drawdown > daily_atr * atr_mult


def generate_intraday_signal(
    df: pd.DataFrame,
    overheat_n: int = 10,
    overheat_threshold: float = 0.15,
    daily_atr: float = 0.0,
) -> dict:
    """15분봉 compute_all 결과를 받아 단기 보조 신호 생성.
    점수 범위: ±4.5 (RSI ±1.5 / MACD ±1.0 / 거래량·이평선·BB·캔들 각 ±0.5)
    모든 지표를 항상 reasons에 포함."""
    if df.empty or len(df) < 26:
        return {"score": 0.0, "verdict": "데이터 부족", "reasons": [],
                "last_price": None, "last_time": "", "overheated": False,
                "structural_break": False}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else last
    score = 0.0
    reasons: list[dict] = []

    # 1) RSI — 30/70 돌파 시점 + 50선 방향 (±1.5)
    rsi  = last.get("rsi")
    prsi = prev.get("rsi")
    if _safe(rsi):
        rsi = float(rsi)
        if _safe(prsi):
            prsi = float(prsi)
            if prsi <= 30 and rsi > 30:
                s, sig, note = _W_INTRA_RSI, "과매도 탈출", f"RSI {prsi:.0f}→{rsi:.0f} — 반등 확인"
            elif prsi >= 70 and rsi < 70:
                s, sig, note = -_W_INTRA_RSI, "과매수 해소", f"RSI {prsi:.0f}→{rsi:.0f} — 매도 확인"
            elif prsi < 50 and rsi >= 50:
                s, sig, note = _W_INTRA_RSI * 0.5, "상승전환", f"RSI {prsi:.0f}→{rsi:.0f} — 50선 상향 돌파"
            elif prsi > 50 and rsi <= 50:
                s, sig, note = -_W_INTRA_RSI * 0.5, "하락전환", f"RSI {prsi:.0f}→{rsi:.0f} — 50선 하향 돌파"
            elif rsi <= 30:
                s, sig, note = _W_INTRA_RSI * 0.5, "과매도", f"RSI {rsi:.0f} → 과매도 구간 (돌파 대기)"
            elif rsi >= 70:
                s, sig, note = -_W_INTRA_RSI * 0.5, "과매수", f"RSI {rsi:.0f} → 과매수 구간 (이탈 대기)"
            else:
                s, sig, note = 0.0, "중립", f"RSI {rsi:.0f} → 중립 구간 (30~70)"
        else:
            # prev RSI 없을 때 기존 방식
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

    # 2) MACD 히스토그램 방향 전환 감지 (±1.0)
    hist  = last.get("macd_hist")
    phist = prev.get("macd_hist")
    if _safe(hist):
        hist = float(hist)
        if _safe(phist):
            phist = float(phist)
            # 히스토그램 방향 전환 (크로스 2~3봉 전 조기 포착)
            if phist < 0 and hist > phist:
                # 음수 구간에서 증가 전환 = 하락 모멘텀 약화
                s, sig, note = _W_INTRA_MACD, "반등 전환", f"히스토그램 {phist:+.4f}→{hist:+.4f} — 하락 모멘텀 약화"
            elif phist > 0 and hist < phist:
                # 양수 구간에서 감소 전환 = 상승 모멘텀 약화
                s, sig, note = -_W_INTRA_MACD, "하락 전환", f"히스토그램 {phist:+.4f}→{hist:+.4f} — 상승 모멘텀 약화"
            elif hist > 0:
                s, sig, note = _W_INTRA_MACD * 0.5, "상승", f"히스토그램 {hist:+.4f} — 단기 상승 우위"
            elif hist < 0:
                s, sig, note = -_W_INTRA_MACD * 0.5, "하락", f"히스토그램 {hist:+.4f} — 단기 하락 우위"
            else:
                s, sig, note = 0.0, "중립", "히스토그램 0 — 추세 전환점"
        else:
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

    # 3) 거래량 4분면 (±0.5)
    vr = last.get("vol_ratio")
    if _safe(vr):
        vr = float(vr)
        rose = _f(last, "close") >= _f(last, "open")
        if vr >= 1.5 and rose:
            s, sig, note = _W_INTRA_VOL, "급증+양봉", f"거래량 {vr:.1f}배 급증 · 양봉"
        elif vr >= 1.5 and not rose:
            s, sig, note = -_W_INTRA_VOL, "급증+음봉", f"거래량 {vr:.1f}배 급증 · 음봉"
        elif vr < 0.7 and rose:
            s, sig, note = -_W_INTRA_VOL * 0.5, "주의", f"거래량 {vr:.1f}배 저조 · 양봉 — 약한 랠리"
        elif vr < 0.7 and not rose:
            s, sig, note = _W_INTRA_VOL * 0.5, "중립(약)", f"거래량 {vr:.1f}배 저조 · 음봉 — 공포 소진 가능"
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

    # 5) 볼린저밴드 %B (±0.5)
    bbl = last.get("bb_lower");  bbu = last.get("bb_upper")
    c   = last.get("close")
    if _safe(bbl) and _safe(bbu) and _safe(c):
        bbl, bbu, cv = float(bbl), float(bbu), float(c)
        band_width = bbu - bbl
        if band_width > 0:
            pct_b = (cv - bbl) / band_width
            if pct_b <= 0:
                s, sig, note = _W_INTRA_BB, "하단이탈", f"%B {pct_b:.2f} — 하단밴드 이탈"
            elif pct_b < 0.2:
                s, sig, note = _W_INTRA_BB * 0.5, "하단근접", f"%B {pct_b:.2f} — 하단 근접"
            elif pct_b >= 1:
                s, sig, note = -_W_INTRA_BB, "상단이탈", f"%B {pct_b:.2f} — 상단밴드 이탈"
            elif pct_b > 0.8:
                s, sig, note = -_W_INTRA_BB * 0.5, "상단근접", f"%B {pct_b:.2f} — 상단 근접"
            else:
                s, sig, note = 0.0, "중립", f"%B {pct_b:.2f} — 밴드 중립 구간"
        else:
            s, sig, note = 0.0, "중립", "밴드폭 0 — 계산 불가"
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

    overheated      = is_overheated(df, n=overheat_n, threshold=overheat_threshold)
    structural_break = is_structural_break(df, daily_atr=daily_atr) if daily_atr > 0 else False

    if overheated and score > 0:
        score = 0.0

    return {
        "score":            round(score, 2),
        "verdict":          _classify_intraday(score),
        "reasons":          reasons,
        "last_price":       last_price,
        "last_time":        last_time,
        "overheated":       overheated,
        "structural_break": structural_break,
    }
