import yfinance as yf
import pandas as pd
import numpy as np
import requests
import re
import time
from datetime import datetime, timezone
from config import now_jakarta

SYMBOL = "GC=F"

_spot_cache = {"price": None, "timestamp": -9999}
SPOT_CACHE_TTL = 30

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

def get_spot_price_xe():
    global _spot_cache
    now = time.time()
    if _spot_cache["price"] and now - _spot_cache["timestamp"] < SPOT_CACHE_TTL:
        return _spot_cache["price"]
    try:
        r = requests.get(
            "https://www.xe.com/currencyconverter/convert/?From=XAU&To=USD",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10,
        )
        if r.status_code == 200:
            m = re.search(r'1\.?\s*XAU\s*=?\s*([\d,]+\.\d{2,4})\s*USD', r.text)
            if m:
                price = float(m.group(1).replace(",", ""))
                _spot_cache = {"price": round(price, 2), "timestamp": now}
                return round(price, 2)
    except Exception:
        pass
    return None

def get_live_price():
    # priority 1: XAUUSD spot (sama dengan chart broker)
    try:
        ticker = yf.Ticker("XAUUSD=X")
        fi = ticker.fast_info
        if fi.last_price and fi.last_price > 100:
            return round(fi.last_price, 2), "XAUUSD spot (yfinance)"
    except Exception:
        pass
    # priority 2: GC=F fast_info
    try:
        ticker = yf.Ticker(SYMBOL)
        fi = ticker.fast_info
        if fi.last_price and fi.last_price > 100:
            return round(fi.last_price, 2), "GC=F futures (yfinance)"
    except Exception:
        pass
    # priority 3: last candle 1m/5m
    cp = get_current_price()
    if cp:
        return cp, "GC=F futures (yfinance)"
    # priority 4: xe.com spot
    spot = get_spot_price_xe()
    if spot is not None:
        return spot, "XAUUSD spot (xe.com)"
    return None, "N/A"

def get_all_timeframes():
    m5 = get_live_candles_m5(50)
    m15 = get_live_candles_m15(30)
    h1 = get_live_candles_h1(50)
    h4 = resample_h4(h1)
    d1 = get_live_candles_d1(30)

    price, price_source = get_live_price()
    if price is None:
        price_source = "GC=F futures (yfinance)"
        for df in [m5, m15, h1, h4, d1]:
            if not df.empty:
                price = round(df["close"].iloc[-1], 2)
                break
    if price is None:
        cp = get_current_price()
        if cp:
            price = cp

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
        "price_source": price_source,
        "timestamp": now_jakarta().strftime("%Y-%m-%d %H:%M:%S"),
    }
