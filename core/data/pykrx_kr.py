from datetime import datetime, timedelta
import pandas as pd
from pykrx import stock
from .base import DataProvider, OHLCV_COLUMNS


class PykrxProvider(DataProvider):
    """한국 주식 무료 데이터 (pykrx). 종목코드 6자리 필요."""

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        if not symbol.isdigit():
            ticker = self._name_to_ticker(symbol)
            if ticker is None:
                return pd.DataFrame(columns=OHLCV_COLUMNS)
            symbol = ticker
        end = datetime.today()
        start = end - timedelta(days=period_days + 10)
        raw = stock.get_market_ohlcv(
            start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), symbol
        )
        if raw is None or raw.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        raw = raw.rename(columns={
            "시가": "open", "고가": "high", "저가": "low",
            "종가": "close", "거래량": "volume",
        })
        out = raw[OHLCV_COLUMNS].copy()
        out.index = pd.to_datetime(out.index)
        out.index.name = None
        return out.sort_index()

    @staticmethod
    def _name_to_ticker(name: str) -> str | None:
        for market in ("KOSPI", "KOSDAQ"):
            for ticker in stock.get_market_ticker_list(market=market):
                if stock.get_market_ticker_name(ticker) == name:
                    return ticker
        return None
