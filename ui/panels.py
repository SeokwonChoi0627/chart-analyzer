import pandas as pd
import streamlit as st

# ── 판정별 컬러 설정 (Apple 단일 강조색 원칙 응용) ──────────────────────
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
    """점수(-9.5 ~ +9.5)를 게이지 백분율(0~100)로 변환."""
    clamped = max(_SCORE_MIN, min(_SCORE_MAX, score))
    return (clamped - _SCORE_MIN) / (_SCORE_MAX - _SCORE_MIN) * 100


def _gauge_html(score: float) -> str:
    """가로형 컬러 게이지 바 + 바늘 HTML 반환."""
    pct = _pct(score)

    # 구간 경계 (%)
    p_n5 = _pct(-5)  # 23.7 %
    p_n2 = _pct(-2)  # 39.5 %
    p_p2 = _pct(2)   # 60.5 %
    p_p5 = _pct(5)   # 76.3 %

    gradient = (
        f"linear-gradient(to right,"
        f"#c62828 0%,#c62828 {p_n5:.1f}%,"
        f"#f4511e {p_n5:.1f}%,#f4511e {p_n2:.1f}%,"
        f"#d9d9d9 {p_n2:.1f}%,#d9d9d9 {p_p2:.1f}%,"
        f"#4caf50 {p_p2:.1f}%,#4caf50 {p_p5:.1f}%,"
        f"#0a8a0a {p_p5:.1f}%,#0a8a0a 100%)"
    )

    # (left%, label, translateX transform)
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

    return f"""
    <div style="margin:20px 0 8px;padding:0 2px;">
      <div style="position:relative;height:12px;border-radius:6px;
           background:{gradient};overflow:visible;">
        <div style="
          position:absolute;left:{pct:.1f}%;top:-7px;
          transform:translateX(-50%);
          width:3px;height:26px;
          background:#1d1d1f;border-radius:2px;
          box-shadow:0 1px 5px rgba(0,0,0,0.28);
        "></div>
      </div>
      <div style="position:relative;height:18px;margin-top:5px;">
        {label_spans}
      </div>
    </div>
    """


def render_signal_card(signal: dict, source: str, analyzed_at: str = "") -> None:
    """Apple 스타일 종합 신호 카드 + 게이지 바 표시."""
    verdict = signal["verdict"]
    score = signal["score"]
    cfg = _VERDICT_CFG.get(verdict, _VERDICT_CFG["중립/관망"])
    color, bg, border = cfg["color"], cfg["bg"], cfg["border"]

    time_row = (
        f'<div style="font-size:11px;color:#bbb;margin-top:1px;">분석 시점 &nbsp;{analyzed_at}</div>'
        if analyzed_at else ""
    )

    st.markdown(
        f"""
        <div style="
          background:{bg};
          border:1.5px solid {border};
          border-radius:18px;
          padding:24px 26px 18px;
          margin-bottom:12px;
          font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        ">
          <!-- 판정 헤드라인 -->
          <div style="font-size:13px;font-weight:600;color:#aaa;
               letter-spacing:0.6px;text-transform:uppercase;margin-bottom:4px;">
            종합 판정
          </div>
          <div style="font-size:30px;font-weight:600;color:{color};
               letter-spacing:-0.3px;line-height:1.1;">
            {verdict}
          </div>

          <!-- 게이지 바 -->
          {_gauge_html(score)}

          <!-- 점수 + 메타 구분선 -->
          <div style="
            display:flex;justify-content:space-between;align-items:flex-end;
            margin-top:14px;padding-top:12px;
            border-top:1px solid {border};
          ">
            <div>
              <div style="font-size:11px;color:#aaa;margin-bottom:2px;letter-spacing:0.4px;">
                종합점수
              </div>
              <div style="font-size:24px;font-weight:600;color:{color};
                   letter-spacing:-0.24px;line-height:1;">
                {score:+.1f}
                <span style="font-size:13px;font-weight:400;color:#bbb;">&nbsp;/ ±9.5</span>
              </div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:11px;color:#bbb;">데이터 &nbsp;{source}</div>
              {time_row}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_reasons_table(signal: dict) -> None:
    """지표별 점수 근거 테이블 (Apple 스타일 섹션 헤더 포함)."""
    st.markdown(
        '<div style="font-size:13px;font-weight:600;color:#aaa;'
        'letter-spacing:0.6px;text-transform:uppercase;'
        'margin:4px 0 8px;font-family:system-ui,-apple-system,sans-serif;">'
        "지표별 근거"
        "</div>",
        unsafe_allow_html=True,
    )

    reasons = signal.get("reasons", [])
    if not reasons:
        st.markdown(
            '<p style="color:#bbb;font-size:14px;text-align:center;padding:12px 0;">'
            "뚜렷한 매수/매도 신호 없음 (중립)"
            "</p>",
            unsafe_allow_html=True,
        )
        return

    table = pd.DataFrame(reasons).rename(columns={
        "indicator": "지표", "signal": "신호", "score": "점수", "note": "근거",
    })
    table["점수"] = table["점수"].map(lambda v: f"{v:+.1f}")
    st.dataframe(table, hide_index=True, use_container_width=True)
