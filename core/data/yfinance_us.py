import unicodedata
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr
from .base import DataProvider, OHLCV_COLUMNS

# ── 한글명 / 영문별칭 → 실제 티커 맵 ────────────────────────────────────────
_US_ALIAS: dict[str, str] = {
    # 한글 검색
    "애플": "AAPL", "아이폰": "AAPL",
    "엔비디아": "NVDA", "엔디비아": "NVDA",
    "마이크로소프트": "MSFT", "마소": "MSFT",
    "알파벳": "GOOGL", "구글": "GOOGL",
    "아마존": "AMZN",
    "메타": "META", "페이스북": "META",
    "테슬라": "TSLA",
    "버크셔": "BRK-B", "버크셔해서웨이": "BRK-B",
    "브로드컴": "AVGO",
    "일라이릴리": "LLY", "릴리": "LLY",
    "jp모건": "JPM", "제이피모건": "JPM",
    "비자": "V",
    "마스터카드": "MA",
    "유나이티드헬스": "UNH",
    "엑슨모빌": "XOM",
    "존슨앤존슨": "JNJ", "존앤존": "JNJ",
    "월마트": "WMT",
    "프록터앤갬블": "PG", "피앤지": "PG",
    "홈디포": "HD",
    "코카콜라": "KO",
    "펩시": "PEP", "펩시코": "PEP",
    "어도비": "ADBE",
    "세일즈포스": "CRM",
    "넷플릭스": "NFLX",
    "인텔": "INTC",
    "AMD": "AMD", "에이엠디": "AMD",
    "퀄컴": "QCOM",
    "텍사스인스트루먼트": "TXN",
    "마이크론": "MU",
    "암": "ARM", "에이알엠": "ARM",
    "팔란티어": "PLTR",
    "스노우플레이크": "SNOW",
    "코인베이스": "COIN",
    "로빈후드": "HOOD",
    "우버": "UBER",
    "에어비앤비": "ABNB",
    "쇼피파이": "SHOP",
    "줌": "ZM", "줌비디오": "ZM",
    "스포티파이": "SPOT",
    "트위터": "X", "엑스": "X",
    "스냅": "SNAP", "스냅챗": "SNAP",
    "핀터레스트": "PINS",
    "리프트": "LYFT",
    "도어대시": "DASH",
    "인스타카트": "CART",
    "보잉": "BA",
    "캐터필러": "CAT",
    "3m": "MMM",
    "제너럴일렉트릭": "GE", "지이": "GE",
    "포드": "F",
    "제너럴모터스": "GM",
    "디즈니": "DIS",
    "컴캐스트": "CMCSA",
    "버라이즌": "VZ",
    "AT&T": "T", "에이티앤티": "T",
    "뱅크오브아메리카": "BAC", "뱅오아": "BAC",
    "골드만삭스": "GS",
    "모건스탠리": "MS",
    "씨티그룹": "C", "씨티": "C",
    "웰스파고": "WFC",
    "블랙록": "BLK",
    "TSMC": "TSM", "대만반도체": "TSM", "티에스엠씨": "TSM",
    "삼성전자우": "005935",  # KR 예외 케이스
    # 영문 별칭
    "GOOGLE": "GOOGL", "ALPHABET": "GOOGL",
    "FACEBOOK": "META",
    "BERKSHIRE": "BRK-B", "BERKSHIREB": "BRK-B",
    "BRKB": "BRK-B", "BRKA": "BRK-A",
}


def _normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s).strip().lower()


def resolve_us_symbol(symbol: str) -> str:
    """한글명/별칭 → 실제 티커 변환. 변환 불가 시 원본 대문자 반환."""
    key = _normalize(symbol)
    # 1순위: 정적 맵 (한글 포함)
    if key in _US_ALIAS:
        return _US_ALIAS[key]
    # 부분 일치 (예: "엔비디" → 엔비디아)
    for name, ticker in _US_ALIAS.items():
        if len(key) >= 2 and key in name:
            return ticker
    # 영문 대문자 키도 체크
    upper = symbol.upper()
    if upper in _US_ALIAS:
        return _US_ALIAS[upper]
    return upper


class YFinanceProvider(DataProvider):
    """미국 주식 무료 데이터 (FinanceDataReader). 한글 종목명도 지원."""

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        sym = resolve_us_symbol(symbol)
        end = datetime.today()
        start = end - timedelta(days=period_days + 10)
        try:
            raw = fdr.DataReader(sym, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
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
