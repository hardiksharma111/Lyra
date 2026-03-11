import re
import urllib.request
import urllib.parse
import json


def search(query: str, max_results: int = 5) -> str:
    """Search the web via DuckDuckGo instant answer API + scrape fallback."""
    try:
        # Try DuckDuckGo instant answers first
        instant = _ddg_instant(query)
        if instant:
            return instant

        # Fall back to DDG HTML scrape
        return _ddg_scrape(query, max_results)

    except Exception as e:
        return f"Search failed: {e}"


def _ddg_instant(query: str) -> str:
    """DuckDuckGo instant answer API — best for factual one-liners."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "Lyra/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())

        abstract = data.get("AbstractText", "").strip()
        answer = data.get("Answer", "").strip()
        definition = data.get("Definition", "").strip()

        if answer:
            return f"[Search] {answer}"
        if abstract:
            return f"[Search] {abstract}"
        if definition:
            return f"[Search] {definition}"

        # Try related topics
        topics = data.get("RelatedTopics", [])
        snippets = []
        for t in topics[:3]:
            if isinstance(t, dict) and t.get("Text"):
                snippets.append(t["Text"])
        if snippets:
            return "[Search] " + " | ".join(snippets)

        return ""
    except Exception:
        return ""


def _ddg_scrape(query: str, max_results: int = 5) -> str:
    """Scrape DuckDuckGo HTML results as fallback."""
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Extract snippets from result blocks
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        titles = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)

        results = []
        for i, snippet in enumerate(snippets[:max_results]):
            clean = re.sub(r'<[^>]+>', '', snippet).strip()
            clean = re.sub(r'\s+', ' ', clean)
            if clean:
                title = ""
                if i < len(titles):
                    title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                if title:
                    results.append(f"{title}: {clean}")
                else:
                    results.append(clean)

        if results:
            return "[Search]\n" + "\n".join(results)

        return "No results found."
    except Exception as e:
        return f"Search scrape failed: {e}"