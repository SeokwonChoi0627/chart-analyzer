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
        f'letter-spacing:0.6px;text-transform:uppercase;margin-bottom:4px;">종합 판정</div>'
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

def detect_entry_point(daily_score: float, intraday_score: float,
                       fin: dict | None = None) -> dict:
    """
    일봉 + 15분봉 복합 신호로 타점 유형 판단.

    매수 타점: 일봉 상승추세(≥+2) + 15분봉 단기 하락(≤-0.5)
    매도 타점: 일봉 하락추세(≤-2) + 15분봉 단기 반등(≥+0.5)
    관망: 조건 미충족
    """
    # 선행 PER < 후행 PER → 장기 유망 가산점
    per_bonus = ""
    if fin:
        val = fin.get("valuation") or {}
        try:
            trailing = float(str(val.get("PER(후행)") or "").replace("배", "").strip() or "0")
            forward  = float(str(val.get("PER(선행)") or "").replace("배", "").strip() or "0")
            if 0 < forward < trailing:
                per_bonus = f"선행PER({forward:.1f}) < 후행PER({trailing:.1f}) — 이익 증가 기대"
        except (ValueError, AttributeError):
            pass

    if daily_score >= 2.0 and intraday_score <= -0.5:
        strength = "강력" if daily_score >= 5.0 and intraday_score <= -1.5 else "일반"
        return {
            "type": "buy",
            "label": "매수 타점 포착" if strength == "일반" else "강력 매수 타점",
            "desc": f"일봉 상승추세(+{daily_score:.1f}) + 15분봉 단기 조정({intraday_score:+.1f}) — 눌림목 매수 구간",
            "color": "#0a8a0a" if strength == "강력" else "#2e7d32",
            "bg": "#f0faf0",
            "border": "#a5d6a7",
            "icon": "📈",
            "per_bonus": per_bonus,
        }
    if daily_score <= -2.0 and intraday_score >= 0.5:
        strength = "강력" if daily_score <= -5.0 and intraday_score >= 1.5 else "일반"
        return {
            "type": "sell",
            "label": "매도 타점 포착" if strength == "일반" else "강력 매도 타점",
            "desc": f"일봉 하락추세({daily_score:.1f}) + 15분봉 단기 반등({intraday_score:+.1f}) — 반등 매도 구간",
            "color": "#c62828" if strength == "강력" else "#d84315",
            "bg": "#fff5f5",
            "border": "#ef9a9a",
            "icon": "📉",
            "per_bonus": "",
        }
    return {"type": "none"}


def render_entry_point_card(daily_score: float, intraday_score: float,
                            fin: dict | None = None) -> None:
    """타점 포착 결과 카드 렌더링."""
    ep = detect_entry_point(daily_score, intraday_score, fin)
    if ep["type"] == "none":
        return

    color  = ep["color"]
    bg     = ep["bg"]
    border = ep["border"]
    icon   = ep["icon"]
    label  = ep["label"]
    desc   = ep["desc"]
    per_b  = ep.get("per_bonus", "")

    per_row = (
        f'<div style="margin-top:8px;padding:6px 10px;background:rgba(0,100,200,0.06);'
        f'border-radius:8px;font-size:12px;color:#0055aa;">'
        f'💡 {per_b}</div>'
        if per_b else ""
    )

    st.markdown(
        f'<div style="background:{bg};border:2px solid {border};border-radius:16px;'
        f'padding:18px 22px;margin:16px 0;'
        f'font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif;">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">'
        f'<span style="font-size:20px;">{icon}</span>'
        f'<span style="font-size:15px;font-weight:700;color:{color};'
        f'letter-spacing:-0.2px;">{label}</span>'
        f'<span style="margin-left:auto;font-size:11px;font-weight:600;color:#fff;'
        f'background:{color};padding:2px 8px;border-radius:99px;">신호 감지</span>'
        f'</div>'
        f'<div style="font-size:13px;color:#444;line-height:1.5;">{desc}</div>'
        f'{per_row}'
        f'</div>',
        unsafe_allow_html=True,
    )
