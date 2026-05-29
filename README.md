# 차트 분석 매수/매도 추천기

개인용 주식 기술적 분석 도구. 일봉 데이터를 이평선·MACD·RSI·볼린저밴드·거래량으로 분석해 매수/매도 신호를 점수화한다.

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 데이터 소스

미래에셋 API(.env 설정 시) → yfinance(미국)/pykrx(한국) 자동 폴백 → 엑셀 업로드.

## 테스트

```bash
pytest -v
```
