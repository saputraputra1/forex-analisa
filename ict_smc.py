from datetime import datetime

def get_killzone(utc_hour=None):
    if utc_hour is None:
        utc_hour = datetime.utcnow().hour
    if 0 <= utc_hour < 5:
        return "Asian Killzone (00:00-05:00 UTC)"
    if 5 <= utc_hour < 7:
        return "Asian-London Transition"
    if 7 <= utc_hour < 10:
        return "London Killzone (07:00-10:00 UTC)"
    if 10 <= utc_hour < 11:
        return "Silver Bullet (10:00-11:00 UTC) - London/NY Overlap"
    if 11 <= utc_hour < 13:
        return "London-NY Transition"
    if 13 <= utc_hour < 16:
        return "NY Killzone (13:00-16:00 UTC)"
    if 16 <= utc_hour < 18:
        return "NY Afternoon (16:00-18:00 UTC)"
    return "Low Volume Period (18:00-00:00 UTC)"

def detect_order_blocks(data, n_lookback=15):
    close = data["close"].values
    open_p = data["open"].values
    high = data["high"].values
    low = data["low"].values
    bullish_obs = []
    bearish_obs = []
    for i in range(2, min(n_lookback, len(close))):
        if close[-i] < open_p[-i] and close[-(i-1)] > open_p[-(i-1)]:
            delta = high[-i] - low[-i]
            if delta > 0:
                bullish_obs.append({
                    "type": "bullish",
                    "zone_top": round(high[-i], 2),
                    "zone_bottom": round(low[-i], 2),
                    "strength": "strong" if delta > (high[-i-1] - low[-i-1]) else "moderate",
                    "distance_candles": i,
                })
        if close[-i] > open_p[-i] and close[-(i-1)] < open_p[-(i-1)]:
            delta = high[-i] - low[-i]
            if delta > 0:
                bearish_obs.append({
                    "type": "bearish",
                    "zone_top": round(high[-i], 2),
                    "zone_bottom": round(low[-i], 2),
                    "strength": "strong" if delta > (high[-i-1] - low[-i-1]) else "moderate",
                    "distance_candles": i,
                })
    current = round(close[-1], 2)
    active_ob = None
    for ob in (bullish_obs + bearish_obs):
        if ob["zone_bottom"] <= current <= ob["zone_top"]:
            active_ob = ob
            break
    return {
        "bullish_obs": bullish_obs[:3],
        "bearish_obs": bearish_obs[:3],
        "active_ob": active_ob,
        "total_detected": len(bullish_obs) + len(bearish_obs),
    }

def detect_fvg(data, n_lookback=20):
    high = data["high"].values
    low = data["low"].values
    bullish_fvgs = []
    bearish_fvgs = []
    for i in range(2, min(n_lookback, len(high))):
        if low[-i] > high[-(i-2)]:
            gap_top = round(low[-i], 2)
            gap_bottom = round(high[-(i-2)], 2)
            if gap_top - gap_bottom > 0:
                bullish_fvgs.append({
                    "type": "bullish",
                    "gap_top": gap_top,
                    "gap_bottom": gap_bottom,
                    "gap_size": round(gap_top - gap_bottom, 2),
                    "distance_candles": i,
                })
        if high[-i] < low[-(i-2)]:
            gap_top = round(low[-(i-2)], 2)
            gap_bottom = round(high[-i], 2)
            if gap_top - gap_bottom > 0:
                bearish_fvgs.append({
                    "type": "bearish",
                    "gap_top": gap_top,
                    "gap_bottom": gap_bottom,
                    "gap_size": round(gap_top - gap_bottom, 2),
                    "distance_candles": i,
                })
    return {"bullish_fvg": bullish_fvgs[:2], "bearish_fvg": bearish_fvgs[:2]}

def detect_liquidity_zones(data, swing_window=5, n_lookback=20):
    from snr import detect_swing_high_low
    close = round(data["close"].iloc[-1], 2)
    swings = detect_swing_high_low(data, swing_window)
    recent_swings = [s for s in swings if s["index"] >= len(data) - n_lookback]
    buy_side = sorted([s["price"] for s in recent_swings if s["type"] == "SH"], reverse=True)
    sell_side = sorted([s["price"] for s in recent_swings if s["type"] == "SL"])
    swept = None
    for s in buy_side[:3]:
        if abs(close - s) <= 1.0:
            swept = ("buy_side_swept", s)
            break
    for s in sell_side[:3]:
        if abs(close - s) <= 1.0:
            swept = ("sell_side_swept", s)
            break
    return {
        "buy_side_liquidity": buy_side[:3],
        "sell_side_liquidity": sell_side[:3],
        "liquidity_sweep_detected": swept is not None,
        "sweep_type": swept[0] if swept else None,
        "sweep_level": swept[1] if swept else None,
        "current_price": close,
    }

def get_optimal_trade_entry(high_swing, low_swing):
    if not high_swing or not low_swing:
        return None
    range_size = high_swing - low_swing
    if range_size <= 0:
        return None
    ote_62 = round(high_swing - range_size * 0.62, 2)
    ote_79 = round(high_swing - range_size * 0.79, 2)
    return {"ote_62": ote_62, "ote_79": ote_79, "range": round(range_size, 2)}

def analyze_ict_smc(data):
    fvg = detect_fvg(data)
    ob = detect_order_blocks(data)
    liq = detect_liquidity_zones(data)
    killzone = get_killzone()
    return {
        "fvg": fvg,
        "order_blocks": ob,
        "liquidity": liq,
        "killzone": killzone,
        "has_fvg": len(fvg["bullish_fvg"]) > 0 or len(fvg["bearish_fvg"]) > 0,
        "has_ob": ob["total_detected"] > 0,
        "has_liquidity_sweep": liq["liquidity_sweep_detected"],
    }
