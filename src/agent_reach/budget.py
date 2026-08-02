CHARS_PER_TOKEN = 4
ELLIPSIS = "\n\n[... middle of this item omitted ...]\n\n"


def estimate_tokens(text):
    return len(text) // CHARS_PER_TOKEN


def truncate_text(text, max_tokens):
    limit = max_tokens * CHARS_PER_TOKEN
    if len(text) <= limit or limit <= len(ELLIPSIS):
        return text[:limit], len(text) > limit
    keep = limit - len(ELLIPSIS)
    head = int(keep * 0.7)
    tail = keep - head
    return text[:head] + ELLIPSIS + text[-tail:], True


def apply_budget(envelope, max_tokens):
    if not max_tokens or max_tokens <= 0:
        return envelope
    spent = 0
    kept = []
    truncated = False
    for item in envelope.items:
        overhead = estimate_tokens(item.title + item.url + item.author)
        remaining = max_tokens - spent - overhead
        if remaining <= 0:
            truncated = True
            break
        if estimate_tokens(item.text) > remaining:
            item.text, _ = truncate_text(item.text, remaining)
            truncated = True
        spent += overhead + estimate_tokens(item.text)
        kept.append(item)
        if spent >= max_tokens:
            truncated = truncated or len(kept) < len(envelope.items)
            break
    envelope.items = kept
    envelope.truncated = envelope.truncated or truncated
    return envelope
