from ..envelope import Item


def probe():
    try:
        import feedparser  # noqa: F401
    except ImportError:
        return False, "feedparser is not installed"
    return True, "feedparser"


def fetch(command, query, params):
    import feedparser

    if not query:
        raise ValueError("rss needs a feed URL")
    limit = int(params.get("limit", 20))
    parsed = feedparser.parse(query)
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"could not read the feed: {parsed.bozo_exception}")
    items = []
    for entry in parsed.entries[:limit]:
        body = ""
        if entry.get("content"):
            body = entry["content"][0].get("value", "")
        body = body or entry.get("summary", "")
        items.append(
            Item(
                source="rss",
                url=entry.get("link", ""),
                title=entry.get("title", ""),
                author=entry.get("author", ""),
                published_at=entry.get("published", entry.get("updated", "")),
                text=_strip_html(body),
            )
        )
    return items


def _strip_html(text):
    import html
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
