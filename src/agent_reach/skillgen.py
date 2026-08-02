from . import manifest as manifests
from . import registry

HEADER = """---
name: agent-reach
description: Read and search external sources through the channels installed on this machine. Use when the task needs content from a feed, a video, or another platform an installed channel covers.
---

# agent-reach

Installed channels only. Run `agent-reach doctor` first if a call fails; a channel can be
installed but unauthenticated.

Every command returns the same envelope, so the output shape does not change per channel.
Use `--max-tokens` whenever the source could be long.

```
agent-reach get <channel>.<command> <query> [--max-tokens N] [--limit N] [--json]
```
"""


def generate():
    available = manifests.available()
    installed = sorted(registry.load())
    lines = [HEADER, "## Channels", ""]
    if not installed:
        lines.append("None installed. Run `agent-reach list --all` to see what the index offers.")
        return "\n".join(lines) + "\n"
    for name in installed:
        entry = available.get(name)
        if entry is None:
            continue
        lines.append(f"### {name}")
        lines.append("")
        lines.append(entry.description)
        if entry.auth != "none":
            lines.append("")
            lines.append(
                f"Needs {entry.auth} auth, which runs as your own account. Check `agent-reach doctor` before relying on it."
            )
        lines.append("")
        for command in entry.commands.values():
            lines.append(f"- `agent-reach get {name}.{command.name} <query>`")
        lines.append("")
    return "\n".join(lines) + "\n"
