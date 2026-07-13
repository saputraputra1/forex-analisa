import pandas as pd
import numpy as np

def rsi(data, period=7):
    close = data["close"].values
    deltas = np.diff(close)
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 100
    rsi_val = np.zeros_like(close)
    rsi_val[:period] = 100 - (100 / (1 + rs))
    for i in range(period, len(close)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0
        else:
            upval = 0
            downval = -delta
        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 100
        rsi_val[i] = 100 - (100 / (1 + rs))
    return round(rsi_val[-1], 2)

def macd(data, fast=5, slow=13, signal=5):
    close = data["close"].values
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "macd": round(macd_line[-1], 2),
        "signal": round(signal_line[-1], 2),
        "histogram": round(histogram[-1], 2),
    }

def _ema(data, period):
    result = np.zeros_like(data)
    multiplier = 2 / (period + 1)
    result[:period] = np.mean(data[:period])
    for i in range(period, len(data)):
        result[i] = (data[i] - result[i-1]) * multiplier + result[i-1]
    return result

def sma(data, period):
    close = data["close"].values
    if len(close) < period:
        return round(close[-1], 2)
    return round(np.mean(close[-period:]), 2)

def ema(data, period):
    close = data["close"].values
    result = _ema(close, period)
    return round(result[-1], 2)

def bollinger_bands(data, period=20, std_dev=2.0):
    close = data["close"].values
    if len(close) < period:
        return {"upper": close[-1], "middle": close[-1], "lower": close[-1]}
    rolling_mean = np.mean(close[-period:])
    rolling_std = np.std(close[-period:])
    upper = rolling_mean + (rolling_std * std_dev)
    lower = rolling_mean - (rolling_std * std_dev)
    return {
        "upper": round(upper, 2),
        "middle": round(rolling_mean, 2),
        "lower": round(lower, 2),
    }

def stochastic(data, k_period=5, d_period=3, smooth=3):
    high = data["high"].values
    low = data["low"].values
    close = data["close"].values
    n = len(close)
    if n < k_period + d_period + smooth:
        return {"k": 50, "d": 50}
    k_vals = []
    for i in range(n - k_period + 1, n + 1):
        hh = np.max(high[i-k_period:i])
        ll = np.min(low[i-k_period:i])
        c = close[i-1]
        if hh == ll:
            k_vals.append(50)
        else:
            k_vals.append(100 * (c - ll) / (hh - ll))
    if len(k_vals) < smooth:
        return {"k": round(k_vals[-1], 2), "d": round(k_vals[-1], 2)}
    k_smooth = []
    for i in range(smooth, len(k_vals) + 1):
        k_smooth.append(np.mean(k_vals[i-smooth:i]))
    k_final = k_smooth[-1] if k_smooth else k_vals[-1]
    if len(k_smooth) < d_period:
        d_final = k_final
    else:
        d_final = np.mean(k_smooth[-d_period:])
    return {"k": round(k_final, 2), "d": round(d_final, 2)}

def support_resistance(data, window=5):
    high = data["high"].values
    low = data["low"].values
    close = data["close"].values
    resistances = []
    supports = []
    for i in range(window, len(high) - window):
        if high[i] == max(high[i-window:i+window+1]):
            resistances.append(high[i])
        if low[i] == min(low[i-window:i+window+1]):
            supports.append(low[i])
    current = close[-1]
    near_support = None
    near_resistance = None
    for s in supports:
        if s < current:
            if near_support is None or s > near_support:
                near_support = s
    for r in resistances:
        if r > current:
            if near_resistance is None or r < near_resistance:
                near_resistance = r
    return {
        "nearest_support": round(near_support, 2) if near_support else round(current * 0.995, 2),
        "nearest_resistance": round(near_resistance, 2) if near_resistance else round(current * 1.005, 2),
    }

def calculate_all(data):
    if data.empty or len(data) < 20:
        return None
    bb = bollinger_bands(data)
    stoch = stochastic(data)
    return {
        "rsi": rsi(data),
        "macd": macd(data),
        "sma_9": sma(data, 9),
        "sma_21": sma(data, 21),
        "sma_50": sma(data, 50),
        "ema_9": ema(data, 9),
        "ema_21": ema(data, 21),
        "ema_50": ema(data, 50),
        "bb": bb,
        "stochastic": stoch,
        "sr": support_resistance(data),
        "close": round(data["close"].iloc[-1], 2),
        "high": round(data["high"].max(), 2),
        "low": round(data["low"].min(), 2),
        "volume": int(data["volume"].sum()),
    }
