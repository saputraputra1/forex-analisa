import requests
from datetime import datetime, timedelta
import time
import re

CACHE = {"data": None, "timestamp": 0}
CACHE_TTL = 300

FOREX_FACTORY_URL = "https://www.forexfactory.com/calendar?day="

HIGH_IMPACT_EVENTS = [
    "Non-Farm Employment Change", "NFp", "Non Farm Payrolls",
    "CPI", "Consumer Price Index", "Core CPI",
    "FOMC", "Interest Rate Decision",
    "GDP", "Gross Domestic Product",
    "Unemployment", "Unemployment Rate",
    "Retail Sales", "Core Retail Sales",
    "ISM", "ISM Manufacturing", "ISM Services",
    "PPI", "Producer Price Index",
    "Federal Reserve", "Fed Chair",
    "Treasury", "10-y Bond Auction",
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
]

IMPACT_KEYWORDS = {
    "HIGH": ["NFP", "Non-Farm", "CPI", "FOMC", "GDP", "Unemployment",
             "Interest Rate", "Fed Chair", "Retail Sales", "Employment"],
    "MEDIUM": ["ISM", "PPI", "GDP", "Housing", "Consumer Confidence",
               "Philly Fed", "Durable Goods", "Trade Balance"],
}

def _filter_high_impact(events):
    result = []
    for e in events:
        name = e.get("event", "").lower()
        for kw in HIGH_IMPACT_EVENTS:
            if kw.lower() in name:
                e["impact"] = "HIGH"
                result.append(e)
                break
    return result

def fetch_calendar(date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    url = FOREX_FACTORY_URL + date
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return []
    except Exception:
        return []
    events = _parse_html(resp.text)
    return events

def _parse_html(html):
    events = []
    rows = re.findall(r'<tr[^>]*class="calendar__row[^"]*"[^>]*>(.*?)</tr>', html, re.DOTALL)
    for row in rows:
        try:
            time_match = re.search(r'class="calendar__time[^"]*"[^>]*>.*?(\d{2}:\d{2})', row, re.DOTALL)
            currency_match = re.search(r'class="calendar__currency[^"]*"[^>]*>.*?<span[^>]*>(USD|EUR|GBP|JPY|AUD|NZD|CAD|CHF)</span>', row, re.DOTALL)
            event_match = re.search(r'class="calendar__event[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', row, re.DOTALL)
            impact_match = re.search(r'class="calendar__impact[^"]*"[^>]*>.*?(icon--impact-(high|medium|low))', row, re.DOTALL)
            forecast_match = re.search(r'class="calendar__forecast[^"]*"[^>]*>(.*?)</td>', row, re.DOTALL)
            previous_match = re.search(r'class="calendar__previous[^"]*"[^>]*>(.*?)</td>', row, re.DOTALL)
            if time_match and event_match and currency_match:
                event_name = re.sub(r'<[^>]+>', '', event_match.group(1)).strip()
                currency = currency_match.group(1)
                if currency != "USD":
                    continue
                impact = "LOW"
                impact_text = impact_match.group(2).lower() if impact_match else ""
                if impact_text == "high":
                    impact = "HIGH"
                elif impact_text == "medium":
                    impact = "MEDIUM"
                if impact == "LOW":
                    ll = event_name.lower()
                    for kw in HIGH_IMPACT_EVENTS:
                        if kw.lower() in ll:
                            impact = "HIGH"
                            break
                forecast = re.sub(r'<[^>]+>', '', forecast_match.group(1)).strip() if forecast_match else "—"
                previous = re.sub(r'<[^>]+>', '', previous_match.group(1)).strip() if previous_match else "—"
                events.append({
                    "time": time_match.group(1),
                    "currency": "USD",
                    "event": event_name,
                    "impact": impact,
                    "forecast": forecast,
                    "previous": previous,
                })
        except Exception:
            continue
    return events

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
    for e in events:
        try:
            ev_time = datetime.strptime(f"{today} {e['time']}", "%Y-%m-%d %H:%M")
            if ev_time < now:
                ev_time += timedelta(days=1)
            delta = (ev_time - now).total_seconds()
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
