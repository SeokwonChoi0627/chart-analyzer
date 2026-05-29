import os
import pandas as pd
from .base import DataProvider, OHLCV_COLUMNS


class MiraeProvider(DataProvider):
    """미래에셋증권 OpenAPI 공급자.
    현재는 API 키/엔드포인트 미확정 상태의 스텁.
    키가 없으면 is_available()=False → 오케스트레이터가 폴백으로 전환."""

    def __init__(self):
        self.app_key = os.getenv("MIRAE_APP_KEY", "").strip()
        self.app_secret = os.getenv("MIRAE_APP_SECRET", "").strip()

    def is_available(self) -> bool:
        return bool(self.app_key and self.app_secret)

    def fetch_ohlcv(self, symbol: str, period_days: int) -> pd.DataFrame:
        if not self.is_available():
            return pd.DataFrame(columns=OHLCV_COLUMNS)
        # 미래에셋 OpenAPI 키 확보 후 실제 호출 구현.
        # 토큰 발급 → 일봉 OHLCV 조회 → 표준 스키마 변환.
        # 현재는 키가 있어도 미구현이므로 빈 DF 반환(폴백 유도).
        return pd.DataFrame(columns=OHLCV_COLUMNS)
