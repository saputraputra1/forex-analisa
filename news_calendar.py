import cloudscraper
from datetime import datetime, timedelta
import time
import re

CACHE = {"data": None, "timestamp": 0}
CACHE_TTL = 300

FOREX_FACTORY_URL = "https://www.forexfactory.com/calendar?day="

scraper = None

def _get_scraper():
    global scraper
    if scraper is None:
        scraper = cloudscraper.create_scraper()
    return scraper

HIGH_IMPACT_EVENTS = [
    "Non-Farm Employment Change", "NFP", "Non Farm Payrolls",
    "CPI", "Consumer Price Index", "Core CPI",
    "FOMC", "Interest Rate Decision",
    "GDP", "Gross Domestic Product",
    "Unemployment", "Unemployment Rate",
    "Retail Sales", "Core Retail Sales",
    "ISM", "ISM Manufacturing", "ISM Services",
    "PPI", "Producer Price Index",
    "Federal Reserve", "Fed Chair",
    "Core PCE", "PCE",
    "Building Permits", "Housing Starts",
    "Industrial Production",
    "Consumer Confidence", "CB Consumer Confidence",
    "Philly Fed", "Empire State",
    "Trade Balance",
    "Existing Home Sales", "New Home Sales",
    "Durable Goods",
    "Michigan", "Consumer Sentiment",
    "Average Hourly Earnings",
    "Labor Market",
    "Average Weekly Hours",
    "Treasury", "10-y Bond Auction",
    "Jobless Claims",
    "ADP", "ADP Employment",
    "Factory Orders",
    "Wholesale Inventories",
]

IMPACT_MAP = {"red": "HIGH", "yel": "MEDIUM", "gre": "LOW"}

def _clean_text(text):
    return re.sub(r'[\ufffd\x00-\x08\x0b\x0c\x0e-\x1f\u200b\u200c\u200d\ufeff]', '', text).strip()

def _parse_html(html):
    events = []
    rows = re.findall(
        r'<tr[^>]*class="calendar__row[^"]*"[^>]*>.*?</tr>',
        html, re.DOTALL
    )
    for row in rows:
        if "calendar__row--day-breaker" in row or "calendar__row--no-event" in row:
            continue
        try:
            time_match = re.search(
                r'class="calendar__cell calendar__time">([\d:]+[ap]m)',
                row, re.DOTALL
            )
            currency_match = re.search(
                r'class="calendar__cell calendar__currency">([A-Z]{3})',
                row, re.DOTALL
            )
            event_match = re.search(
                r'class="calendar__event-title">([^<]+)',
                row, re.DOTALL
            )
            impact_match = re.search(
                r'icon--ff-impact-(red|yel|gre)',
                row
            )
            forecast_match = re.search(
                r'class="calendar__cell calendar__forecast">\s*([^<]*)',
                row, re.DOTALL
            )
            previous_match = re.search(
                r'class="calendar__cell calendar__previous">.*?<span>\s*([^<]*)</span>',
                row, re.DOTALL
            )
            if not (time_match and currency_match and event_match):
                continue
            currency = currency_match.group(1)
            if currency != "USD":
                continue
            event_name = _clean_text(event_match.group(1))
            raw_time = time_match.group(1)
            raw_impact = impact_match.group(1) if impact_match else "gre"
            impact = IMPACT_MAP.get(raw_impact, "LOW")
            if impact == "LOW":
                ll = event_name.lower()
                for kw in HIGH_IMPACT_EVENTS:
                    if kw.lower() in ll:
                        impact = "HIGH"
                        break
            forecast_raw = _clean_text(forecast_match.group(1)) if forecast_match else ""
            previous_raw = _clean_text(previous_match.group(1)) if previous_match and previous_match.group(1) else ""
            forecast = forecast_raw if forecast_raw else "—"
            previous = previous_raw if previous_raw else "—"
            events.append({
                "time": raw_time,
                "currency": "USD",
                "event": event_name,
                "impact": impact,
                "forecast": forecast,
                "previous": previous,
            })
        except Exception:
            continue
    return events

def fetch_calendar(date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    url = FOREX_FACTORY_URL + date
    try:
        resp = _get_scraper().get(url, timeout=20)
        if resp.status_code != 200:
            return []
        html = resp.text
    except Exception:
        return []
    return _parse_html(html)

def get_upcoming_events(hours_ahead=24, min_impact="HIGH"):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    if time.time() - CACHE["timestamp"] < CACHE_TTL and CACHE["data"]:
        events = CACHE["data"]
    else:
        events = fetch_calendar(today)
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        events += fetch_calendar(tomorrow)
        CACHE["data"] = events
        CACHE["timestamp"] = time.time()
    filtered = []
    seen = set()
    for e in events:
        try:
            hour, minute = e["time"].replace("am", "").replace("pm", "").split(":")
            hour = int(hour)
            minute = int(minute)
            if "pm" in e["time"] and hour != 12:
                hour += 12
            if "am" in e["time"] and hour == 12:
                hour = 0
            ev_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if ev_time < now:
                ev_time += timedelta(days=1)
            delta = (ev_time - now).total_seconds()
            dedup_key = f"{e['event']}_{e['time']}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            if 0 <= delta <= hours_ahead * 3600:
                if min_impact == "HIGH" and e["impact"] == "HIGH":
                    e["datetime"] = ev_time
                    e["minutes_until"] = int(delta / 60)
                    filtered.append(e)
                elif min_impact == "ALL":
                    e["datetime"] = ev_time
                    e["minutes_until"] = int(delta / 60)
                    filtered.append(e)
        except (ValueError, KeyError):
            continue
    filtered.sort(key=lambda x: x["minutes_until"])
    return filtered

def get_imminent_events(minutes_ahead=30):
    return get_upcoming_events(hours_ahead=1, min_impact="HIGH")
