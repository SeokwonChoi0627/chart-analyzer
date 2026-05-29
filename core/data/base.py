from abc import ABC, abstractmethod
import re
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def detect_market(symbol: str) -> str:
    """종목 입력을 보고 시장 판별. 'KR' 또는 'US' 반환."""
    s = symbol.strip()
    if re.fullmatch(r"\d{6}", s):
        return "KR"
    if re.search(r"[가-힣]", s):
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
