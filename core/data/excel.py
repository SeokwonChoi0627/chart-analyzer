import pandas as pd

COLUMN_ALIASES = {
    "open":   {"open", "시가", "시작가"},
    "high":   {"high", "고가", "최고가"},
    "low":    {"low", "저가", "최저가"},
    "close":  {"close", "종가", "현재가", "adj close"},
    "volume": {"volume", "거래량", "vol"},
}
DATE_ALIASES = {"date", "일자", "날짜", "거래일", "기준일"}


def _build_rename_map(columns) -> dict:
    rename = {}
    for col in columns:
        key = str(col).strip().lower()
        if key in DATE_ALIASES:
            rename[col] = "__date__"
            continue
        for std, aliases in COLUMN_ALIASES.items():
            if key in aliases:
                rename[col] = std
                break
    return rename


def parse_ohlcv_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """임의 컬럼명의 DataFrame을 표준 OHLCV 스키마로 변환."""
    rename = _build_rename_map(raw.columns)
    df = raw.rename(columns=rename)

    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if "__date__" not in df.columns:
        missing.append("날짜")
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}. 인식 가능한 컬럼명을 확인하세요.")

    df["__date__"] = pd.to_datetime(df["__date__"])
    df = df.set_index("__date__").sort_index()
    df.index.name = None
    out = df[required].astype(float)
    return out
