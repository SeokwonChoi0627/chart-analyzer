"""주요 재무지표 조회.

우선순위 (KR):
  1) Naver 모바일 API  m.stock.naver.com/api/stock/{code}/integration
  2) Naver itemSummary  api.finance.naver.com/service/itemSummary.naver
  3) Yahoo Finance quoteSummary  (분기 실적 추가 시도)

우선순위 (US):
  Yahoo Finance quoteSummary (crumb 인증)
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
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                  "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Referer": "https://m.stock.naver.com",
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
    if symbol.isdigit():
        return symbol
    try:
        import FinanceDataReader as fdr
        listing = fdr.StockListing("KRX")
        m = listing[listing["Name"] == symbol]
        if not m.empty:
            return str(m.iloc[0]["Code"])
        m = listing[listing["Name"].str.contains(symbol, na=False)]
        if not m.empty:
            m = m.copy(); m["_l"] = m["Name"].str.len()
            return str(m.sort_values("_l").iloc[0]["Code"])
    except Exception:
        pass
    return symbol


def _fmt_ratio(v) -> str:
    try:
        return f"{float(str(v).replace(',', '')):.2f}배" if v else "—"
    except Exception:
        return str(v) if v else "—"


def _fmt_amount(val, currency: str) -> str:
    if val is None:
        return "—"
    if currency == "KRW":
        t = val / 1e12
        return f"{t:.1f}조" if abs(t) >= 1 else f"{val/1e8:.0f}억"
    b = val / 1e9
    return f"${b:.1f}B" if abs(b) >= 1 else f"${val/1e6:.0f}M"


# ── Naver 모바일 API (KR 우선) ────────────────────────────────────────────────

def _fetch_naver_mobile(code: str) -> tuple[dict, str]:
    """Naver 모바일 /integration 엔드포인트로 PER·PBR·EPS·시총 등 조회."""
    url = f"https://m.stock.naver.com/api/stock/{code}/integration"
    try:
        resp = requests.get(url, headers=_HEADERS_NAVER, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {}, f"Naver모바일({url}): {type(e).__name__}: {e}"

    # totalInfos 배열에서 code → value 매핑
    infos = data.get("totalInfos") or []
    info_map: dict[str, str] = {}
    for item in infos:
        c = item.get("code") or item.get("name")
        v = item.get("value")
        if c and v:
            info_map[str(c)] = str(v)

    # 주요 필드 추출 (Naver 필드명 후보 복수로 시도)
    def _get(*keys) -> str | None:
        for k in keys:
            v = info_map.get(k)
            if v and v not in ("", "-", "N/A"):
                return v
        return None

    per_v = _get("per", "PER")
    pbr_v = _get("pbr", "PBR")
    eps_v = _get("eps", "EPS")
    bps_v = _get("bps", "BPS")
    div_v = _get("dividendYield", "dividendRatio", "배당수익률")
    cap_v = _get("marketValue", "시가총액")

    if not per_v and not pbr_v:
        return {}, (
            f"Naver모바일: per/pbr 없음. "
            f"사용 가능한 keys={list(info_map.keys())[:10]}"
        )

    extras: list[dict] = []
    for label, val in [("EPS", eps_v), ("BPS", bps_v), ("배당률", div_v), ("시총", cap_v)]:
        if val:
            extras.append({"항목": label, "값": val})

    return {
        "quarters":  [],
        "per":       _fmt_ratio(per_v),
        "pbr":       _fmt_ratio(pbr_v),
        "extras":    extras,
        "currency":  "KRW",
        "source":    "Naver Finance (모바일)",
        "yf_symbol": f"{code}.KS",
    }, ""


def _fetch_naver_summary(code: str) -> tuple[dict, str]:
    """Naver itemSummary API로 PER·PBR 조회 (레거시 폴백)."""
    url = f"https://api.finance.naver.com/service/itemSummary.naver?itemCode={code}"
    try:
        resp = requests.get(url, headers=_HEADERS_NAVER, timeout=10, verify=False)
        resp.raise_for_status()
        d = resp.json()
    except Exception as e:
        return {}, f"NaverSummary({url}): {type(e).__name__}: {e}"

    per_v = d.get("per") or d.get("PER")
    pbr_v = d.get("pbr") or d.get("PBR")
    if not per_v and not pbr_v:
        return {}, f"NaverSummary: per/pbr 없음 keys={list(d.keys())[:10]}"

    extras: list[dict] = []
    for label, key in [("EPS", "eps"), ("BPS", "bps"), ("배당률", "dividendRatio")]:
        v = d.get(key)
        if v:
            extras.append({"항목": label, "값": str(v)})

    return {
        "quarters":  [],
        "per":       _fmt_ratio(per_v),
        "pbr":       _fmt_ratio(pbr_v),
        "extras":    extras,
        "currency":  "KRW",
        "source":    "Naver Finance",
        "yf_symbol": f"{code}.KS",
    }, ""


# ── Yahoo Finance ─────────────────────────────────────────────────────────────

def _get_yf_session() -> tuple[requests.Session, str]:
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

            per_r, pbr_r = _ks("trailingPE"), _ks("priceToBook")
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
            pass
    return {}, f"Yahoo({yf_sym}): 분기 실적 없음"


def _fetch_yahoo_quote(symbol: str) -> tuple[dict, str]:
    """
    Yahoo Finance quote API (v7/v6 순으로 시도) — crumb 불필요.
    PER·PBR·EPS·배당률·시총 반환.
    """
    errors: list[str] = []

    # 시도할 (URL, params) 조합 목록
    attempts = [
        (f"https://query1.finance.yahoo.com/v7/finance/quote", {"symbols": symbol}),
        (f"https://query2.finance.yahoo.com/v7/finance/quote", {"symbols": symbol}),
        (f"https://query1.finance.yahoo.com/v6/finance/quote", {"symbols": symbol}),
        (f"https://query2.finance.yahoo.com/v6/finance/quote", {"symbols": symbol}),
    ]

    for url, params in attempts:
        try:
            resp = requests.get(url, params=params, headers=_HEADERS_YF,
                                timeout=10, verify=False)
            resp.raise_for_status()
            data = resp.json()
            result = (data.get("quoteResponse") or {}).get("result") or []
            if not result:
                errors.append(f"{url}: result 없음 (응답 앞부분: {resp.text[:80]})")
                continue

            r = result[0]
            currency = r.get("currency") or "USD"
            per_v = r.get("trailingPE")
            pbr_v = r.get("priceToBook")
            if not per_v and not pbr_v:
                available = [k for k, v in r.items() if v is not None][:8]
                errors.append(f"{url}: per/pbr 없음, 사용가능 키={available}")
                continue

            extras: list[dict] = []
            eps = r.get("epsTrailingTwelveMonths")
            div = r.get("dividendYield")   # 소수 e.g. 0.0057 = 0.57%
            cap = r.get("marketCap")
            if eps is not None:
                extras.append({"항목": "EPS", "값": f"${eps:.2f}"})
            if div is not None:
                extras.append({"항목": "배당률", "값": f"{div * 100:.2f}%"})
            if cap is not None:
                extras.append({"항목": "시총", "값": _fmt_amount(cap, currency)})

            return {
                "quarters":  [],
                "per":       f"{per_v:.1f}배" if per_v else "—",
                "pbr":       f"{pbr_v:.2f}배" if pbr_v else "—",
                "extras":    extras,
                "currency":  currency,
                "source":    "Yahoo Finance",
                "yf_symbol": symbol,
            }, ""

        except Exception as e:
            errors.append(f"{url}: {type(e).__name__}: {str(e)[:100]}")

    return {}, " | ".join(errors)


# ── 공개 인터페이스 ───────────────────────────────────────────────────────────

def fetch_financials(symbol: str, market: str) -> tuple[dict, list[str]]:
    """
    재무지표 조회. Returns: (result_dict, [error_messages])
    """
    all_errors: list[str] = []

    # ── 한국 주식 ──────────────────────────────────────────────────────────────
    if market == "KR":
        code = _resolve_kr_code(symbol)

        # 1차: Naver 모바일 API
        fin, err = _fetch_naver_mobile(code)
        if not fin:
            all_errors.append(f"[Naver 모바일] {err}")
            # 2차: Naver itemSummary
            fin, err = _fetch_naver_summary(code)
            if not fin:
                all_errors.append(f"[Naver 요약] {err}")

        if fin:
            # 병행: Yahoo Finance v10으로 분기 실적 추가 시도
            try:
                session, crumb = _get_yf_session()
                for suffix in [".KS", ".KQ"]:
                    yf_fin, _ = _fetch_yahoo(f"{code}{suffix}", session, crumb)
                    if yf_fin.get("quarters"):
                        fin["quarters"] = yf_fin["quarters"]
                        fin["source"] += " + Yahoo(분기)"
                        break
            except Exception:
                pass
            return fin, []

        # 3차: Yahoo Finance v10
        session, crumb = _get_yf_session()
        for suffix in [".KS", ".KQ"]:
            fin, err = _fetch_yahoo(f"{code}{suffix}", session, crumb)
            if fin:
                return fin, []
            all_errors.append(f"[Yahoo {code}{suffix}] {err}")

        return {}, all_errors

    # ── 미국 주식 ──────────────────────────────────────────────────────────────
    sym = symbol.upper()

    # 1차: Yahoo Finance v7/v6 (crumb 불필요 — 기본 지표)
    fin, err = _fetch_yahoo_quote(sym)
    if not fin:
        all_errors.append(f"[Yahoo v7/v6] {err}")

    if fin:
        # 병행: v10으로 분기 실적 추가 시도
        try:
            session, crumb = _get_yf_session()
            yf_fin, _ = _fetch_yahoo(sym, session, crumb)
            if yf_fin.get("quarters"):
                fin["quarters"] = yf_fin["quarters"]
                fin["source"] += " + 분기실적"
        except Exception:
            pass
        return fin, []

    # 2차: Yahoo Finance v10 (crumb 필요)
    session, crumb = _get_yf_session()
    fin, err = _fetch_yahoo(sym, session, crumb)
    if fin:
        return fin, []
    all_errors.append(f"[Yahoo v10] {err}")

    return {}, all_errors
