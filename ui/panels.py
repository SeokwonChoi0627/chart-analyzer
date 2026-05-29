import pandas as pd
import streamlit as st

_VERDICT_STYLE = {
    "강력 매수": ("🟢", "#0a8a0a"),
    "매수 고려": ("🟢", "#4caf50"),
    "중립/관망": ("⚪", "#9e9e9e"),
    "매도 고려": ("🔴", "#f4511e"),
    "강력 매도": ("🔴", "#c62828"),
}


def render_signal_card(signal: dict, source: str, analyzed_at: str = "") -> None:
    """종합 신호 카드 표시."""
    verdict = signal["verdict"]
    emoji, color = _VERDICT_STYLE.get(verdict, ("⚪", "#9e9e9e"))
    time_line = (
        f'<div style="font-size:12px; color:#999; margin-top:4px;">분석 시점: {analyzed_at}</div>'
        if analyzed_at else ""
    )
    st.markdown(
        f"""
        <div style="border:2px solid {color}; border-radius:12px;
             padding:18px; text-align:center; margin-bottom:12px;">
            <div style="font-size:32px; font-weight:700; color:{color};">
                {emoji} {verdict}
            </div>
            <div style="font-size:18px; color:#555; margin-top:6px;">
                종합점수: {signal['score']:+.1f} / ±9.5
            </div>
            <div style="font-size:12px; color:#999; margin-top:4px;">
                데이터 소스: {source}
            </div>
            {time_line}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_reasons_table(signal: dict) -> None:
    """지표별 점수 근거 테이블."""
    reasons = signal.get("reasons", [])
    if not reasons:
        st.info("뚜렷한 매수/매도 신호가 없습니다 (중립).")
        return
    table = pd.DataFrame(reasons).rename(columns={
        "indicator": "지표", "signal": "신호", "score": "점수", "note": "근거",
    })
    table["점수"] = table["점수"].map(lambda v: f"{v:+.1f}")
    st.dataframe(table, hide_index=True, use_container_width=True)
