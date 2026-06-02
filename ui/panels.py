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

_SCORE_MIN = -9.5
_SCORE_MAX = 9.5


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
        (0,     "−9.5", "translateX(0)"),
        (p_n5,  "−5",   "translateX(-50%)"),
        (p_n2,  "−2",   "translateX(-50%)"),
        (50,    "0",    "translateX(-50%)"),
        (p_p2,  "+2",   "translateX(-50%)"),
        (p_p5,  "+5",   "translateX(-50%)"),
        (100,   "+9.5", "translateX(-100%)"),
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
        f'<span style="font-size:13px;font-weight:400;color:#bbb;">&nbsp;/ ±9.5</span></div>'
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
        f'<span style="font-size:11px;font-weight:600;color:#8e8e93;'
        f'letter-spacing:0.6px;text-transform:uppercase;">종합 결론</span>'
        f'<span style="font-size:12px;font-weight:600;color:#ffffff;'
        f'background:{accent};padding:4px 14px;border-radius:9999px;'
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
