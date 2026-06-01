"""최근 분기 실적 / 주요 재무지표 조회.

우선순위:
  KR: Naver Finance itemSummary (PER·PBR·EPS·배당·시총)
      → Yahoo Finance quoteSummary (분기 실적, crumb 인증)
  US: Yahoo Finance quoteSummary (crumb 인증)
"""
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

_HEADERS_YF = {"User-Agent": _UA, "Accept": "application/json"}
_HEADERS_NAVER = {
    "User-Agent": _UA,
    "Referer": "https://finance.naver.com",
    "Accept": "application/json, text/plain, */*",
}

_YF_SUMMARY_URLS = [
    "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}",
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}",
]
_YF_CRUMB_URLS = [
    "https://query1.finance.yahoo.com/v1/test/getcrumb",
    "https://query2.finance.yahoo.com/v1/test/getcrumb",
]
_YF_MODULES = "incomeStatementHistoryQuarterly,defaultKeyStatistics,price"


# ── 공통 유틸 ─────────────────────────────────────────────────────────────────

def _resolve_kr_code(symbol: str) -> str:
    """한글명 / 부분명 → 6자리 종목코드."""
    if symbol.isdigit():
        return symbol
    try:
        import FinanceDataReader as fdr
        listing = fdr.StockListing("KRX")
        matched = listing[listing["Name"] == symbol]
        if not matched.empty:
            return str(matched.iloc[0]["Code"])
        matched = listing[listing["Name"].str.contains(symbol, na=False)]
        if not matched.empty:
            matched = matched.copy()
            matched["_len"] = matched["Name"].str.len()
            return str(matched.sort_values("_len").iloc[0]["Code"])
    except Exception:
        pass
    return symbol


def _fmt_amount(val, currency: str) -> str:
    if val is None:
        return "—"
    if currency == "KRW":
        t = val / 1e12
        return f"{t:.1f}조" if abs(t) >= 1 else f"{val/1e8:.0f}억"
    b = val / 1e9
    return f"${b:.1f}B" if abs(b) >= 1 else f"${val/1e6:.0f}M"


# ── Naver Finance (KR 전용) ───────────────────────────────────────────────────

def _fetch_naver_kr(code: str) -> tuple[dict, str]:
    """
    Naver Finance itemSummary API로 주요 재무지표 조회.
    반환: (result_dict, error_msg)
    """
    url = f"https://api.finance.naver.com/service/itemSummary.naver?itemCode={code}"
    try:
        resp = requests.get(url, headers=_HEADERS_NAVER, timeout=10, verify=False)
        resp.raise_for_status()
        d = resp.json()
    except Exception as e:
        return {}, f"Naver itemSummary: {type(e).__name__}: {e}"

    def _v(key: str) -> str | None:
        v = d.get(key)
        return str(v).strip() if v else None

    def _fmt_ratio(v) -> str:
        try:
            return f"{float(v):.2f}배" if v else "—"
        except Exception:
            return str(v)

    per = _fmt_ratio(_v("per"))
    pbr = _fmt_ratio(_v("pbr"))

    # 추가 지표
    extras: list[dict] = []
    for label, key, suffix in [
        ("EPS",    "eps",           "원"),
        ("BPS",    "bps",           "원"),
        ("배당률",  "dividendRatio", "%"),
    ]:
        v = _v(key)
        if v:
            try:
                fv = float(v.replace(",", ""))
                val_str = f"{fv:,.0f}{suffix}" if suffix == "원" else f"{fv:.2f}{suffix}"
            except Exception:
                val_str = v + suffix
            extras.append({"항목": label, "값": val_str})

    # 시가총액 (억원 단위로 오는 경우)
    mc = _v("marketCap")
    if mc:
        try:
            mc_v = float(mc.replace(",", ""))
            mc_str = f"{mc_v/10000:.1f}조" if mc_v >= 10000 else f"{mc_v:.0f}억"
            extras.append({"항목": "시가총액", "값": mc_str})
        except Exception:
            pass

    if per == "—" and pbr == "—" and not extras:
        return {}, "Naver: 유효 데이터 없음"

    return {
        "quarters":  [],   # Naver itemSummary는 분기 실적 없음
        "per":       per,
        "pbr":       pbr,
        "extras":    extras,
        "currency":  "KRW",
        "source":    "Naver Finance",
        "yf_symbol": f"{code}.KS",
    }, ""


# ── Yahoo Finance (KR·US) ─────────────────────────────────────────────────────

def _get_yf_session() -> tuple[requests.Session, str]:
    """Yahoo Finance 세션 + crumb 토큰 취득."""
    session = requests.Session()
    session.headers.update(_HEADERS_YF)
    try:
        session.get("https://fc.yahoo.com/", timeout=8, verify=False)
    except Exception:
        pass
    crumb = ""
    for url in _YF_CRUMB_URLS:
        try:
            r = session.get(url, timeout=8, verify=False)
            if r.status_code == 200 and r.text.strip():
                crumb = r.text.strip()
                break
        except Exception:
            continue
    return session, crumb


def _fetch_yahoo(yf_sym: str, session: requests.Session, crumb: str) -> tuple[dict, str]:
    """Yahoo Finance quoteSummary로 분기 실적 조회."""
    params = {"modules": _YF_MODULES}
    if crumb:
        params["crumb"] = crumb

    for url_tpl in _YF_SUMMARY_URLS:
        url = url_tpl.format(sym=yf_sym)
        try:
            resp = session.get(url, params=params, timeout=12, verify=False)
            resp.raise_for_status()
            data = resp.json()
            qs = data.get("quoteSummary") or {}
            if qs.get("error"):
                continue
            result = qs.get("result") or []
            if not result:
                continue

            r = result[0]
            currency = (r.get("price") or {}).get("currency") or "USD"

            ish = ((r.get("incomeStatementHistoryQuarterly") or {})
                   .get("incomeStatementHistory") or [])
            quarters = []
            for item in ish[:4]:
                ed = item.get("endDate") or {}
                end_raw = ed.get("raw") if isinstance(ed, dict) else None
                try:
                    period = datetime.fromtimestamp(end_raw).strftime("%Y.%m") if end_raw else "?"
                except Exception:
                    period = "?"

                def _r(key, _i=item):
                    v = _i.get(key)
                    return v.get("raw") if isinstance(v, dict) else None

                quarters.append({
                    "기간":    period,
                    "매출":    _fmt_amount(_r("totalRevenue"),    currency),
                    "영업이익": _fmt_amount(_r("operatingIncome"), currency),
                    "순이익":   _fmt_amount(_r("netIncome"),       currency),
                })

            if not quarters:
                continue

            ks = r.get("defaultKeyStatistics") or {}

            def _ks(key):
                v = ks.get(key)
                return v.get("raw") if isinstance(v, dict) else v

            per_r = _ks("trailingPE")
            pbr_r = _ks("priceToBook")

            return {
                "quarters":  quarters,
                "per":       f"{per_r:.1f}배" if per_r else "—",
                "pbr":       f"{pbr_r:.2f}배" if pbr_r else "—",
                "extras":    [],
                "currency":  currency,
                "source":    "Yahoo Finance",
                "yf_symbol": yf_sym,
            }, ""

        except Exception as e:
            pass  # 다음 URL 시도

    return {}, f"Yahoo({yf_sym}): 분기 실적 없음"


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def fetch_financials(symbol: str, market: str) -> tuple[dict, str]:
    """
    주요 재무지표 + 분기 실적 조회.
    Returns: (result_dict, error_msg)

    result_dict:
    {
        "quarters":  [{"기간":..., "매출":..., "영업이익":..., "순이익":...}, ...],
        "extras":    [{"항목":..., "값":...}, ...],   # Naver 추가 지표
        "per":  "12.5배",
        "pbr":  "1.03배",
        "currency":  "KRW",
        "source":    "Naver Finance" | "Yahoo Finance",
        "yf_symbol": "005930.KS",
    }
    """
    errors: list[str] = []

    if market == "KR":
        code = _resolve_kr_code(symbol)

        # 1차: Naver Finance (PER·PBR·EPS·배당·시총)
        fin, err = _fetch_naver_kr(code)
        if fin:
            # 2차(병행): Yahoo Finance로 분기 실적 추가 시도
            try:
                session, crumb = _get_yf_session()
                for suffix in [".KS", ".KQ"]:
                    yf_fin, _ = _fetch_yahoo(f"{code}{suffix}", session, crumb)
                    if yf_fin.get("quarters"):
                        fin["quarters"] = yf_fin["quarters"]
                        fin["source"] = "Naver + Yahoo Finance"
                        break
            except Exception:
                pass
            return fin, ""
        errors.append(err)

    # US or KR Naver 실패 → Yahoo Finance
    session, crumb = _get_yf_session()
    if market == "KR":
        code = _resolve_kr_code(symbol)
        yf_syms = [f"{code}.KS", f"{code}.KQ"]
    else:
        yf_syms = [symbol.upper()]

    for yf_sym in yf_syms:
        fin, err = _fetch_yahoo(yf_sym, session, crumb)
        if fin:
            return fin, ""
        errors.append(err)

    return {}, " | ".join(errors)
