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


def build_intraday_chart(df: pd.DataFrame, title: str = "") -> go.Figure:
    """15분봉 캔들 + 거래량 + RSI 3단 차트 (세션 갭 제거)."""
    # 모든 포인트를 고유한 "MM/DD HH:MM" 문자열로 — 중복 방지 필수
    x_all = df.index.strftime("%m/%d %H:%M").tolist()

    # 눈금에 표시할 레이블: 날짜가 바뀌는 첫 봉만 "MM/DD HH:MM", 나머지는 빈 문자열
    # → 화면에는 날짜 경계만 표시되어 가독성 향상
    dates = df.index.date
    tick_text: list[str] = []
    for i, lbl in enumerate(x_all):
        if i == 0 or dates[i] != dates[i - 1]:
            tick_text.append(lbl)          # 날짜 바뀌는 첫 봉: 날짜+시간 표시
        else:
            tick_text.append("")           # 같은 날 봉: 빈 레이블

    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.55, 0.2, 0.25],
        vertical_spacing=0.04,
        subplot_titles=("15분봉 가격", "거래량", "RSI"),
    )

    # 1단: 캔들
    fig.add_trace(go.Candlestick(
        x=x_all, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="15분봉",
    ), row=1, col=1)

    # 단기 이평선 (5봉=75분, 20봉=5시간)
    for col_, color in [("sma5", "#ff9800"), ("sma20", "#2196f3")]:
        if col_ in df.columns:
            fig.add_trace(go.Scatter(
                x=x_all, y=df[col_], name=col_.upper(),
                line=dict(width=1, color=color),
            ), row=1, col=1)

    # 2단: 거래량 (양봉/음봉 색상)
    bar_colors = [
        "#26a69a" if c >= o else "#ef5350"
        for c, o in zip(df["close"], df["open"])
    ]
    fig.add_trace(go.Bar(
        x=x_all, y=df["volume"], name="거래량",
        marker_color=bar_colors, showlegend=False,
    ), row=2, col=1)

    # 3단: RSI
    if "rsi" in df.columns:
        fig.add_trace(go.Scatter(
            x=x_all, y=df["rsi"], name="RSI",
            line=dict(color="#e91e63", width=1.5), showlegend=False,
        ), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red",   row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="blue",  row=3, col=1)

    fig.update_layout(
        title=f"{title} — 15분봉" if title else "15분봉",
        height=480,
        showlegend=False,
        xaxis_rangeslider_visible=False,
        margin=dict(t=50, b=40),
    )
    # 카테고리 축: 모든 x값은 고유 → 야간/주말 갭 없이 연속 표시
    # tickvals/ticktext로 날짜 경계만 레이블 표시
    fig.update_xaxes(
        type="category",
        tickvals=x_all,
        ticktext=tick_text,
        tickangle=-45,
    )
    return fig
