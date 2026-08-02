from . import manifest as manifests
from . import registry, runner


def check(names=None):
    available = manifests.available()
    installed = registry.load()
    targets = names or sorted(installed) or []
    rows = []
    for name in targets:
        entry = available.get(name)
        if entry is None:
            rows.append({"channel": name, "ok": False, "auth": "?", "detail": "not in the index"})
            continue
        try:
            ok, detail = runner.probe(entry)
        except Exception as exc:
            ok, detail = False, str(exc)
        rows.append(
            {
                "channel": name,
                "ok": ok,
                "auth": entry.auth,
                "detail": detail,
                "installed": name in installed,
            }
        )
    return rows


def exit_code(rows):
    if not rows:
        return 0
    return 0 if all(row["ok"] for row in rows) else 1
