import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_chart(df: pd.DataFrame, title: str = "") -> go.Figure:
    """캔들 + 이평선 + MACD + RSI + 거래량 4단 서브플롯 Figure 생성."""
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        row_heights=[0.5, 0.18, 0.16, 0.16],
        vertical_spacing=0.03,
        subplot_titles=("가격/이평선", "거래량", "MACD", "RSI"),
    )

    # 1단: 캔들 + 이평선
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="가격",
    ), row=1, col=1)
    for w, color in [("sma5", "#ff9800"), ("sma20", "#2196f3"), ("sma60", "#9c27b0")]:
        if w in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[w], name=w.upper(),
                line=dict(width=1, color=color),
            ), row=1, col=1)

    # 2단: 거래량
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="거래량",
                         marker_color="#90a4ae"), row=2, col=1)

    # 3단: MACD
    if "macd" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["macd"], name="MACD",
                                 line=dict(color="#2196f3", width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["macd_signal"], name="Signal",
                                 line=dict(color="#ff9800", width=1)), row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df["macd_hist"], name="Hist",
                             marker_color="#bdbdbd"), row=3, col=1)

    # 4단: RSI
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI",
                                 line=dict(color="#e91e63", width=1)), row=4, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="blue", row=4, col=1)

    fig.update_layout(
        title=title, height=900, showlegend=True,
        xaxis_rangeslider_visible=False, margin=dict(t=60, b=20),
    )
    return fig
