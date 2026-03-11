import re
import urllib.request
import urllib.parse
import json


def search(query: str, max_results: int = 5) -> str:
    """Route to best source based on query type."""
    q = query.lower()

    # Weather queries → wttr.in (free, no API key, accurate)
    if any(w in q for w in ["weather", "temperature", "forecast", "rain", "humidity", "climate"]):
        city = _extract_city(query)
        if city:
            return _get_weather(city)

    # Try DuckDuckGo instant answer first
    instant = _ddg_instant(query)
    if instant:
        return instant

    # Fall back to DDG scrape
    return _ddg_scrape(query, max_results)


def _extract_city(query: str) -> str:
    """Pull city name from a weather query."""
    q = query.lower()
    for word in ["weather in", "weather for", "temperature in", "forecast for", "forecast in"]:
        if word in q:
            city = q.split(word)[-1].strip()
            city = re.sub(r'[^\w\s]', '', city).strip()
            return city
    # fallback: last meaningful word
    words = [w for w in query.split() if w.lower() not in
             {"weather", "temperature", "forecast", "today", "now", "current", "whats", "what", "is", "the"}]
    return words[-1] if words else ""


def _get_weather(city: str) -> str:
    """Get weather from wttr.in — free, no API key needed."""
    try:
        encoded = urllib.parse.quote(city)
        url = f"https://wttr.in/{encoded}?format=j1"
        req = urllib.request.Request(url, headers={"User-Agent": "Lyra/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        current = data["current_condition"][0]
        area = data["nearest_area"][0]

        temp_c = current["temp_C"]
        feels_c = current["FeelsLikeC"]
        humidity = current["humidity"]
        desc = current["weatherDesc"][0]["value"]
        wind_kmph = current["windspeedKmph"]
        area_name = area["areaName"][0]["value"]
        country = area["country"][0]["value"]

        return (
            f"[Weather] {area_name}, {country}: {desc}, {temp_c}°C "
            f"(feels like {feels_c}°C), humidity {humidity}%, "
            f"wind {wind_kmph} km/h"
        )
    except Exception as e:
        return f"Weather fetch failed: {e}"


def _ddg_instant(query: str) -> str:
    """DuckDuckGo instant answer API."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Lyra/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        answer = data.get("Answer", "").strip()
        abstract = data.get("AbstractText", "").strip()
        definition = data.get("Definition", "").strip()

        if answer:
            return f"[Search] {answer}"
        if abstract:
            return f"[Search] {abstract}"
        if definition:
            return f"[Search] {definition}"

        topics = data.get("RelatedTopics", [])
        snippets = [t["Text"] for t in topics[:3] if isinstance(t, dict) and t.get("Text")]
        if snippets:
            return "[Search] " + " | ".join(snippets)

        return ""
    except Exception:
        return ""


def _ddg_scrape(query: str, max_results: int = 5) -> str:
    """Scrape DuckDuckGo HTML results."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)

        results = []
        for i, snippet in enumerate(snippets[:max_results]):
            clean = re.sub(r'<[^>]+>', '', snippet).strip()
            clean = re.sub(r'\s+', ' ', clean)
            if clean:
                title = re.sub(r'<[^>]+>', '', titles[i]).strip() if i < len(titles) else ""
                results.append(f"{title}: {clean}" if title else clean)

        return "[Search]\n" + "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search failed: {e}"