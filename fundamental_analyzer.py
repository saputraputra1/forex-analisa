from datetime import datetime
import yfinance as yf

DXY_SYMBOL = "DX-Y.NYB"

def get_market_session(utc_hour=None):
    if utc_hour is None:
        utc_hour = datetime.utcnow().hour
    if 0 <= utc_hour < 5:
        return {"session": "Asia", "volatility": "low", "color": "\U0001f7e8"}
    if 5 <= utc_hour < 7:
        return {"session": "Asian-London Transition", "volatility": "medium", "color": "\U0001f7e0"}
    if 7 <= utc_hour < 10:
        return {"session": "London", "volatility": "high", "color": "\U0001f534"}
    if 10 <= utc_hour < 11:
        return {"session": "Silver Bullet (London-NY Overlap)", "volatility": "very_high", "color": "\U0001f525"}
    if 11 <= utc_hour < 13:
        return {"session": "London-NY Transition", "volatility": "high", "color": "\U0001f7e0"}
    if 13 <= utc_hour < 16:
        return {"session": "New York", "volatility": "high", "color": "\U0001f535"}
    if 16 <= utc_hour < 18:
        return {"session": "NY Afternoon", "volatility": "medium", "color": "\U0001f7e0"}
    return {"session": "Low Volume (Asia/Australia)", "volatility": "low", "color": "\U0001f7e8"}

def get_dxy_price():
    try:
        ticker = yf.Ticker(DXY_SYMBOL)
        data = ticker.history(period="1d", interval="5m")
        if not data.empty:
            return round(data["Close"].iloc[-1], 2)
    except Exception:
        pass
    return None

def get_dxy_trend(data_d=None):
    try:
        if data_d is None:
            ticker = yf.Ticker(DXY_SYMBOL)
            data_d = ticker.history(period="5d", interval="1h")
        if data_d.empty:
            return None
        closes = data_d["Close"].values
        if len(closes) < 10:
            return None
        if closes[-1] > closes[-10]:
            return "bullish"
        return "bearish"
    except Exception:
        return None

def analyze_fundamental(upcoming_events=None):
    session = get_market_session()
    dxy = get_dxy_price()
    dxy_trend = get_dxy_trend()
    imminent = None
    if upcoming_events and len(upcoming_events) > 0:
        imminent = upcoming_events[0]
    return {
        "session": session["session"],
        "volatility": session["volatility"],
        "dxy": dxy,
        "dxy_trend": dxy_trend,
        "imminent_news": imminent,
        "imminent_news_minutes": imminent["minutes_until"] if imminent else None,
        "imminent_news_event": imminent["event"] if imminent else None,
        "has_imminent_news": imminent is not None,
    }
