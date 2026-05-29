from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr
from .base import DataProvider, OHLCV_COLUMNS


class YFinanceProvider(DataProvider):
    """미국 주식 무료 데이터 (FinanceDataReader). SSL 프록시 환경에서도 동작."""

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        end = datetime.today()
        start = end - timedelta(days=period_days + 10)
        raw = fdr.DataReader(symbol.upper(), start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
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
