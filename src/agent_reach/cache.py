import hashlib
import json
import time
from pathlib import Path

from .paths import cache_dir


def _key(channel, command, query, params):
    blob = json.dumps([channel, command, query, params], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:32]


def _path(channel, command, query, params):
    return cache_dir() / f"{_key(channel, command, query, params)}.json"


def get(channel, command, query, params, ttl):
    if ttl <= 0:
        return None
    path = _path(channel, command, query, params)
    if not path.exists():
        return None
    try:
        record = json.loads(path.read_text())
    except (ValueError, OSError):
        return None
    if time.time() - record.get("stored_at", 0) > ttl:
        return None
    return record.get("envelope")


def put(channel, command, query, params, envelope):
    path = _path(channel, command, query, params)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"stored_at": time.time(), "envelope": envelope}
    path.write_text(json.dumps(record))


def clear(channel=None):
    removed = 0
    for path in cache_dir().glob("*.json"):
        if channel:
            try:
                record = json.loads(path.read_text())
            except (ValueError, OSError):
                continue
            if record.get("envelope", {}).get("channel") != channel:
                continue
        path.unlink()
        removed += 1
    return removed
