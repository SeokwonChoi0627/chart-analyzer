import os
from datetime import datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core.cache import OhlcvCache
from core.data.orchestrator import fetch, DataUnavailableError
from core.data.excel import parse_ohlcv_frame
from core.data.intraday import fetch_15min
from core.data.base import detect_market
from core.indicators import compute_all
from core.signals import generate_signal, generate_intraday_signal
from ui.chart import build_chart, build_intraday_chart
from ui.panels import render_signal_card, render_reasons_table, render_intraday_panel

load_dotenv()

st.set_page_config(page_title="차트 분석 매수/매도 추천기", page_icon="📈", layout="wide")

CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "cache.db")
PERIOD_DAYS = 190  # 6개월 고정


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

/* ── 폼 제출 버튼 (Enter 키 포함) ── */
div.stFormSubmitButton > button {
    border-radius: 9999px !important;
    background-color: #0066cc !important;
    color: #ffffff !important;
    border: none !important;
    font-weight: 400;
    letter-spacing: -0.1px;
    width: 100%;
}
div.stFormSubmitButton > button:hover {
    background-color: #0071e3 !important;
}
div.stFormSubmitButton > button:active {
    transform: scale(0.96);
}
</style>
"""


def main():
    st.markdown(_CSS, unsafe_allow_html=True)

    # ── 최상단: 타이틀 + 현재 날짜/시간 ──────────────────────────────────────
    now = datetime.now()
    title_col, time_col = st.columns([3, 1])
    with title_col:
        st.title("📈 차트 분석 매수/매도 추천기")
    with time_col:
        st.markdown(
            f'<div style="text-align:right;padding-top:18px;'
            f'font-family:system-ui,-apple-system,sans-serif;">'
            f'<div style="font-size:20px;font-weight:600;color:#1d1d1f;letter-spacing:-0.3px;">'
            f'{now.strftime("%H:%M:%S")}</div>'
            f'<div style="font-size:12px;color:#888;margin-top:2px;">'
            f'{now.strftime("%Y년 %m월 %d일")}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── 사이드바 ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("설정")
        with st.form("analysis_form"):
            symbol = st.text_input("종목", placeholder="삼성전자 / 005930 / AAPL")
            st.divider()
            st.caption("자동 조회 실패 시 아래로 업로드")
            uploaded = st.file_uploader("엑셀/CSV 업로드", type=["xlsx", "xls", "csv"])
            run = st.form_submit_button("분석 실행", use_container_width=True)

    if not run:
        st.info("좌측에서 종목을 입력하고 '분석 실행'을 누르세요.")
        return

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
            df, source = fetch(symbol, PERIOD_DAYS, get_cache())
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
    analyzed_at = now.strftime("%Y-%m-%d %H:%M:%S")
    chart_title = symbol.strip() or (uploaded.name if uploaded else "")

    # ── 섹션 1: 일봉 분석 ────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 2])
    with col1:
        render_signal_card(signal, source, analyzed_at)
        render_reasons_table(signal)
    with col2:
        st.plotly_chart(build_chart(enriched, chart_title), use_container_width=True)

    # ── 섹션 2: 15분봉 단기 분석 ─────────────────────────────────────────────
    if uploaded is not None or not symbol.strip():
        return  # 업로드 모드는 15분봉 스킵

    st.divider()
    st.markdown(
        '<div style="font-size:16px;font-weight:600;color:#1d1d1f;'
        'letter-spacing:-0.2px;margin-bottom:12px;'
        'font-family:system-ui,-apple-system,sans-serif;">'
        '📊 15분봉 단기 분석</div>',
        unsafe_allow_html=True,
    )

    market = detect_market(symbol.strip())
    with st.spinner("15분봉 데이터 조회 중…"):
        df_15m, err_15m = fetch_15min(symbol.strip(), market, days=5)

    col3, col4 = st.columns([1, 2])

    if df_15m.empty:
        with col3:
            st.markdown(
                '<div style="border:1px dashed #e0e0e0;border-radius:14px;'
                'padding:20px 18px;text-align:center;'
                'font-family:system-ui,-apple-system,sans-serif;">'
                '<div style="font-size:11px;font-weight:600;color:#aaa;'
                'letter-spacing:0.6px;text-transform:uppercase;margin-bottom:6px;">'
                '15분봉 단기 신호</div>'
                '<div style="font-size:13px;color:#bbb;">'
                '⚠️ 15분봉 데이터를 가져올 수 없습니다'
                '</div></div>',
                unsafe_allow_html=True,
            )
        with col4:
            st.warning("15분봉 데이터를 불러오지 못했습니다.")
            if err_15m:
                with st.expander("🔍 오류 상세 (진단용)", expanded=True):
                    st.code(err_15m, language=None)
    else:
        enriched_15m = compute_all(df_15m)
        signal_15m = generate_intraday_signal(enriched_15m)
        with col3:
            render_intraday_panel(signal_15m)
        with col4:
            st.plotly_chart(
                build_intraday_chart(enriched_15m, chart_title),
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
