import unicodedata
from datetime import datetime, timedelta
import pandas as pd
import requests
import FinanceDataReader as fdr
from .base import DataProvider, OHLCV_COLUMNS

# 자주 쓰는 종목 정적 맵 (Naver/FDR 모두 실패할 때 폴백)
_COMMON_STOCKS: dict[str, str] = {
    "삼성전자": "005930", "sk하이닉스": "000660", "sk하이닉스우": "000661",
    "lg에너지솔루션": "373220", "삼성바이오로직스": "207940", "현대차": "005380",
    "기아": "000270", "셀트리온": "068270", "포스코홀딩스": "005490",
    "kb금융": "105560", "신한지주": "055550", "삼성sdi": "006400",
    "lg화학": "051910", "하나금융지주": "086790", "현대모비스": "012330",
    "카카오": "035720", "네이버": "035420", "naver": "035420",
    "sk이노베이션": "096770", "삼성물산": "028260", "넷마블": "251270",
    "크래프톤": "259960", "카카오뱅크": "323410", "카카오페이": "377300",
    "두산에너빌리티": "034020", "한국전력": "015760", "고려아연": "010130",
    "아모레퍼시픽": "090430", "한화에어로스페이스": "012450",
    "에코프로비엠": "247540", "에코프로": "086520", "포스코퓨처엠": "003670",
    "엘앤에프": "066970", "코스모신소재": "005070", "hy": "022100",
}

_NAVER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 Mobile Safari/604.1"
    ),
    "Referer": "https://m.stock.naver.com",
    "Accept": "application/json, text/plain, */*",
}


def _normalize(s: str) -> str:
    """NFC 정규화 + 공백 제거."""
    return unicodedata.normalize("NFC", s).strip()


def _lookup_naver(name: str) -> str | None:
    """Naver Finance 자동완성 API로 종목명 → 코드 변환."""
    for base in [
        "https://ac.finance.naver.com/api/ac",
        "https://m.stock.naver.com/api/search/stocks",
    ]:
        try:
            params = {"q": name, "query": name, "st": "111111",
                      "r_lt": "111111", "r_vt": "100", "r_rqcnt": "5"}
            r = requests.get(base, params=params, headers=_NAVER_HEADERS,
                             timeout=6, verify=False)
            r.raise_for_status()
            data = r.json()
            # ac.finance 형식
            items = data.get("resultList") or data.get("items") or []
            for item in items:
                code = item.get("code") or item.get("itemCode") or item.get("symbol")
                label = _normalize(str(item.get("name") or item.get("itemName") or ""))
                if code and _normalize(name) in label:
                    return str(code).zfill(6)
        except Exception:
            continue
    return None


def _lookup_fdr(name: str) -> str | None:
    """FinanceDataReader StockListing으로 종목명 → 코드 변환."""
    name_nfc = _normalize(name)
    try:
        listing = fdr.StockListing("KRX")
        listing = listing.copy()
        listing["_nfc"] = listing["Name"].apply(
            lambda x: _normalize(str(x)) if pd.notna(x) else ""
        )
        matched = listing[listing["_nfc"] == name_nfc]
        if not matched.empty:
            return matched.iloc[0]["Code"]
        matched = listing[listing["_nfc"].str.contains(name_nfc, na=False, regex=False)]
        if not matched.empty:
            matched = matched.copy()
            matched["_len"] = matched["_nfc"].str.len()
            return matched.sort_values("_len").iloc[0]["Code"]
    except Exception:
        pass
    return None


class PykrxProvider(DataProvider):
    """한국 주식 무료 데이터 (FinanceDataReader)."""

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        symbol = _normalize(symbol)

        if not symbol.isdigit():
            ticker = self._name_to_ticker(symbol)
            if ticker is None:
                return pd.DataFrame(columns=OHLCV_COLUMNS)
            symbol = ticker

        end = datetime.today()
        start = end - timedelta(days=period_days + 10)
        try:
            raw = fdr.DataReader(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        except Exception:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        if raw is None or raw.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        raw = raw.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        out = raw[OHLCV_COLUMNS].copy()
        out.index = pd.to_datetime(out.index)
        out.index.name = None
        return out.sort_index()

    @staticmethod
    def _name_to_ticker(name: str) -> str | None:
        name_nfc = _normalize(name)
        name_lower = name_nfc.lower()

        # 1순위: 정적 맵 (즉시, 네트워크 불필요)
        if name_lower in _COMMON_STOCKS:
            return _COMMON_STOCKS[name_lower]

        # 2순위: Naver 자동완성 (서버에서 신뢰성 높음)
        code = _lookup_naver(name_nfc)
        if code:
            return code

        # 3순위: FinanceDataReader KRX listing (로컬에서 신뢰성 높음)
        return _lookup_fdr(name_nfc)
