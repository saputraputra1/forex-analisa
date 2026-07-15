import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

SYMBOL = "GC=F"

def get_current_price():
    ticker = yf.Ticker(SYMBOL)
    data = ticker.history(period="1d", interval="1m")
    if not data.empty:
        return round(data["Close"].iloc[-1], 2)
    data = ticker.history(period="1d", interval="5m")
    if not data.empty:
        return round(data["Close"].iloc[-1], 2)
    return None

def get_candles(interval="5m", period="1d", limit=50):
    ticker = yf.Ticker(SYMBOL)
    data = ticker.history(period=period, interval=interval)
    if data.empty:
        return pd.DataFrame()
    data = data.tail(limit).copy()
    data.columns = [c.lower() for c in data.columns]
    return data

def get_live_candles_m5(limit=50):
    return get_candles(interval="5m", period="1d", limit=limit)

def get_live_candles_m15(limit=30):
    return get_candles(interval="15m", period="2d", limit=limit)

def get_live_candles_h1(limit=50):
    return get_candles(interval="60m", period="5d", limit=limit)

def get_live_candles_d1(limit=30):
    return get_candles(interval="1d", period="1mo", limit=limit)

def resample_h4(df_h1):
    if df_h1.empty or len(df_h1) < 4:
        return pd.DataFrame()
    df = df_h1.copy()
    df.index = pd.to_datetime(df.index)
    h4 = df.resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["close"])
    return h4.tail(30)

def get_all_timeframes():
    m5 = get_live_candles_m5(50)
    m15 = get_live_candles_m15(30)
    h1 = get_live_candles_h1(50)
    h4 = resample_h4(h1)
    d1 = get_live_candles_d1(30)

    price = None
    for df in [m5, m15, h1, h4, d1]:
        if not df.empty:
            price = round(df["close"].iloc[-1], 2)
            break
    if price is None:
        price = get_current_price()

    return {
        "price": price,
        "M5": m5,
        "M15": m15,
        "H1": h1,
        "H4": h4,
        "D1": d1,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
