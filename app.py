import os
from datetime import datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from core.cache import OhlcvCache
from core.data.orchestrator import fetch, DataUnavailableError
from core.data.intraday import fetch_15min
from core.data.financials import fetch_financials
from core.data.base import detect_market
from core.indicators import compute_all
from core.signals import generate_signal, generate_intraday_signal
from ui.chart import build_chart, build_intraday_chart
from ui.panels import render_signal_card, render_reasons_table, render_intraday_panel

load_dotenv()

st.set_page_config(
    page_title="차트 분석기",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "cache.db")
PERIOD_DAYS = 190  # 6개월 고정


@st.cache_resource
def get_cache() -> OhlcvCache:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    return OhlcvCache(CACHE_PATH)


@st.cache_data(ttl=3600)
def get_financials(symbol: str, market: str) -> tuple[dict, list]:
    """재무 데이터 1시간 캐시. (dict, [error_msgs]) 반환."""
    return fetch_financials(symbol, market)


_CSS = """
<style>
/* ── 전체 폰트: SF Pro 대체 스택 ── */
html, body, [class*="css"] {
    font-family: system-ui, -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    color: #1d1d1f;
}

/* ── 종목 헤더 fixed 고정 ── */
.sticky-header {
    position: fixed;
    top: 0;
    left: 280px;
    right: 0;
    z-index: 999;
    background: #ffffff;
    padding: 10px 2rem 8px;
    border-bottom: 1px solid #e5e5ea;
}

/* ── 고정 헤더 높이만큼 본문 여백 ── */
div[data-testid="stMainBlockContainer"] {
    padding-top: 72px !important;
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

/* ── Streamlit 상단 툴바 숨김 ── */
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
#MainMenu,
header[data-testid="stHeader"] {
    display: none !important;
    visibility: hidden !important;
}

/* ── 사이드바 항상 표시 고정 ── */
section[data-testid="stSidebar"] {
    transform: none !important;
    min-width: 280px !important;
    width: 280px !important;
}

/* ── 사이드바 내부 접기 버튼 숨김 ── */
div[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}

/* ── 메인 영역의 사이드바 열기 버튼 숨김 ── */
button[data-testid="collapsedControl"] {
    display: none !important;
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


def _section_title(text: str) -> None:
    st.markdown(
        f'<div style="font-size:10px;font-weight:600;color:#aaa;letter-spacing:0.6px;'
        f'text-transform:uppercase;margin:10px 0 4px;">{text}</div>',
        unsafe_allow_html=True,
    )


def _per_pbr_row(per: str, pbr: str) -> None:
    """PER / PBR을 잘림 없이 나란히 표시."""
    st.markdown(
        f'<div style="display:flex;gap:16px;margin:6px 0 10px;">'
        f'<div style="flex:1;">'
        f'<div style="font-size:11px;color:#aaa;font-weight:600;letter-spacing:0.4px;">PER</div>'
        f'<div style="font-size:20px;font-weight:700;color:#1d1d1f;letter-spacing:-0.3px;white-space:nowrap;">{per}</div>'
        f'</div>'
        f'<div style="flex:1;">'
        f'<div style="font-size:11px;color:#aaa;font-weight:600;letter-spacing:0.4px;">PBR</div>'
        f'<div style="font-size:20px;font-weight:700;color:#1d1d1f;letter-spacing:-0.3px;white-space:nowrap;">{pbr}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _kv_table(data: dict) -> None:
    """key-value dict를 2열 간결 테이블로 표시."""
    if not data:
        return
    rows = list(data.items())
    df = pd.DataFrame(rows, columns=["항목", "값"]).set_index("항목")
    st.dataframe(df, use_container_width=True)


def _render_financials(fin: dict, errors: list) -> None:
    """사이드바 하단 — 종합 재무정보 표시. 외부에서 fetch한 데이터를 받음."""
    st.divider()
    st.markdown(
        '<div style="font-size:12px;font-weight:600;color:#aaa;'
        'letter-spacing:0.5px;text-transform:uppercase;margin-bottom:6px;">'
        '재무 정보</div>',
        unsafe_allow_html=True,
    )

    if not fin:
        st.caption("재무 데이터를 불러올 수 없습니다.")
        if errors:
            with st.expander("🔍 오류 상세", expanded=False):
                for e in errors:
                    st.caption(e)
        return

    # ── 밸류에이션 ──────────────────────────────────────────────────────────────
    valuation = fin.get("valuation") or {}
    extras    = fin.get("extras", [])   # Naver 소스 폴백

    if valuation:
        _section_title("밸류에이션")
        per = valuation.get("PER(후행)") or fin.get("per", "—")
        pbr = valuation.get("PBR")       or fin.get("pbr", "—")
        _per_pbr_row(per, pbr)
        rest = {k: v for k, v in valuation.items()
                if k not in ("PER(후행)", "PBR") and v}
        _kv_table(rest)
    elif extras:
        per, pbr = fin.get("per", "—"), fin.get("pbr", "—")
        if per != "—" or pbr != "—":
            _per_pbr_row(per, pbr)
        df_ext = pd.DataFrame(extras).set_index("항목")
        st.dataframe(df_ext, use_container_width=True)
    else:
        per, pbr = fin.get("per", "—"), fin.get("pbr", "—")
        if per != "—" or pbr != "—":
            _per_pbr_row(per, pbr)

    # ── 수익성 ──────────────────────────────────────────────────────────────────
    profitability = fin.get("profitability") or {}
    if profitability:
        _section_title("수익성")
        _kv_table(profitability)

    # ── 시장 정보 ────────────────────────────────────────────────────────────────
    market_info = fin.get("market") or {}
    if market_info:
        _section_title("시장 정보")
        _kv_table(market_info)

    # ── 분기 실적 ────────────────────────────────────────────────────────────────
    quarters = fin.get("quarters", [])
    if quarters:
        _section_title("최근 분기 실적")
        df_q = pd.DataFrame(quarters)
        st.dataframe(df_q, hide_index=True, use_container_width=True)

    source = fin.get("source", "")
    if source:
        st.caption(f"출처: {source}")


def main():
    st.markdown(_CSS, unsafe_allow_html=True)

    from datetime import timezone, timedelta
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)

    # ── 사이드바: 입력 폼 ─────────────────────────────────────────────────────
    with st.sidebar:
        st.title("차트 분석기")
        st.markdown('<div style="margin-bottom:28px;"></div>', unsafe_allow_html=True)
        with st.form("analysis_form"):
            symbol = st.text_input("종목", placeholder="삼성전자 / 005930 / AAPL")
            run = st.form_submit_button("분석 실행", use_container_width=True)
        st.markdown(
            '<div style="font-size:14px;color:#aaa;text-align:left;margin-top:2px;">'
            'made by penguin</div>',
            unsafe_allow_html=True,
        )

    if not run:
        st.info("좌측에서 종목을 입력하고 '분석 실행'을 누르세요.")
        return

    if not symbol.strip():
        st.warning("종목을 입력하세요.")
        return

    # ── 일봉 데이터 조회 ──────────────────────────────────────────────────────
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

    market     = detect_market(symbol.strip())
    enriched   = compute_all(df)
    signal     = generate_signal(enriched)
    analyzed_at = now.strftime("%Y-%m-%d %H:%M:%S")
    chart_title = f"{symbol.strip().upper()} - 일봉"

    # ── 재무 데이터 (한 번만 조회) ───────────────────────────────────────────
    with st.spinner("재무 데이터 조회 중…"):
        fin_data, fin_errors = get_financials(symbol.strip(), market)
    company_name = fin_data.get("company_name", "") if fin_data else ""

    # ── 사이드바 하단: 재무 정보 ──────────────────────────────────────────────
    with st.sidebar:
        _render_financials(fin_data, fin_errors)
    ticker_upper = symbol.strip().upper()
    kst_time = now.strftime("%H:%M")
    kst_date = now.strftime("%Y.%m.%d")

    if company_name and company_name.upper() != ticker_upper:
        name_block = (
            f'<div style="font-size:26px;font-weight:700;color:#1d1d1f;'
            f'letter-spacing:-0.5px;line-height:1.15;">{company_name}</div>'
            f'<div style="font-size:14px;font-weight:500;color:#888;'
            f'margin-top:2px;letter-spacing:0.2px;">{ticker_upper}</div>'
        )
    else:
        name_block = (
            f'<div style="font-size:26px;font-weight:700;color:#1d1d1f;'
            f'letter-spacing:-0.5px;">{ticker_upper}</div>'
        )

    header_html = (
        f'<div class="sticky-header" style="display:flex;justify-content:space-between;'
        f'align-items:flex-start;font-family:system-ui,-apple-system,sans-serif;">'
        f'<div>{name_block}</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:22px;font-weight:600;color:#1d1d1f;letter-spacing:-0.3px;">{kst_time}</div>'
        f'<div style="font-size:11px;color:#aaa;margin-top:2px;">KST &nbsp;{kst_date}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # ── 섹션 1: 일봉 분석 ────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 2])
    with col1:
        render_signal_card(signal, source, analyzed_at)
        render_reasons_table(signal)
    with col2:
        st.plotly_chart(build_chart(enriched, chart_title), use_container_width=True)

    # ── 섹션 2: 15분봉 단기 분석 ─────────────────────────────────────────────
    st.divider()
    st.markdown(
        '<div style="font-size:16px;font-weight:600;color:#1d1d1f;'
        'letter-spacing:-0.2px;margin-bottom:12px;'
        'font-family:system-ui,-apple-system,sans-serif;">'
        '📊 15분봉 단기 분석</div>',
        unsafe_allow_html=True,
    )

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
                with st.expander("🔍 오류 상세 (진단용)", expanded=False):
                    st.code(err_15m, language=None)
    else:
        enriched_15m = compute_all(df_15m)
        signal_15m   = generate_intraday_signal(enriched_15m)
        with col3:
            render_intraday_panel(signal_15m)
        with col4:
            st.plotly_chart(
                build_intraday_chart(enriched_15m, chart_title),
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
