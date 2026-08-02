<div align="center">

# agent-reach

[![License](https://img.shields.io/badge/LICENSE-MIT-5C9E31?style=for-the-badge)](LICENSE)
[![Python](https://img.shields.io/badge/PYTHON-3.11+-3776AB?style=for-the-badge)](https://www.python.org/)
[![Built by](https://img.shields.io/badge/BUILT%20BY-JEAN%20GALEA-8A2BE2?style=for-the-badge)](https://github.com/jgalea)

**Give an agent the channels it needs, and only those.**

</div>

Most tools that give an agent access to external sources ship every platform at once. You install twelve
integrations to use two, and the agent carries instructions for all twelve in its context on every run.

agent-reach inverts that. Channels install one at a time from an index. Each one is a manifest rather than
code, so adding a channel is a few lines of TOML over a CLI that already exists. Everything returns the same
envelope, responses cache to disk, and `--max-tokens` bounds what reaches the model.

Nothing runs in the cloud and nothing is metered.

## Install

```bash
uv tool install agent-reach
```

Then install the channels you want:

```bash
agent-reach install rss
agent-reach install youtube
```

`install` runs a pinned command from a fixed set of verbs (`uv`, `pipx`, `go`, `brew`). Manifests cannot
supply shell. Use `--dry-run` to see the exact command first.

## Use

```bash
$ agent-reach get rss.feed https://wpmayor.com/feed/ --limit 3
$ agent-reach get youtube.transcript "https://youtu.be/VIDEO" --max-tokens 4000
$ agent-reach get wporg.reviews akismet --json
```

Every read command accepts `--json`, `--limit`, `--max-tokens` and `--no-cache`.

Check what is actually working before relying on it:

```bash
$ agent-reach doctor
ok   rss          auth:none    feedparser
ok   youtube      auth:none    yt-dlp 2026.07.28
DOWN wporg        auth:none    'wporg' not on PATH
```

`doctor --json` is meant for agents, and the exit code is non-zero when any channel is down.

## Channels

| Channel | Backend | Auth |
|---|---|---|
| `rss` | feedparser | none |
| `youtube` | yt-dlp | none |

The index stays small on purpose. Channels you add yourself live in a tap, described below.

## Writing a channel

A channel over an existing CLI that emits JSON is a manifest and nothing else:

```toml
name = "reviews-cli"
description = "Product reviews from a CLI that already speaks JSON."
auth = "none"
cache_ttl = 1800

[backend]
type = "cli"
binary = "reviews-cli"

[backend.install]
verb = "go"
package = "github.com/you/reviews-cli/cmd/reviews-cli@latest"

[backend.probe]
args = ["--help"]

[[command]]
name = "recent"
args = ["reviews", "{query}", "--json"]

[command.map]
items = "$"
title = "title"
url = "url"
author = "author"
text = "text"
published_at = "created_at"

[command.map.engagement]
stars = "rating"
```

Declare `[command.params]` to map a flag through (`limit = "--limit"`). Anything undeclared is never
forwarded to the binary, so a channel cannot be talked into passing arbitrary flags.

Drop it in `~/.agent-reach/taps/<name>/` and it shows up in `agent-reach list --all`. A tap is any directory
of manifests, so private channels stay private.

Channels needing a login declare `auth = "cookie"`, and both `install` and `doctor` say so. Those run as your
own account against platforms that ban for automation, so treat them as a deliberate choice.

## Agent skill

```bash
agent-reach skill --write ~/.claude/skills/agent-reach/SKILL.md
```

The generated skill documents installed channels only, so context stays proportional to what you use.
Regenerate it after installing or removing one.

## License

MIT
