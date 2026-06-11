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
from core.signals import generate_signal, generate_intraday_signal, is_overheated
from core.market_sentiment import (
    fetch_10y_yield, fetch_fear_greed, fetch_index_brief, rating_ko,
)
from core.regime import WEIGHTED_REGIMES, detect_regime
from core.risk import compute_risk_levels, evaluate_position, trailing_stop_from_df
from core.backtest import run_backtest
from core.screener import scan_symbols
from core.context import sentiment_context, valuation_warning
from core.auth import verify_password
from core.portfolio import PortfolioStore
from core.dashboard import analyze_positions, summarize
from ui.chart import build_chart, build_intraday_chart
from ui.panels import (
    render_signal_card, render_reasons_table, render_intraday_panel,
    render_entry_point_card, render_risk_card, render_regime_badge,
    render_backtest_section, render_screener_table, render_position_card,
    render_portfolio_summary, render_portfolio_table,
)


def _parse_entry_price(raw: str) -> float:
    """매수가 입력 파싱: '298,500' → 298500.0. 비어있거나 무효면 0."""
    try:
        value = float(raw.replace(",", "").strip())
        return value if value > 0 else 0.0
    except (ValueError, AttributeError):
        return 0.0

_MAX_SCREENER_SYMBOLS = 20

# override=True: 앱 실행 중 .env를 수정해도 새로고침 시 즉시 반영
load_dotenv(override=True)

st.set_page_config(
    page_title="차트 분석기",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

CACHE_PATH = os.path.join(os.path.dirname(__file__), "data", "cache.db")
PORTFOLIO_DB_PATH = os.path.join(os.path.dirname(__file__), "data", "portfolio.db")
PERIOD_DAYS = 190  # 6개월 고정


@st.cache_resource
def get_cache() -> OhlcvCache:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    return OhlcvCache(CACHE_PATH)


@st.cache_resource
def get_portfolio() -> PortfolioStore:
    os.makedirs(os.path.dirname(PORTFOLIO_DB_PATH), exist_ok=True)
    return PortfolioStore(PORTFOLIO_DB_PATH)


@st.cache_data(ttl=300)
def get_market_sentiment() -> tuple[dict, dict]:
    """10Y 국채금리 + CNN F&G (5분 캐시)."""
    return fetch_10y_yield(), fetch_fear_greed()


@st.cache_data(ttl=300)
def get_index_briefs() -> list[dict]:
    """KOSPI · NASDAQ 지수 간이 분석 (5분 캐시)."""
    return [
        fetch_index_brief("^KS11", "KOSPI"),
        fetch_index_brief("^IXIC", "NASDAQ"),
    ]


@st.cache_data(ttl=3600)
def get_financials(symbol: str, market: str) -> tuple[dict, list]:
    """재무 데이터 1시간 캐시. (dict, [error_msgs]) 반환."""
    return fetch_financials(symbol, market)



_OG_META = """
<meta property="og:title" content="매매타점 차트분석기" />
<meta property="og:description" content="펭귄맨의 투자비법 노하우 Made by. Penguin" />
<meta property="og:image" content="https://raw.githubusercontent.com/SeokwonChoi0627/chart-analyzer/master/assets/og_preview.png" />
<meta property="og:image:width" content="1456" />
<meta property="og:image:height" content="816" />
<meta property="og:type" content="website" />
<meta property="og:locale" content="ko_KR" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="매매타점 차트분석기" />
<meta name="twitter:description" content="펭귄맨의 투자비법 노하우 Made by. Penguin" />
<meta name="twitter:image" content="https://raw.githubusercontent.com/SeokwonChoi0627/chart-analyzer/master/assets/og_preview.png" />
"""

_CHART_CONFIG = {
    "scrollZoom": False,       # 스크롤 줌 비활성화
    "doubleClick": False,      # 더블클릭 리셋 비활성화
    "displayModeBar": False,   # 상단 툴바 숨김
    "staticPlot": False,       # hover 툴팁은 유지
}

_CSS = """
<style>
/* ── 전체 폰트: SF Pro 대체 스택 ── */
html, body, [class*="css"] {
    font-family: system-ui, -apple-system, BlinkMacSystemFont,
                 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    color: #1d1d1f;
}

/* ── 종목명+시각 헤더 fixed 고정 ── */
.sticky-header {
    position: fixed;
    top: 0;
    left: 320px;
    right: 0;
    z-index: 999;
    background: #ffffff;
    padding: 10px 2rem 8px;
    border-bottom: 1px solid #e5e5ea;
}
div[data-testid="stMainBlockContainer"] {
    padding-top: 68px !important;
}

/* ── 사이드바: 배경 + 우측 테두리 ── */
section[data-testid="stSidebar"] {
    background-color: #ebebf0 !important;
    border-right: 1px solid #d1d1d6 !important;
}
section[data-testid="stSidebar"] * {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── PC: 사이드바 항상 표시 ── */
@media (min-width: 769px) {
    section[data-testid="stSidebar"] {
        transform: none !important;
        min-width: 320px !important;
        width: 320px !important;
    }
    div[data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }
}

/* ── 모바일 전용 ── */
@media (max-width: 768px) {
    /* 사이드바 완전 숨김 */
    section[data-testid="stSidebar"],
    div[data-testid="stSidebarCollapseButton"],
    button[data-testid="collapsedControl"] {
        display: none !important;
    }
    /* 헤더 left 0 */
    .sticky-header {
        left: 0 !important;
        padding: 8px 16px 6px !important;
    }
    /* 본문 여백 조정 */
    div[data-testid="stMainBlockContainer"] {
        padding-top: 56px !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
    }
    /* 모바일 검색 폼 표시 */
    .mobile-search { display: block !important; }
}

/* 데스크톱: 모바일 검색 폼만 숨김 — 로그인 폼 등 다른 main 폼은 표시 */
@media (min-width: 769px) {
    div[data-testid="stMainBlockContainer"] .st-key-mobile_form {
        display: none !important;
    }
}

/* ── 사이드바 모드 선택: 버튼 스타일 + 호버 글로우 ── */
section[data-testid="stSidebar"] div[role="radiogroup"] {
    flex-direction: column;
    gap: 8px;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label {
    background: #ffffff;
    border: 1px solid #d1d1d6;
    border-radius: 12px;
    padding: 11px 16px !important;
    margin: 0 !important;
    width: 100%;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease,
                box-shadow 0.15s ease, transform 0.1s ease;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    border-color: #0066cc;
    background: #f0f6ff;
    box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.18),
                0 2px 12px rgba(0, 102, 204, 0.15);
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:active {
    transform: scale(0.97);
}
/* 라디오 동그라미 숨김 */
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-of-type {
    display: none;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label p {
    font-size: 14px;
    color: #1d1d1f;
}
/* 선택된 모드 버튼 강조 */
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
    background: #0066cc;
    border-color: #0066cc;
    box-shadow: 0 2px 10px rgba(0, 102, 204, 0.3);
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
    color: #ffffff;
    font-weight: 600;
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
    st.markdown(_OG_META, unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)

    from datetime import timezone, timedelta
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)

    # ── 사이드바 (데스크톱) ───────────────────────────────────────────────────
    with st.sidebar:
        st.title("차트 분석기")
        st.markdown('<div style="margin-bottom:28px;"></div>', unsafe_allow_html=True)
        mode = st.radio(
            "분석 모드",
            ["단일종목분석", "여러종목분석", "포트폴리오"],
            label_visibility="collapsed",
        )
        symbol_sb, run_sb = "", False
        watchlist_raw, run_screener = "", False
        entry_raw = ""
        if mode == "단일종목분석":
            with st.form("analysis_form"):
                symbol_sb = st.text_input("종목", placeholder="삼성전자 / 005930 / AAPL")
                entry_raw = st.text_input(
                    "내 매수가 (보유 시)",
                    placeholder="예: 298500 — 미보유 시 비워두세요",
                )
                run_sb = st.form_submit_button("분석 실행", use_container_width=True)
        elif mode == "여러종목분석":
            with st.form("screener_form"):
                watchlist_raw = st.text_area(
                    "관심종목 (줄바꿈 또는 쉼표 구분)",
                    placeholder="삼성전자\nSK하이닉스\nAAPL\nTSLA",
                    height=140,
                )
                run_screener = st.form_submit_button("일괄 스캔", use_container_width=True)
        elif st.session_state.get("pf_authed"):
            # ── 내 포트폴리오: 종목 등록/삭제 (로그인 후) ──────────────────
            with st.form("pf_add_form", clear_on_submit=True):
                pf_symbol = st.text_input("종목", placeholder="삼성전자 / AAPL")
                pf_entry = st.text_input("매수가", placeholder="예: 270000")
                pf_qty = st.text_input("수량 (선택)", placeholder="예: 10 — 미입력 시 수익률만")
                pf_add = st.form_submit_button("보유 종목 등록", use_container_width=True)
            if pf_add:
                try:
                    qty_val = float(pf_qty.replace(",", "").strip() or 0)
                    get_portfolio().add(pf_symbol, _parse_entry_price(pf_entry), qty_val)
                    st.success(f"'{pf_symbol.strip()}' 등록 완료")
                except ValueError as e:
                    st.error(f"등록 실패: {e}")
            pf_positions = get_portfolio().list_positions()
            if pf_positions:
                pf_labels = {
                    f"{p['symbol']} @ {p['entry_price']:,.0f}"
                    + (f" ×{p['quantity']:g}" if p["quantity"] else "")
                    + f"  (#{p['id']})": p["id"]
                    for p in pf_positions
                }
                pf_sel = st.selectbox("등록 종목", list(pf_labels.keys()))
                if st.button("선택 종목 삭제", use_container_width=True):
                    get_portfolio().remove(pf_labels[pf_sel])
                    st.rerun()
            if st.button("로그아웃", use_container_width=True):
                st.session_state["pf_authed"] = False
                st.rerun()
        else:
            st.caption("메인 화면에서 로그인하면 종목을 등록할 수 있습니다.")
        # ── 시장 심리 지표 ───────────────────────────────────────────────
        st.markdown("---")
        st.markdown(
            '<div style="font-size:12px;font-weight:600;color:#888;'
            'letter-spacing:0.4px;text-transform:uppercase;margin-bottom:6px;">'
            '시장 심리</div>',
            unsafe_allow_html=True,
        )
        tnx, fg = get_market_sentiment()
        if tnx.get("value") is not None:
            chg_tnx = tnx.get("change", 0.0)
            chg_color_tnx = "#c62828" if chg_tnx > 0 else "#0a8a0a"
            st.markdown(
                f'<div style="margin-bottom:6px;">'
                f'<span style="font-size:11px;color:#aaa;">미 10년물 국채금리</span><br>'
                f'<span style="font-size:18px;font-weight:700;color:#1d1d1f;">{tnx["value"]}%</span>'
                f'<span style="font-size:12px;color:{chg_color_tnx};margin-left:6px;">{chg_tnx:+.3f}%p</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("10년물 금리 조회 실패")
        if fg.get("score") is not None:
            score_fg = fg["score"]
            if score_fg <= 25:
                bar_color = "#c62828"
            elif score_fg <= 45:
                bar_color = "#e65100"
            elif score_fg <= 55:
                bar_color = "#888"
            elif score_fg <= 75:
                bar_color = "#2e7d32"
            else:
                bar_color = "#0a8a0a"
            st.markdown(
                f'<div>'
                f'<span style="font-size:11px;color:#aaa;">CNN 공포·탐욕 지수</span><br>'
                f'<span style="font-size:18px;font-weight:700;color:{bar_color};">{score_fg:.0f}</span>'
                f'<span style="font-size:12px;color:{bar_color};margin-left:6px;">{rating_ko(fg.get("rating",""))}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("공포·탐욕 지수 조회 실패")

        # ── 주요 지수 브리프 (KOSPI · NASDAQ) ────────────────────────────
        st.markdown("---")
        st.markdown(
            '<div style="font-size:12px;font-weight:600;color:#888;'
            'letter-spacing:0.4px;text-transform:uppercase;margin-bottom:6px;">'
            '주요 지수</div>',
            unsafe_allow_html=True,
        )
        for brief in get_index_briefs():
            if brief.get("value") is None:
                st.caption(f"{brief['name']} 조회 실패")
                continue
            chg = brief["change_pct"]
            chg_color = "#0a8a0a" if chg >= 0 else "#c62828"
            note_color = "#2e7d32" if brief["above_sma20"] else "#c62828"
            st.markdown(
                f'<div style="margin-bottom:10px;">'
                f'<span style="font-size:11px;color:#aaa;">{brief["name"]}</span><br>'
                f'<span style="font-size:18px;font-weight:700;color:#1d1d1f;">'
                f'{brief["value"]:,.2f}</span>'
                f'<span style="font-size:12px;font-weight:600;color:{chg_color};'
                f'margin-left:6px;">{chg:+.2f}%</span><br>'
                f'<span style="font-size:11px;font-weight:600;color:{note_color};">'
                f'{brief["note"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div style="font-size:14px;color:#aaa;text-align:left;margin-top:8px;">'
            'made by penguin</div>',
            unsafe_allow_html=True,
        )

    # ── 내 포트폴리오 모드 ───────────────────────────────────────────────────
    if mode == "포트폴리오":
        st.markdown(
            '<div style="font-size:22px;font-weight:700;color:#1d1d1f;'
            'letter-spacing:-0.4px;margin:8px 0 14px;'
            'font-family:system-ui,-apple-system,sans-serif;">내 포트폴리오</div>',
            unsafe_allow_html=True,
        )

        expected_pw = os.getenv("PORTFOLIO_PASSWORD", "")
        if not expected_pw:
            try:
                expected_pw = st.secrets.get("PORTFOLIO_PASSWORD", "")
            except Exception:
                expected_pw = ""
        if not expected_pw:
            st.error(
                "포트폴리오 비밀번호가 설정되지 않았습니다.\n\n"
                "**로컬 실행 시:** `C:\\AI\\chart_analyzer\\.env` 파일에 추가하세요:\n\n"
                "`PORTFOLIO_PASSWORD=원하는비밀번호`\n\n"
                "**Streamlit Cloud 배포 시:** 앱 대시보드 → Settings → Secrets에 추가하세요:\n\n"
                "`PORTFOLIO_PASSWORD = \"원하는비밀번호\"`"
            )
            return

        if not st.session_state.get("pf_authed"):
            with st.form("pf_login_form"):
                pw_input = st.text_input("비밀번호", type="password",
                                          placeholder="포트폴리오 비밀번호 입력")
                login = st.form_submit_button("로그인", use_container_width=True)
            if login:
                if verify_password(pw_input, expected_pw):
                    st.session_state["pf_authed"] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
            return

        positions = get_portfolio().list_positions()
        if not positions:
            st.info("사이드바에서 보유 종목(종목·매수가·수량)을 등록하세요. "
                    "등록 즉시 이 화면에서 전체 포지션을 한눈에 분석합니다.")
            return

        cache = get_cache()
        with st.spinner(f"{len(positions)}개 포지션 분석 중… (종목당 1~3초)"):
            rows = analyze_positions(
                positions, fetch_fn=lambda s: fetch(s, PERIOD_DAYS, cache))

        render_portfolio_summary(summarize(rows))
        render_portfolio_table(rows)
        st.caption(
            "위험한 포지션(손절 이탈)부터 정렬됩니다. "
            "권장 청산선 = 매수가 기준 고정 손절(−2×ATR)과 트레일링 스탑(최근 고점−3×ATR) 중 높은 쪽. "
            "매수추천도는 일봉 종합 신호(국면 가중) 기준입니다."
        )
        return

    # ── 관심종목 스크리너 모드 ────────────────────────────────────────────────
    if mode == "여러종목분석":
        st.markdown(
            '<div style="font-size:22px;font-weight:700;color:#1d1d1f;'
            'letter-spacing:-0.4px;margin:8px 0 14px;'
            'font-family:system-ui,-apple-system,sans-serif;">관심종목 스크리너</div>',
            unsafe_allow_html=True,
        )
        if not run_screener:
            st.info("사이드바에 관심종목을 입력하고 '일괄 스캔'을 누르세요. 점수순으로 정렬해 보여드립니다.")
            return

        tokens = [t for line in watchlist_raw.splitlines() for t in line.split(",")]
        symbols = [t.strip() for t in tokens if t.strip()][:_MAX_SCREENER_SYMBOLS]
        if not symbols:
            st.warning("종목을 한 개 이상 입력하세요.")
            return

        cache = get_cache()

        def _fetch_for_scan(sym: str):
            return fetch(sym, PERIOD_DAYS, cache)

        with st.spinner(f"{len(symbols)}개 종목 스캔 중… (종목당 1~3초)"):
            results = scan_symbols(symbols, fetch_fn=_fetch_for_scan)
        render_screener_table(results)
        st.caption("점수는 일봉 종합 신호(국면 가중 적용) 기준입니다. 상세 분석은 단일 종목 모드를 이용하세요.")
        return

    # ── 모바일 상단 검색 폼 ───────────────────────────────────────────────────
    st.markdown('<div class="mobile-search">', unsafe_allow_html=True)
    with st.form("mobile_form"):
        st.markdown(
            '<div style="font-size:18px;font-weight:700;color:#1d1d1f;'
            'letter-spacing:-0.4px;margin-bottom:10px;">차트 분석기</div>',
            unsafe_allow_html=True,
        )
        symbol_mb = st.text_input("종목", placeholder="삼성전자 / AAPL / 애플",
                                   label_visibility="collapsed", key="mobile_symbol")
        run_mb = st.form_submit_button("분석 실행", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # 어느 폼이 실행됐는지 확인
    run    = run_sb or run_mb
    symbol = (symbol_sb if run_sb else symbol_mb) if run else ""

    if not run:
        st.info("종목을 입력하고 '분석 실행'을 누르세요.")
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
    regime_info = detect_regime(enriched)
    active_regime = regime_info["regime"] if regime_info["regime"] in WEIGHTED_REGIMES else None
    signal     = generate_signal(enriched, regime=active_regime)
    _atr_series = enriched.get("atr", pd.Series(dtype=float))
    daily_atr = (
        float(_atr_series.iloc[-1])
        if hasattr(_atr_series, "iloc") and len(_atr_series) and pd.notna(_atr_series.iloc[-1])
        else 0.0
    )
    analyzed_at = now.strftime("%Y-%m-%d %H:%M:%S")
    chart_title = f"{symbol.strip().upper()} - 일봉"

    # ── 재무 데이터 (한 번만 조회) ───────────────────────────────────────────
    with st.spinner("재무 데이터 조회 중…"):
        fin_data, fin_errors = get_financials(symbol.strip(), market)
    company_name = fin_data.get("company_name", "") if fin_data else ""

    # ── 사이드바 하단: 재무 정보 + 과열 필터 ────────────────────────────────────
    with st.sidebar:
        _render_financials(fin_data, fin_errors)
        st.markdown("---")
        st.markdown(
            '<div style="font-size:12px;font-weight:600;color:#888;'
            'letter-spacing:0.4px;text-transform:uppercase;margin-bottom:6px;">'
            '급등 과열 필터</div>',
            unsafe_allow_html=True,
        )
        overheat_n = st.slider("기준 봉 수", min_value=3, max_value=30, value=10, step=1)
        overheat_thr = st.slider("과열 임계값 (%)", min_value=5, max_value=50, value=15, step=1)

        # ── 일봉 과열 상태 표시 ─────────────────────────────────────────
        daily_overheated = is_overheated(enriched, n=overheat_n, threshold=overheat_thr / 100)
        if daily_overheated:
            st.markdown(
                f'<div style="margin-top:8px;padding:8px 12px;border-radius:10px;'
                f'background:#fff0f0;border:1px solid #ffcccc;">'
                f'<span style="font-size:12px;font-weight:700;color:#c62828;">🔥 일봉 과열 감지</span><br>'
                f'<span style="font-size:11px;color:#c62828;">'
                f'최근 {overheat_n}봉 누적 {overheat_thr}% 초과 — 신규 매수 주의</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div style="margin-top:8px;padding:8px 12px;border-radius:10px;'
                f'background:#f0fff4;border:1px solid #b2dfdb;">'
                f'<span style="font-size:12px;font-weight:700;color:#2e7d32;">✅ 일봉 정상 구간</span><br>'
                f'<span style="font-size:11px;color:#2e7d32;">'
                f'최근 {overheat_n}봉 누적 {overheat_thr}% 미만</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
    ticker_upper = symbol.strip().upper()
    kst_time = now.strftime("%H:%M")
    kst_date = now.strftime("%Y.%m.%d")

    # ── 현재가 (마지막 종가) ──────────────────────────────────────────────────
    last_close = enriched["close"].iloc[-1] if not enriched.empty else None
    prev_close = enriched["close"].iloc[-2] if len(enriched) >= 2 else None
    if last_close is not None:
        if market == "KR":
            price_str = f"{last_close:,.0f}원"
        else:
            price_str = f"${last_close:,.2f}"
        if prev_close is not None:
            chg = (last_close - prev_close) / prev_close * 100
            chg_color = "#0a8a0a" if chg >= 0 else "#c62828"
            chg_str = f"{chg:+.2f}%"
        else:
            chg_color = "#888"
            chg_str = ""
    else:
        price_str = ""
        chg_str   = ""
        chg_color = "#888"

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

    price_block = (
        f'<div style="text-align:right;margin-right:24px;">'
        f'<div style="font-size:22px;font-weight:700;color:#1d1d1f;'
        f'letter-spacing:-0.4px;">{price_str}</div>'
        f'<div style="font-size:12px;font-weight:600;color:{chg_color};'
        f'margin-top:2px;">{chg_str}</div>'
        f'</div>'
    ) if price_str else ""

    header_html = (
        f'<div class="sticky-header" style="display:flex;justify-content:space-between;'
        f'align-items:center;font-family:system-ui,-apple-system,sans-serif;">'
        f'<div>{name_block}</div>'
        f'<div style="display:flex;align-items:center;">'
        f'{price_block}'
        f'<div style="text-align:right;">'
        f'<div style="font-size:22px;font-weight:600;color:#1d1d1f;letter-spacing:-0.3px;">{kst_time}</div>'
        f'<div style="font-size:11px;color:#aaa;margin-top:2px;">KST &nbsp;{kst_date}</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # ── 15분봉 데이터 미리 조회 (타점 카드를 최상단에 표시하기 위해) ──────────
    with st.spinner("데이터 조회 중…"):
        df_15m, err_15m = fetch_15min(symbol.strip(), market, days=5)

    enriched_15m = None
    signal_15m   = {"score": 0.0, "verdict": "데이터 부족", "reasons": [], "last_time": ""}
    if not df_15m.empty:
        enriched_15m = compute_all(df_15m)
        signal_15m   = generate_intraday_signal(
            enriched_15m,
            overheat_n=overheat_n,
            overheat_threshold=overheat_thr / 100,
            daily_atr=daily_atr,
        )

    if signal_15m.get("overheated"):
        st.warning(
            f"⚠️ 단기 과열 구간 — 매수 신호 억제됨 "
            f"(최근 {overheat_n}봉 누적 상승 {overheat_thr}% 초과)"
        )
    if signal_15m.get("structural_break"):
        st.warning("⚠️ 추세 이탈 감지 — ATR 기준 낙폭 초과 (눌림목보다 반전 가능성)")

    # ── 복합 타점 카드 (최상단) ───────────────────────────────────────────────
    render_entry_point_card(
        daily_score=signal["score"],
        intraday_score=signal_15m.get("score", 0.0),
        fin=fin_data,
    )

    # ── 시장 심리 · 밸류에이션 교차 검증 코멘트 ──────────────────────────────
    senti_ctx = sentiment_context(fg.get("score"), signal["score"])
    if senti_ctx:
        if senti_ctx["level"] == "기회":
            st.info(f"💡 {senti_ctx['message']}")
        else:
            st.warning(f"⚠️ {senti_ctx['message']}")
    val_warn = valuation_warning(fin_data, signal["verdict"])
    if val_warn:
        st.warning(f"⚠️ {val_warn}")

    # ── 시장 국면 배지 (ADX) ─────────────────────────────────────────────────
    render_regime_badge(regime_info)

    # ── 일봉 과열 상태 카드 (종합결론↔일봉 기준판정 사이) ────────────────────
    if daily_overheated:
        st.markdown(
            f'<div style="padding:14px 20px;border-radius:14px;margin-bottom:8px;'
            f'background:#fff0f0;border:1.5px solid #ffcccc;'
            f'font-family:system-ui,-apple-system,sans-serif;">'
            f'<span style="font-size:14px;font-weight:700;color:#c62828;">🔥 일봉 과열 감지</span>'
            f'<span style="font-size:13px;color:#c62828;margin-left:10px;">'
            f'최근 {overheat_n}봉 누적 {overheat_thr}% 초과 — 신규 매수 주의</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="padding:14px 20px;border-radius:14px;margin-bottom:8px;'
            f'background:#f0fff4;border:1.5px solid #b2dfdb;'
            f'font-family:system-ui,-apple-system,sans-serif;">'
            f'<span style="font-size:14px;font-weight:700;color:#2e7d32;">✅ 일봉 정상 구간</span>'
            f'<span style="font-size:13px;color:#2e7d32;margin-left:10px;">'
            f'최근 {overheat_n}봉 누적 {overheat_thr}% 미만</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── 섹션 1: 일봉 분석 ────────────────────────────────────────────────────
    col1, col2 = st.columns([1, 2])
    with col1:
        render_signal_card(signal, source, analyzed_at)
        if last_close is not None:
            entry_price = _parse_entry_price(entry_raw)
            if entry_price > 0:
                # 보유 포지션: 매수가 고정 손절/목표 + 트레일링 스탑 (매수 시점 이후 고점 기준)
                trailing = trailing_stop_from_df(enriched, entry=entry_price)
                pos = evaluate_position(
                    entry=entry_price, current=float(last_close),
                    atr=daily_atr, trailing_stop=trailing,
                )
                if pos:
                    render_position_card(pos, entry_price, float(last_close), market)
                else:
                    st.caption("입력한 매수가로 포지션을 평가할 수 없습니다. 매수가를 확인하세요.")
            else:
                # 미보유: 오늘 신규 진입 가정 기준선
                risk = compute_risk_levels(entry=float(last_close), atr=daily_atr)
                render_risk_card(risk, float(last_close), market)
        render_reasons_table(signal)
    with col2:
        st.plotly_chart(
            build_chart(enriched, chart_title),
            use_container_width=True,
            config=_CHART_CONFIG,
        )

    # ── 섹션 2: 15분봉 단기 분석 ─────────────────────────────────────────────
    st.divider()
    st.markdown(
        '<div style="font-size:16px;font-weight:600;color:#1d1d1f;'
        'letter-spacing:-0.2px;margin-bottom:12px;'
        'font-family:system-ui,-apple-system,sans-serif;">'
        '15분봉 단기 분석</div>',
        unsafe_allow_html=True,
    )

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
                '15분봉 데이터를 가져올 수 없습니다'
                '</div></div>',
                unsafe_allow_html=True,
            )
        with col4:
            st.warning("15분봉 데이터를 불러오지 못했습니다.")
            if err_15m:
                with st.expander("오류 상세", expanded=False):
                    st.code(err_15m, language=None)
    else:
        with col3:
            render_intraday_panel(signal_15m)
        with col4:
            st.plotly_chart(
                build_intraday_chart(enriched_15m, chart_title),
                use_container_width=True,
                config=_CHART_CONFIG,
            )

    # ── 섹션 3: 신호 백테스트 ────────────────────────────────────────────────
    st.divider()
    with st.expander("📊 신호 백테스트 — 이 종목에서 신호가 실제로 맞았는지 검증", expanded=False):
        with st.spinner("과거 구간 신호 성과 집계 중…"):
            bt = run_backtest(enriched)
        render_backtest_section(bt)


if __name__ == "__main__":
    main()
