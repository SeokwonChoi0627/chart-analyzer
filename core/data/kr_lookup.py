"""한글 종목명 → 6자리 코드 변환 유틸. 외부 의존성 최소화."""
import unicodedata

# ── 주요 종목 정적 맵 (네트워크 없이 즉시 변환) ──────────────────────────────
_MAP: dict[str, str] = {
    "삼성전자": "005930", "sk하이닉스": "000660",
    "lg에너지솔루션": "373220", "삼성바이오로직스": "207940",
    "현대차": "005380", "현대자동차": "005380",
    "기아": "000270", "셀트리온": "068270",
    "포스코홀딩스": "005490", "kb금융": "105560",
    "신한지주": "055550", "삼성sdi": "006400",
    "lg화학": "051910", "하나금융지주": "086790",
    "현대모비스": "012330", "카카오": "035720",
    "네이버": "035420", "naver": "035420",
    "sk이노베이션": "096770", "삼성물산": "028260",
    "크래프톤": "259960", "카카오뱅크": "323410",
    "카카오페이": "377300", "두산에너빌리티": "034020",
    "한국전력": "015760", "고려아연": "010130",
    "아모레퍼시픽": "090430", "한화에어로스페이스": "012450",
    "에코프로비엠": "247540", "에코프로": "086520",
    "포스코퓨처엠": "003670", "엘앤에프": "066970",
    "넷마블": "251270", "sk텔레콤": "017670",
    "kt": "030200", "lg전자": "066570",
    "삼성생명": "032830", "삼성화재": "000810",
    "현대건설": "000720", "롯데케미칼": "011170",
    "sk케미칼": "285130", "한미약품": "128940",
    "셀트리온헬스케어": "091990", "삼성엔지니어링": "028050",
    "두산밥캣": "241560", "금호석유": "011780",
    "키움증권": "039490", "미래에셋증권": "006800",
    "s-oil": "010950", "lx홀딩스": "383800",
    "에스디바이오센서": "137310", "현대중공업": "329180",
    "한화솔루션": "009830", "대한항공": "003490",
    "하이브": "352820", "sm엔터테인먼트": "041510",
    "jyp엔터테인먼트": "035900", "yg엔터테인먼트": "122870",
}


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()


def resolve_kr_code(symbol: str) -> str:
    """
    한글 종목명(또는 부분명) → 6자리 종목코드.
    1순위: 정적 맵 (즉시, 네트워크 불필요)
    2순위: Naver 자동완성 API
    3순위: FDR KRX listing
    변환 실패 시 원본 반환.
    """
    s = symbol.strip()
    if s.isdigit():
        return s

    key = _nfc(s)

    # 1순위: 정적 맵
    if key in _MAP:
        return _MAP[key]
    # 부분 일치 (예: "삼성전" → "삼성전자")
    for name, code in _MAP.items():
        if key in name:
            return code

    # 2순위: Naver 자동완성
    try:
        import requests, urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 Mobile Safari/604.1"
            ),
            "Referer": "https://m.stock.naver.com",
            "Accept": "application/json, text/plain, */*",
        }
        r = requests.get(
            "https://ac.finance.naver.com/api/ac",
            params={"q": s, "st": "111111", "r_lt": "111111",
                    "r_vt": "100", "r_rqcnt": "5"},
            headers=headers, timeout=6, verify=False,
        )
        r.raise_for_status()
        for item in (r.json().get("resultList") or []):
            code = str(item.get("code") or "").zfill(6)
            label = _nfc(str(item.get("name") or ""))
            if code and key in label:
                return code
    except Exception:
        pass

    # 3순위: FDR KRX listing
    try:
        import FinanceDataReader as fdr
        listing = fdr.StockListing("KRX").copy()
        listing["_k"] = listing["Name"].apply(
            lambda x: _nfc(str(x)) if __import__("pandas").notna(x) else ""
        )
        matched = listing[listing["_k"] == key]
        if not matched.empty:
            return matched.iloc[0]["Code"]
        matched = listing[listing["_k"].str.contains(key, na=False, regex=False)]
        if not matched.empty:
            matched = matched.copy()
            matched["_l"] = matched["_k"].str.len()
            return matched.sort_values("_l").iloc[0]["Code"]
    except Exception:
        pass

    return s
