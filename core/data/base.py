from abc import ABC, abstractmethod
import re
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """미완성 봉 제거: close가 NaN인 행 삭제. 원본 불변.

    FinanceDataReader는 미국장 미마감 시점에 마지막 봉을 close=NaN으로
    반환하는 경우가 있어, 지표 계산 전에 반드시 걸러야 한다.
    """
    if df is None:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    if df.empty or "close" not in df.columns:
        return df
    return df.dropna(subset=["close"])


def detect_market(symbol: str) -> str:
    """종목 입력을 보고 시장 판별. 'KR' 또는 'US' 반환."""
    import unicodedata
    s = symbol.strip()
    if re.fullmatch(r"\d{6}", s):
        return "KR"
    if re.search(r"[가-힣]", s):
        # 한글이지만 미국 종목명인지 먼저 확인
        try:
            from .yfinance_us import _US_ALIAS, _normalize
            if _normalize(s) in _US_ALIAS:
                return "US"
        except Exception:
            pass
        return "KR"
    return "US"


class DataProvider(ABC):
    """모든 데이터 공급자의 공통 인터페이스."""

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        """OHLCV DataFrame 반환.
        index=DatetimeIndex(오름차순), columns=OHLCV_COLUMNS.
        데이터 없으면 빈 DataFrame 반환(예외 X)."""
        raise NotImplementedError
