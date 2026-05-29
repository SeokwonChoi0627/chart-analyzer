from datetime import date
import pandas as pd
from .base import detect_market, OHLCV_COLUMNS
from .mirae import MiraeProvider
from .yfinance_us import YFinanceProvider
from .pykrx_kr import PykrxProvider
from ..cache import OhlcvCache


class DataUnavailableError(Exception):
    """모든 자동 소스에서 데이터를 못 가져왔을 때."""


def fetch(symbol: str, period_days: int, cache: OhlcvCache) -> tuple[pd.DataFrame, str]:
    """OHLCV와 사용된 소스명을 반환. 실패 시 DataUnavailableError."""
    symbol = symbol.strip()
    market = detect_market(symbol)

    cached = cache.load(symbol, max_age_date=date.today())
    if cached is not None and not cached.empty:
        return cached, "캐시"

    mirae = MiraeProvider()
    if mirae.is_available():
        df = mirae.fetch_ohlcv(symbol, period_days)
        if not df.empty:
            cache.save(symbol, df)
            return df, "미래에셋"

    provider = PykrxProvider() if market == "KR" else YFinanceProvider()
    source = "pykrx" if market == "KR" else "yfinance"
    df = provider.fetch_ohlcv(symbol, period_days)
    if not df.empty:
        cache.save(symbol, df)
        return df, source

    raise DataUnavailableError(
        f"'{symbol}' 데이터를 자동으로 가져오지 못했습니다. 엑셀/CSV를 업로드해 주세요."
    )
