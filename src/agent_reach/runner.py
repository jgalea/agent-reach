import importlib
import json
import shutil
import subprocess

from . import budget, cache
from .envelope import Envelope, Item
from .manifest import ManifestError


class RunError(Exception):
    pass


def _resolve(data, path):
    if path in ("$", "", None):
        return data
    current = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _as_items(raw, mapping, source):
    rows = _resolve(raw, mapping.get("items", "$"))
    if rows is None:
        return []
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        return []
    engagement_map = mapping.get("engagement", {})
    items = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        item = Item(source=source)
        for field in ("url", "title", "author", "published_at", "text"):
            key = mapping.get(field)
            if key:
                value = _resolve(row, key)
                if value is not None:
                    setattr(item, field, str(value))
        for label, key in engagement_map.items():
            value = _resolve(row, key)
            if value is not None:
                item.engagement[label] = value
        items.append(item)
    return items


def _run_cli(manifest, command, query, params):
    if not shutil.which(manifest.binary):
        raise RunError(
            f"'{manifest.binary}' is not on PATH. Run: agent-reach install {manifest.name}"
        )
    argv = [manifest.binary]
    for arg in command.args:
        argv.append(arg.replace("{query}", query))
    for key, flag in command.params.items():
        if key in params:
            argv.extend([flag, str(params[key])])
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        raise RunError(f"{manifest.binary} exited {proc.returncode}: {detail[-1] if detail else ''}")
    try:
        raw = json.loads(proc.stdout or "null")
    except ValueError:
        raise RunError(f"{manifest.binary} did not return JSON")
    return _as_items(raw, command.mapping, manifest.name)


def _builtin_module(manifest):
    module_name = manifest.backend.get("module", manifest.name)
    try:
        return importlib.import_module(f".channels.{module_name}", package="agent_reach")
    except ImportError as exc:
        raise RunError(f"channel '{manifest.name}' has no builtin module: {exc}")


def _run_builtin(manifest, command, query, params):
    module = _builtin_module(manifest)
    return module.fetch(command.name, query, params)


def run(manifest, command_name=None, query="", params=None, use_cache=True, max_tokens=0):
    params = params or {}
    command = manifest.command(command_name)
    cached = cache.get(manifest.name, command.name, query, params, manifest.cache_ttl) if use_cache else None
    if cached is not None:
        envelope = Envelope.from_dict(cached)
        envelope.cached = True
    else:
        if manifest.kind == "builtin":
            items = _run_builtin(manifest, command, query, params)
        else:
            items = _run_cli(manifest, command, query, params)
        limit = params.get("limit")
        if limit:
            items = items[: int(limit)]
        envelope = Envelope(
            channel=manifest.name, command=command.name, query=query, items=items
        )
        if use_cache and manifest.cache_ttl > 0:
            cache.put(manifest.name, command.name, query, params, envelope.to_dict())
    return budget.apply_budget(envelope, max_tokens)


def probe(manifest):
    if manifest.kind == "builtin":
        module = _builtin_module(manifest)
        checker = getattr(module, "probe", None)
        if checker is None:
            return True, "builtin"
        return checker()
    binary = manifest.binary
    path = shutil.which(binary)
    if not path:
        return False, f"'{binary}' not on PATH"
    args = manifest.backend.get("probe", {}).get("args", ["--version"])
    try:
        proc = subprocess.run([binary, *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, f"{binary} {' '.join(args)} exited {proc.returncode}"
    version = (proc.stdout or proc.stderr).strip().splitlines()
    return True, version[0][:60] if version else path
