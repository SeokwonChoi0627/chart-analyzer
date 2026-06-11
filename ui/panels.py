import pandas as pd
import streamlit as st

# ── 판정별 컬러 설정 ─────────────────────────────────────────────────────────
_VERDICT_CFG: dict[str, dict] = {
    "강력 매수": {"color": "#0a8a0a", "bg": "#f0faf0", "border": "#a5d6a7"},
    "매수 고려": {"color": "#4caf50", "bg": "#f5fbf5", "border": "#c8e6c9"},
    "중립/관망": {"color": "#757575", "bg": "#fafafa", "border": "#e0e0e0"},
    "매도 고려": {"color": "#f4511e", "bg": "#fff8f6", "border": "#ffccbc"},
    "강력 매도": {"color": "#c62828", "bg": "#fff5f5", "border": "#ef9a9a"},
}

# 이평선3 + MACD2 + 거래량2 + RSI1.5 + BB1 + 캔들1.5 + 다이버전스1.5
# + 국면 가중(이평선·MACD ×1.3) ≈ 실용 최대 ±12
_SCORE_MIN = -12.0
_SCORE_MAX = 12.0


def _pct(score: float) -> float:
    clamped = max(_SCORE_MIN, min(_SCORE_MAX, score))
    return (clamped - _SCORE_MIN) / (_SCORE_MAX - _SCORE_MIN) * 100


def _gauge_html(score: float) -> str:
    pct = _pct(score)
    p_n5 = _pct(-5)
    p_n2 = _pct(-2)
    p_p2 = _pct(2)
    p_p5 = _pct(5)

    gradient = (
        "linear-gradient(to right,"
        "#c62828 0%,"
        f"#f4511e {p_n5:.1f}%,"
        f"#e8e8e8 {p_n2:.1f}%,"
        f"#e8e8e8 {p_p2:.1f}%,"
        f"#4caf50 {p_p5:.1f}%,"
        "#0a8a0a 100%)"
    )

    labels = [
        (0,     "−12",  "translateX(0)"),
        (p_n5,  "−5",   "translateX(-50%)"),
        (p_n2,  "−2",   "translateX(-50%)"),
        (50,    "0",    "translateX(-50%)"),
        (p_p2,  "+2",   "translateX(-50%)"),
        (p_p5,  "+5",   "translateX(-50%)"),
        (100,   "+12",  "translateX(-100%)"),
    ]
    label_spans = "".join(
        f'<span style="position:absolute;left:{p:.1f}%;transform:{tx};'
        f'font-size:10px;color:#aaa;white-space:nowrap;">{lbl}</span>'
        for p, lbl, tx in labels
    )

    return (
        f'<div style="margin:20px 0 8px;padding:0 2px;">'
        f'<div style="position:relative;height:10px;border-radius:5px;'
        f'background:{gradient};overflow:visible;">'
        f'<div style="position:absolute;left:{pct:.1f}%;top:-6px;'
        f'transform:translateX(-50%);width:3px;height:22px;'
        f'background:#1d1d1f;border-radius:2px;'
        f'box-shadow:0 1px 5px rgba(0,0,0,0.28);"></div>'
        f'</div>'
        f'<div style="position:relative;height:18px;margin-top:5px;">'
        f'{label_spans}'
        f'</div>'
        f'</div>'
    )


def render_signal_card(signal: dict, source: str, analyzed_at: str = "") -> None:
    verdict = signal["verdict"]
    score = signal["score"]
    cfg = _VERDICT_CFG.get(verdict, _VERDICT_CFG["중립/관망"])
    color, bg, border = cfg["color"], cfg["bg"], cfg["border"]

    time_row = (
        f'<div style="font-size:11px;color:#bbb;margin-top:1px;">분석 시점 &nbsp;{analyzed_at}</div>'
        if analyzed_at else ""
    )

    st.markdown(
        f'<div style="background:{bg};border:1.5px solid {border};border-radius:18px;'
        f'padding:24px 26px 18px;margin-bottom:12px;'
        f'font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif;">'
        f'<div style="font-size:13px;font-weight:600;color:#aaa;'
        f'letter-spacing:0.6px;text-transform:uppercase;margin-bottom:4px;">일봉 기준 판정</div>'
        f'<div style="font-size:30px;font-weight:600;color:{color};'
        f'letter-spacing:-0.3px;line-height:1.1;">{verdict}</div>'
        f'{_gauge_html(score)}'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-end;'
        f'margin-top:14px;padding-top:12px;border-top:1px solid {border};">'
        f'<div>'
        f'<div style="font-size:11px;color:#aaa;margin-bottom:2px;letter-spacing:0.4px;">종합점수</div>'
        f'<div style="font-size:24px;font-weight:600;color:{color};'
        f'letter-spacing:-0.24px;line-height:1;">{score:+.1f}'
        f'<span style="font-size:13px;font-weight:400;color:#bbb;">&nbsp;/ ±12</span></div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:11px;color:#bbb;">데이터 &nbsp;{source}</div>'
        f'{time_row}'
        f'</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


_INTRADAY_CFG: dict[str, dict] = {
    "단기 매수 타이밍": {"color": "#0a8a0a", "bg": "#f0faf0", "border": "#a5d6a7"},
    "단기 상승 기조":   {"color": "#4caf50", "bg": "#f5fbf5", "border": "#c8e6c9"},
    "단기 중립":        {"color": "#757575", "bg": "#fafafa", "border": "#e0e0e0"},
    "단기 하락 기조":   {"color": "#f4511e", "bg": "#fff8f6", "border": "#ffccbc"},
    "단기 매도 타이밍": {"color": "#c62828", "bg": "#fff5f5", "border": "#ef9a9a"},
    "데이터 부족":      {"color": "#9e9e9e", "bg": "#f9f9f9", "border": "#e0e0e0"},
}


def _intraday_gauge_html(score: float) -> str:
    # ±4.5 범위 (RSI±1.5 + MACD±1.0 + 거래량·이평선·BB·캔들 각 ±0.5)
    pct = (max(-4.5, min(4.5, score)) + 4.5) / 9.0 * 100
    return (
        f'<div style="margin:10px 0 6px;">'
        f'<div style="position:relative;height:8px;border-radius:4px;'
        f'background:linear-gradient(to right,'
        f'#c62828 0%,#f4511e 33%,#d9d9d9 44%,#d9d9d9 56%,#4caf50 67%,#0a8a0a 100%);'
        f'overflow:visible;">'
        f'<div style="position:absolute;left:{pct:.1f}%;top:-5px;'
        f'transform:translateX(-50%);width:3px;height:18px;'
        f'background:#1d1d1f;border-radius:2px;'
        f'box-shadow:0 1px 4px rgba(0,0,0,0.25);"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;'
        f'margin-top:4px;font-size:9px;color:#ccc;">'
        f'<span>−4.5</span><span>0</span><span>+4.5</span>'
        f'</div>'
        f'</div>'
    )


def render_intraday_panel(signal_15m: dict) -> None:
    """15분봉 단기 신호 카드 + 지표 테이블."""
    verdict = signal_15m.get("verdict", "데이터 부족")
    score   = signal_15m.get("score", 0.0)
    last_time = signal_15m.get("last_time", "")
    cfg = _INTRADAY_CFG.get(verdict, _INTRADAY_CFG["데이터 부족"])
    color, bg, border = cfg["color"], cfg["bg"], cfg["border"]

    time_note = (
        f'<span style="font-size:10px;color:#bbb;margin-left:8px;">{last_time}</span>'
        if last_time else ""
    )

    st.markdown(
        f'<div style="background:{bg};border:1px solid {border};border-radius:14px;'
        f'padding:16px 20px 12px;margin-bottom:12px;'
        f'font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif;">'
        f'<div style="font-size:11px;font-weight:600;color:#aaa;'
        f'letter-spacing:0.6px;text-transform:uppercase;margin-bottom:3px;">'
        f'15분봉 단기 신호</div>'
        f'<div style="font-size:20px;font-weight:600;color:{color};'
        f'letter-spacing:-0.2px;">{verdict}{time_note}</div>'
        f'{_intraday_gauge_html(score)}'
        f'<div style="font-size:12px;color:{color};font-weight:600;">'
        f'단기 점수 {score:+.2f} / ±4.5</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    reasons = signal_15m.get("reasons", [])
    if reasons:
        table = pd.DataFrame(reasons).rename(columns={
            "indicator": "지표", "signal": "신호", "score": "점수", "note": "근거",
        })
        table["점수"] = table["점수"].map(lambda v: f"{v:+.1f}")
        st.dataframe(table, hide_index=True, use_container_width=True)


def render_reasons_table(signal: dict) -> None:
    st.markdown(
        '<div style="font-size:13px;font-weight:600;color:#aaa;'
        'letter-spacing:0.6px;text-transform:uppercase;'
        'margin:4px 0 8px;font-family:system-ui,-apple-system,sans-serif;">'
        "지표별 근거</div>",
        unsafe_allow_html=True,
    )
    reasons = signal.get("reasons", [])
    if not reasons:
        st.markdown(
            '<p style="color:#bbb;font-size:14px;text-align:center;padding:12px 0;">'
            "뚜렷한 매수/매도 신호 없음 (중립)</p>",
            unsafe_allow_html=True,
        )
        return

    table = pd.DataFrame(reasons).rename(columns={
        "indicator": "지표", "signal": "신호", "score": "점수", "note": "근거",
    })
    table["점수"] = table["점수"].map(lambda v: f"{v:+.1f}")
    st.dataframe(table, hide_index=True, use_container_width=True)


# ── 타점 포착 카드 ────────────────────────────────────────────────────────────
#
# 7단계 색상 스펙트럼 (빨강=매수, 파랑=매도)
# 1. 강력 매수 타점  #c62828  (진한 빨강)
# 2. 매수 타점      #e53935  (빨강)
# 3. 상승 추세 진행  #ef6c00  (주황)
# 4. 관망           #757575  (회색)
# 5. 하락 추세 진행  #5c8fd6  (연한 파랑)
# 6. 매도 타점      #1565c0  (파랑)
# 7. 강력 매도 타점  #0d3c7a  (진한 파랑)

# (stage_id, label, accent, dot_color)
_STAGES = [
    ("strong_buy",  "강력 매수 타점",  "#0a8a0a", "#0a8a0a"),
    ("buy",         "매수 타점",       "#2e7d32", "#43a047"),
    ("up_trend",    "상승 추세 진행",  "#66bb6a", "#66bb6a"),
    ("neutral",     "관망",            "#9e9e9e", "#bdbdbd"),
    ("down_trend",  "하락 추세 진행",  "#ef9a9a", "#ef9a9a"),
    ("sell",        "매도 타점",       "#c62828", "#e53935"),
    ("strong_sell", "강력 매도 타점",  "#7f0000", "#b71c1c"),
]
_STAGE_MAP = {s[0]: s for s in _STAGES}


def _classify_stage(daily: float, intra: float) -> tuple[str, str]:
    """(stage_id, desc) 반환."""
    d_up   = daily >= 2.0
    d_sup  = daily >= 5.0
    d_dn   = daily <= -2.0
    d_sdn  = daily <= -5.0
    i_dn   = intra <= -0.5
    i_sdn  = intra <= -1.5
    i_up   = intra >= 0.5
    i_sup  = intra >= 1.5

    if d_sup and i_sdn:
        return "strong_buy", (
            f"일봉 강한 상승({daily:+.1f}) + 15분봉 급락({intra:+.1f})\n"
            f"강력한 눌림목 — 최적 매수 타이밍"
        )
    if d_up and i_dn:
        return "buy", (
            f"일봉 상승추세({daily:+.1f}) + 15분봉 단기 하락({intra:+.1f})\n"
            f"눌림목 매수 구간 — 분할 매수 고려"
        )
    if d_up and not i_dn:
        return "up_trend", (
            f"일봉 상승추세({daily:+.1f}) + 15분봉 동반 상승({intra:+.1f})\n"
            f"추세 진행 중 — 추격 매수 주의, 눌림목 대기"
        )
    if d_sdn and i_sup:
        return "strong_sell", (
            f"일봉 강한 하락({daily:+.1f}) + 15분봉 급반등({intra:+.1f})\n"
            f"강력한 반등 매도 — 최적 매도 타이밍"
        )
    if d_dn and i_up:
        return "sell", (
            f"일봉 하락추세({daily:+.1f}) + 15분봉 단기 반등({intra:+.1f})\n"
            f"반등 매도 구간 — 분할 매도 고려"
        )
    if d_dn and not i_up:
        return "down_trend", (
            f"일봉 하락추세({daily:+.1f}) + 15분봉 동반 하락({intra:+.1f})\n"
            f"하락 추세 지속 — 신규 매수 금지, 관망"
        )
    return "neutral", (
        f"일봉 중립({daily:+.1f}) / 15분봉 {intra:+.1f}\n"
        f"뚜렷한 추세 없음 — 방향 확인 후 진입"
    )


def render_entry_point_card(daily_score: float, intraday_score: float,
                            fin: dict | None = None) -> None:
    """다중 타임프레임 타점 카드 — Apple 디자인, 항상 표시."""
    stage_id, desc = _classify_stage(daily_score, intraday_score)
    _, label, accent, _ = _STAGE_MAP[stage_id]

    stage_ids = [s[0] for s in _STAGES]
    stage_idx = stage_ids.index(stage_id)

    # ── 선행 PER 안내 ──────────────────────────────────────────────────────────
    per_row = ""
    if fin:
        val = fin.get("valuation") or {}
        try:
            trailing = float(str(val.get("PER(후행)") or "").replace("배","").strip() or "0")
            forward  = float(str(val.get("PER(선행)") or "").replace("배","").strip() or "0")
            if 0 < forward < trailing:
                per_row = (
                    f'<div style="display:flex;align-items:center;gap:8px;'
                    f'margin-top:14px;padding:10px 14px;'
                    f'background:#f0faf0;border-radius:11px;">'
                    f'<span style="font-size:13px;font-weight:600;color:#2e7d32;'
                    f'letter-spacing:-0.2px;">장기 유망</span>'
                    f'<span style="font-size:13px;color:#444;letter-spacing:-0.374px;">'
                    f'선행PER {forward:.1f}배 &lt; 후행PER {trailing:.1f}배 — 이익 증가 기대</span>'
                    f'</div>'
                )
        except (ValueError, AttributeError):
            pass

    # ── 7단계 스펙트럼 도트 ────────────────────────────────────────────────────
    dot_colors = [s[3] for s in _STAGES]
    dots_html = ""
    for i, dc in enumerate(dot_colors):
        if i == stage_idx:
            dots_html += (
                f'<span style="display:inline-block;width:16px;height:16px;'
                f'border-radius:50%;background:{dc};'
                f'box-shadow:0 0 0 3px #fff,0 0 0 5px {dc};'
                f'margin:0 5px;vertical-align:middle;"></span>'
            )
        else:
            dots_html += (
                f'<span style="display:inline-block;width:10px;height:10px;'
                f'border-radius:50%;background:{dc};opacity:0.28;'
                f'margin:0 5px;vertical-align:middle;"></span>'
            )

    desc_lines = desc.split("\n")
    desc_main  = desc_lines[0] if desc_lines else desc
    desc_sub   = desc_lines[1] if len(desc_lines) > 1 else ""

    st.markdown(
        # 카드 컨테이너 — Apple store-utility-card
        f'<div style="'
        f'background:#ffffff;'
        f'border:1px solid rgba(0,0,0,0.08);'
        f'border-radius:18px;'
        f'box-shadow:0 2px 12px rgba(0,0,0,0.06);'
        f'padding:28px 32px 26px;'
        f'margin:24px 0;'
        f'font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;">'

        # 헤더 행
        f'<div style="display:flex;align-items:center;'
        f'justify-content:space-between;margin-bottom:16px;">'
        f'<span style="font-size:22px;font-weight:700;color:#1d1d1f;'
        f'letter-spacing:-0.4px;">종합 결론</span>'
        f'<span style="font-size:13px;font-weight:600;color:#ffffff;'
        f'background:{accent};padding:5px 16px;border-radius:9999px;'
        f'letter-spacing:-0.12px;">{label}</span>'
        f'</div>'

        # 스펙트럼 도트
        f'<div style="display:flex;align-items:center;justify-content:center;'
        f'margin-bottom:6px;">{dots_html}</div>'
        f'<div style="margin-bottom:16px;"></div>'

        # 구분선
        f'<div style="height:1px;background:rgba(0,0,0,0.06);margin-bottom:14px;"></div>'

        # 설명 — Apple typography.body (17px / 400 / -0.374px)
        f'<div style="font-size:15px;font-weight:600;color:#1d1d1f;'
        f'letter-spacing:-0.374px;line-height:1.3;margin-bottom:5px;">'
        f'{desc_main}</div>'
        f'<div style="font-size:14px;font-weight:400;color:#636366;'
        f'letter-spacing:-0.224px;line-height:1.5;">'
        f'{desc_sub}</div>'

        # PER 안내
        f'{per_row}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── 리스크 관리 카드 (ATR 손절/목표가) ────────────────────────────────────────

def _fmt_price(v: float, market: str) -> str:
    return f"{v:,.0f}원" if market == "KR" else f"${v:,.2f}"


def render_risk_card(risk: dict | None, entry: float, market: str) -> None:
    """ATR 기반 손절가·목표가·리스크/리워드 카드."""
    if not risk:
        return

    rows = [
        ("손절가",   risk["stop"],    risk["stop_pct"],    "#c62828"),
        ("진입 기준", entry,           0.0,                 "#1d1d1f"),
        ("1차 목표", risk["target1"], risk["target1_pct"], "#2e7d32"),
        ("2차 목표", risk["target2"], risk["target2_pct"], "#0a8a0a"),
    ]
    rows_html = ""
    for label, price, pct, color in rows:
        pct_str = f"{pct:+.1f}%" if pct else "현재가"
        rows_html += (
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;padding:7px 0;border-bottom:1px solid #f0f0f3;">'
            f'<span style="font-size:13px;color:#636366;">{label}</span>'
            f'<span style="text-align:right;">'
            f'<span style="font-size:15px;font-weight:600;color:{color};">'
            f'{_fmt_price(price, market)}</span>'
            f'<span style="font-size:11px;color:#aaa;margin-left:8px;">{pct_str}</span>'
            f'</span></div>'
        )

    st.markdown(
        f'<div style="background:#ffffff;border:1px solid rgba(0,0,0,0.08);'
        f'border-radius:14px;padding:18px 20px 14px;margin-bottom:12px;'
        f'font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:8px;">'
        f'<span style="font-size:11px;font-weight:600;color:#aaa;'
        f'letter-spacing:0.6px;text-transform:uppercase;">리스크 관리 (ATR 기반)</span>'
        f'<span style="font-size:11px;font-weight:600;color:#0066cc;">'
        f'손익비 1:{risk["rr1"]:.1f} ~ 1:{risk["rr2"]:.1f}</span>'
        f'</div>'
        f'{rows_html}'
        f'<div style="font-size:11px;color:#aaa;margin-top:8px;line-height:1.5;">'
        f'손절 = 진입가 − 2×ATR · 목표 = 진입가 + 3~4×ATR<br>'
        f'매수 시 손절가 이탈하면 기계적으로 청산하세요. 출구 규칙이 수익을 지킵니다.'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── 시장 국면 배지 ────────────────────────────────────────────────────────────

_REGIME_CFG = {
    "추세장":   {"color": "#0066cc", "bg": "#f0f6ff", "border": "#bbd6f7", "icon": "📈"},
    "횡보장":   {"color": "#8e6d00", "bg": "#fffbef", "border": "#f0e2af", "icon": "↔️"},
    "전환 구간": {"color": "#757575", "bg": "#fafafa", "border": "#e0e0e0", "icon": "🔄"},
    "판별 불가": {"color": "#9e9e9e", "bg": "#f9f9f9", "border": "#e0e0e0", "icon": "—"},
}


def render_regime_badge(regime_info: dict) -> None:
    """ADX 기반 시장 국면 카드."""
    regime = regime_info.get("regime", "판별 불가")
    adx = regime_info.get("adx")
    desc = regime_info.get("desc", "")
    cfg = _REGIME_CFG.get(regime, _REGIME_CFG["판별 불가"])
    adx_str = f"ADX {adx:.1f}" if adx is not None else "ADX —"

    st.markdown(
        f'<div style="padding:12px 18px;border-radius:14px;margin-bottom:8px;'
        f'background:{cfg["bg"]};border:1.5px solid {cfg["border"]};'
        f'font-family:system-ui,-apple-system,sans-serif;">'
        f'<span style="font-size:14px;font-weight:700;color:{cfg["color"]};">'
        f'{cfg["icon"]} 시장 국면: {regime}</span>'
        f'<span style="font-size:12px;font-weight:600;color:{cfg["color"]};'
        f'margin-left:10px;">{adx_str}</span>'
        f'<div style="font-size:12px;color:#636366;margin-top:3px;">{desc}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── 백테스트 결과 테이블 ──────────────────────────────────────────────────────

def render_backtest_section(bt: dict) -> None:
    """신호 백테스트 결과 — 판정별 적중률/평균 수익률."""
    total = bt.get("total_signals", 0)
    evaluated = bt.get("evaluated_bars", 0)
    if total == 0:
        st.caption("백테스트할 신호 표본이 부족합니다 (최소 80봉 필요).")
        return

    st.markdown(
        f'<div style="font-size:12px;color:#636366;margin-bottom:8px;">'
        f'최근 {evaluated}봉 구간에서 중립 제외 신호 <b>{total}회</b> 발생 — '
        f'신호 발생 후 5봉/20봉 뒤 수익률 기준 적중률입니다.</div>',
        unsafe_allow_html=True,
    )

    rows = []
    for h, buckets in bt.get("horizons", {}).items():
        for verdict, stats in buckets.items():
            rows.append({
                "판정": verdict,
                "기간": f"{h}봉 후",
                "표본": stats["count"],
                "적중률": f"{stats['win_rate']:.0f}%",
                "평균 수익률": f"{stats['avg_return']:+.2f}%",
            })
    if not rows:
        st.caption("집계할 신호가 없습니다.")
        return

    order = {"강력 매수": 0, "매수 고려": 1, "매도 고려": 2, "강력 매도": 3}
    rows.sort(key=lambda r: (order.get(r["판정"], 9), r["기간"]))
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(
        "⚠️ 이 종목의 과거 6개월 데이터 기준이며 미래 수익을 보장하지 않습니다. "
        "적중률이 50% 부근이면 해당 판정은 이 종목에서 신뢰도가 낮다는 뜻입니다."
    )


# ── 스크리너 결과 테이블 ──────────────────────────────────────────────────────

def render_screener_table(results: list[dict], market_fmt: str = "KR") -> None:
    """관심종목 스캔 결과 — 점수순 정렬 테이블."""
    if not results:
        st.info("스캔할 종목이 없습니다.")
        return

    ok_rows = []
    failed = []
    for r in results:
        if r["error"]:
            failed.append(r)
            continue
        close = r["close"]
        price = f"{close:,.0f}" if close >= 1000 else f"{close:,.2f}"
        ok_rows.append({
            "종목": r["symbol"],
            "판정": r["verdict"],
            "점수": f"{r['score']:+.1f}",
            "현재가": price,
            "국면": r["regime"],
            "데이터": r["source"],
        })

    if ok_rows:
        st.dataframe(pd.DataFrame(ok_rows), hide_index=True, use_container_width=True)
    if failed:
        with st.expander(f"조회 실패 {len(failed)}건", expanded=False):
            for r in failed:
                st.caption(f"**{r['symbol']}** — {r['error']}")
