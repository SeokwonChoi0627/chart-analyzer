import os
from datetime import date, datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core.cache import OhlcvCache
from core.data.orchestrator import fetch, DataUnavailableError
from core.data.excel import parse_ohlcv_frame
from core.indicators import compute_all
from core.signals import generate_signal
from ui.chart import build_chart
from ui.panels import render_signal_card, render_reasons_table

load_dotenv()

st.set_page_config(page_title="차트 분석 매수/매도 추천기", page_icon="📈", layout="wide")

CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "cache.db")
PERIOD_MAP = {"3개월": 95, "6개월": 190, "1년": 365}


@st.cache_resource
def get_cache() -> OhlcvCache:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    return OhlcvCache(CACHE_PATH)


_CSS = """
<style>
/* ── 전체 폰트: SF Pro 대체 스택 ── */
html, body, [class*="css"] {
    font-family: system-ui, -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    color: #1d1d1f;
}

/* ── 사이드바: Apple parchment 배경 ── */
section[data-testid="stSidebar"] {
    background-color: #f5f5f7 !important;
}
section[data-testid="stSidebar"] * {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── 메인 타이틀 ── */
h1 {
    font-weight: 600 !important;
    letter-spacing: -0.28px !important;
    color: #1d1d1f !important;
}

/* ── 알림 박스 ── */
div[data-testid="stAlert"] {
    border-radius: 12px !important;
}

/* ── 버튼 ── */
div.stButton > button {
    border-radius: 9999px !important;
    font-weight: 400;
    letter-spacing: -0.1px;
}
div.stButton > button[kind="primary"] {
    background-color: #0066cc !important;
    border: none !important;
}
div.stButton > button[kind="primary"]:hover {
    background-color: #0071e3 !important;
}
div.stButton > button[kind="primary"]:active {
    transform: scale(0.96);
}
</style>
"""


def main():
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title("📈 차트 분석 매수/매도 추천기")

    with st.sidebar:
        st.header("설정")
        symbol = st.text_input("종목", placeholder="삼성전자 / 005930 / AAPL")
        period_label = st.selectbox("기간", list(PERIOD_MAP.keys()), index=1)
        st.divider()
        st.caption("자동 조회 실패 시 아래로 업로드")
        uploaded = st.file_uploader("엑셀/CSV 업로드", type=["xlsx", "xls", "csv"])
        run = st.button("분석 실행", type="primary", use_container_width=True)

    if not run:
        st.info("좌측에서 종목을 입력하고 '분석 실행'을 누르세요.")
        return

    period_days = PERIOD_MAP[period_label]
    df = None
    source = ""

    if uploaded is not None:
        try:
            raw = (pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv")
                   else pd.read_excel(uploaded))
            df = parse_ohlcv_frame(raw)
            source = f"업로드({uploaded.name})"
        except Exception as e:
            st.error(f"파일 파싱 실패: {e}")
            return
    else:
        if not symbol.strip():
            st.warning("종목을 입력하거나 파일을 업로드하세요.")
            return
        try:
            df, source = fetch(symbol, period_days, get_cache())
        except DataUnavailableError as e:
            st.error(str(e))
            return
        except Exception as e:
            st.error(f"데이터 조회 중 오류: {e}")
            return

    if df is None or df.empty:
        st.error("데이터가 비어 있습니다.")
        return
    if len(df) < 60:
        st.warning(f"데이터가 {len(df)}일치뿐입니다. 일부 지표(60일선 등)는 부정확할 수 있습니다.")

    enriched = compute_all(df)
    signal = generate_signal(enriched)
    analyzed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    title = symbol.strip() or (uploaded.name if uploaded else "")
    col1, col2 = st.columns([1, 2])
    with col1:
        render_signal_card(signal, source, analyzed_at)
        render_reasons_table(signal)
    with col2:
        st.plotly_chart(build_chart(enriched, title), use_container_width=True)


if __name__ == "__main__":
    main()
