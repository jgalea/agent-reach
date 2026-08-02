from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Item:
    source: str
    url: str = ""
    title: str = ""
    author: str = ""
    published_at: str = ""
    text: str = ""
    engagement: dict = field(default_factory=dict)
    children: list = field(default_factory=list)


@dataclass
class Envelope:
    channel: str
    command: str
    query: str
    fetched_at: str = field(default_factory=now_iso)
    cached: bool = False
    truncated: bool = False
    items: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        items = [Item(**i) for i in data.get("items", [])]
        return cls(
            channel=data["channel"],
            command=data.get("command", ""),
            query=data.get("query", ""),
            fetched_at=data.get("fetched_at", now_iso()),
            cached=data.get("cached", False),
            truncated=data.get("truncated", False),
            items=items,
        )


def render_text(envelope):
    lines = [f"# {envelope.channel}:{envelope.command} — {envelope.query}".rstrip(" —")]
    if envelope.cached:
        lines.append(f"(cached, fetched {envelope.fetched_at})")
    for item in envelope.items:
        lines.append("")
        heading = item.title or item.url or item.source
        lines.append(f"## {heading}")
        meta = [p for p in (item.author, item.published_at, item.url) if p]
        if meta:
            lines.append("  ".join(meta))
        if item.engagement:
            lines.append(
                "  ".join(f"{k}: {v}" for k, v in item.engagement.items() if v not in (None, ""))
            )
        if item.text:
            lines.append("")
            lines.append(item.text)
        for child in item.children:
            lines.append("")
            lines.append(f"  > {child.get('author', '')}: {child.get('text', '')}".rstrip())
    if envelope.truncated:
        lines.append("")
        lines.append("[output truncated to fit the token budget]")
    return "\n".join(lines)
