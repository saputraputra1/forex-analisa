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

def get_all_timeframes():
    m5 = get_live_candles_m5(50)
    m15 = get_live_candles_m15(30)
    price = None
    if not m5.empty:
        price = round(m5["close"].iloc[-1], 2)
    elif not m15.empty:
        price = round(m15["close"].iloc[-1], 2)
    if price is None:
        price = get_current_price()
    return {
        "price": price,
        "M5": m5,
        "M15": m15,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
