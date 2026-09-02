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
    _check_status(parsed)
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


def _check_status(parsed):
    # feedparser reports an HTTP 429 as bozo=False with no entries, which is
    # indistinguishable from a feed that is genuinely empty. Raising here also
    # keeps runner.run from caching the blocked response for the full TTL.
    status = parsed.get("status")
    if not isinstance(status, int) or status < 400:
        return
    if status == 429:
        raise RuntimeError(
            "rate limited (HTTP 429): the host is throttling this IP. Wait a few "
            "minutes and retry. An empty result here means blocked, not quiet."
        )
    if status in (401, 403):
        raise RuntimeError(f"the feed refused this request (HTTP {status})")
    if status == 404:
        raise RuntimeError(f"no feed at that URL (HTTP {status})")
    raise RuntimeError(f"could not read the feed (HTTP {status})")


def _strip_html(text):
    import html
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()
