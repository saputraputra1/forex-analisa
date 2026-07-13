import numpy as np

def detect_swing_high_low(data, window=5):
    high = data["high"].values
    low = data["low"].values
    close = data["close"].values
    n = len(high)
    swings = []
    for i in range(window, n - window):
        if high[i] == max(high[i-window:i+window+1]):
            swings.append({"type": "SH", "price": round(high[i], 2), "index": i})
        if low[i] == min(low[i-window:i+window+1]):
            swings.append({"type": "SL", "price": round(low[i], 2), "index": i})
    return swings

def get_nearest_swing_levels(data, window=5, n_levels=3):
    swings = detect_swing_high_low(data, window)
    current = round(data["close"].iloc[-1], 2)
    sh_levels = sorted([s["price"] for s in swings if s["type"] == "SH"], reverse=True)
    sl_levels = sorted([s["price"] for s in swings if s["type"] == "SL"])
    res_above = [r for r in sh_levels if r > current][:n_levels]
    sup_below = [s for s in sl_levels if s < current][:n_levels]
    near_res = res_above[0] if res_above else round(current * 1.005, 2)
    near_sup = sup_below[-1] if sup_below else round(current * 0.995, 2)
    return {
        "swing_highs": sh_levels[:n_levels],
        "swing_lows": sl_levels[:n_levels],
        "nearest_resistance": near_res,
        "nearest_support": near_sup,
        "current_price": current,
    }

def market_structure(data, window=5):
    swings = detect_swing_high_low(data, window)
    sh = [s for s in swings if s["type"] == "SH"]
    sl = [s for s in swings if s["type"] == "SL"]
    last_sh = [s["price"] for s in sh[-3:]]
    last_sl = [s["price"] for s in sl[-3:]]
    trend = "neutral"
    if len(last_sh) >= 2 and len(last_sl) >= 2:
        if last_sh[-1] > last_sh[-2] and last_sl[-1] > last_sl[-2]:
            trend = "uptrend"
        elif last_sh[-1] < last_sh[-2] and last_sl[-1] < last_sl[-2]:
            trend = "downtrend"
    bos = False
    close = round(data["close"].iloc[-1], 2)
    if trend == "uptrend" and len(last_sh) >= 2:
        if close > last_sh[-1]:
            bos = True
    if trend == "downtrend" and len(last_sl) >= 2:
        if close < last_sl[-1]:
            bos = True
    return {"trend": trend, "bos": bos, "last_highs": last_sh, "last_lows": last_sl}

def detect_choch(data, window=5):
    swings = detect_swing_high_low(data, window)
    sh = [s for s in swings if s["type"] == "SH"]
    sl = [s for s in swings if s["type"] == "SL"]
    choch = None
    if len(sh) >= 2 and len(sl) >= 2:
        if sh[-1]["price"] < sh[-2]["price"] and sl[-1]["price"] > sl[-2]["price"]:
            choch = "bullish"
        elif sh[-1]["price"] > sh[-2]["price"] and sl[-1]["price"] < sl[-2]["price"]:
            choch = "bearish"
    return choch

def get_pivot_points(high, low, close):
    pp = (high + low + close) / 3
    r1 = 2 * pp - low
    r2 = pp + (high - low)
    r3 = high + 2 * (pp - low)
    s1 = 2 * pp - high
    s2 = pp - (high - low)
    s3 = low - 2 * (high - pp)
    return {
        "pivot": round(pp, 2), "r1": round(r1, 2), "r2": round(r2, 2), "r3": round(r3, 2),
        "s1": round(s1, 2), "s2": round(s2, 2), "s3": round(s3, 2),
    }

def get_round_numbers(price, range_width=50):
    base = int(price / 10) * 10
    return [base + i * 10 for i in range(-range_width//10, range_width//10 + 1)]

def get_nearest_round_numbers(price, n=3):
    base = round(price / 10) * 10
    return [base + i * 10 for i in range(-n, n + 1)]

def analyze_snr(data):
    close = round(data["close"].iloc[-1], 2)
    high = round(data["high"].max(), 2)
    low = round(data["low"].min(), 2)
    swing_levels = get_nearest_swing_levels(data)
    ms = market_structure(data)
    choch = detect_choch(data)
    round_nums = get_nearest_round_numbers(close, 3)
    pivots = get_pivot_points(high, low, close)
    return {
        "close": close,
        "trend": ms["trend"],
        "bos": ms["bos"],
        "choch": choch,
        "nearest_resistance": swing_levels["nearest_resistance"],
        "nearest_support": swing_levels["nearest_support"],
        "swing_highs": swing_levels["swing_highs"],
        "swing_lows": swing_levels["swing_lows"],
        "round_numbers": round_nums,
        "pivot": pivots["pivot"],
        "pivot_r1": pivots["r1"],
        "pivot_s1": pivots["s1"],
        "pivot_r2": pivots["r2"],
        "pivot_s2": pivots["s2"],
    }
