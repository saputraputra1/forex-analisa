import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from config import now_jakarta

SYMBOL = "GC=F"

STALE_THRESHOLD_MIN = {
    "M5": 15,
    "M15": 30,
    "H1": 120,
    "H4": 300,
    "D1": 1440,
}

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
    if data.index.tz is None:
        data.index = pd.DatetimeIndex(data.index).tz_localize("UTC")
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
    h4 = df.resample("4h").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna(subset=["close"])
    return h4.tail(30)

def _get_candle_age_min(df):
    if df.empty:
        return None
    last_time = df.index[-1]
    now_utc = datetime.now(timezone.utc)
    if last_time.tzinfo is None:
        last_time = last_time.tz_localize("UTC")
    delta = now_utc - last_time
    return delta.total_seconds() / 60

def get_live_price():
    try:
        ticker = yf.Ticker(SYMBOL)
        fi = ticker.fast_info
        if fi.last_price:
            return round(fi.last_price, 2)
    except Exception:
        pass
    return get_current_price()

def get_all_timeframes():
    m5 = get_live_candles_m5(50)
    m15 = get_live_candles_m15(30)
    h1 = get_live_candles_h1(50)
    h4 = resample_h4(h1)
    d1 = get_live_candles_d1(30)

    price = get_live_price()
    if price is None:
        for df in [m5, m15, h1, h4, d1]:
            if not df.empty:
                price = round(df["close"].iloc[-1], 2)
                break
    if price is None:
        price = get_current_price()

    data_stale = False
    for tf_name, df, threshold in [
        ("M5", m5, STALE_THRESHOLD_MIN["M5"]),
        ("M15", m15, STALE_THRESHOLD_MIN["M15"]),
    ]:
        age = _get_candle_age_min(df)
        if age is not None and age > threshold:
            data_stale = True
            break

    return {
        "price": price,
        "M5": m5,
        "M15": m15,
        "H1": h1,
        "H4": h4,
        "D1": d1,
        "data_stale": data_stale,
        "price_source": "GC=F futures",
        "timestamp": now_jakarta().strftime("%Y-%m-%d %H:%M:%S"),
    }
