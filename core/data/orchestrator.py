from datetime import date
import pandas as pd
from .base import clean_ohlcv, detect_market, OHLCV_COLUMNS
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

    # 캐시에 이미 미완성 봉(close NaN)이 저장됐을 수 있어 로드 후에도 정화
    cached = clean_ohlcv(cache.load(symbol, max_age_date=date.today()))
    if cached is not None and not cached.empty:
        return cached, "캐시"

    mirae = MiraeProvider()
    if mirae.is_available():
        df = clean_ohlcv(mirae.fetch_ohlcv(symbol, period_days))
        if not df.empty:
            cache.save(symbol, df)
            return df, "미래에셋"

    provider = PykrxProvider() if market == "KR" else YFinanceProvider()
    source = "pykrx" if market == "KR" else "yfinance"
    df = clean_ohlcv(provider.fetch_ohlcv(symbol, period_days))
    if not df.empty:
        cache.save(symbol, df)
        return df, source

    if market == "KR":
        raise DataUnavailableError(
            f"'{symbol}' 데이터를 가져오지 못했습니다.\n"
            f"종목코드(예: 005930) 또는 정확한 종목명(예: 삼성전자)으로 입력해 보세요."
        )
    raise DataUnavailableError(
        f"'{symbol}' 데이터를 가져오지 못했습니다.\n"
        f"티커 심볼(예: AAPL, TSLA)로 정확히 입력해 보세요."
    )
