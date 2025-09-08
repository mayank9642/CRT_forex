import requests
from datetime import datetime, timedelta

# Trading Economics free API endpoint
API_URL = "https://api.tradingeconomics.com/calendar"
API_KEY = "guest:guest"  # Free public key

# List of high-impact event keywords (can be expanded)
HIGH_IMPACT_KEYWORDS = [
    "Non Farm Payrolls", "FOMC", "Fed Interest Rate", "CPI", "Unemployment Rate", "GDP", "Core CPI", "Retail Sales", "PPI", "ISM", "Fed Chair", "ECB", "BOE", "BOJ", "Interest Rate"
]

# Countries relevant for XAUUSD (Gold)
RELEVANT_COUNTRIES = ["United States", "China", "Euro Area", "Japan", "United Kingdom"]

# Minutes before/after news to block trading (can be set per session)
NEWS_WINDOW_MINUTES = 30  # Default, can be overridden
SESSION_NEWS_WINDOWS = {
    # Example: 'London': 45, 'NY': 60
}

def get_upcoming_high_impact_news():
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=NEWS_WINDOW_MINUTES)
    window_end = now + timedelta(minutes=NEWS_WINDOW_MINUTES)
    params = {
        "c": API_KEY,
        "d1": window_start.strftime("%Y-%m-%dT%H:%M"),
        "d2": window_end.strftime("%Y-%m-%dT%H:%M"),
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=10)
        events = resp.json() if resp.status_code == 200 else []
    except Exception as e:
        print(f"News API error: {e}")
        return []
    high_impact_events = []
    for event in events:
        if event.get("country") in RELEVANT_COUNTRIES:
            if event.get("impact", "") == "High" or any(k in event.get("event", "") for k in HIGH_IMPACT_KEYWORDS):
                # Check time window
                try:
                    event_time = datetime.strptime(event["date"], "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    continue
                if window_start <= event_time <= window_end:
                    high_impact_events.append(event)
    return high_impact_events

def is_news_blocking(session_name=None):
    """
    Returns True if there is high-impact news within the window for the current or given session.
    """
    global NEWS_WINDOW_MINUTES
    window = NEWS_WINDOW_MINUTES
    if session_name and session_name in SESSION_NEWS_WINDOWS:
        window = SESSION_NEWS_WINDOWS[session_name]
    NEWS_WINDOW_MINUTES = window
    events = get_upcoming_high_impact_news()
    if events:
        print("High-impact news detected:")
        for e in events:
            print(f"{e['date']} | {e['country']} | {e['event']} | Impact: {e.get('impact', '')}")
        return True
    return False
