import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_reach import budget, cache, installer, manifest, registry, runner, skillgen  # noqa: E402
from agent_reach.channels import youtube  # noqa: E402
from agent_reach.envelope import Envelope, Item, render_text  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_REACH_HOME", str(tmp_path / "home"))


def test_index_parses():
    channels = manifest.available()
    assert {"rss", "youtube", "wporg"} <= set(channels)
    for entry in channels.values():
        assert entry.description
        assert entry.commands


def test_wporg_manifest_maps_fields():
    entry = manifest.get("wporg")
    reviews = entry.command("reviews")
    assert reviews.args == ["reviews", "{query}", "--json"]
    assert reviews.mapping["title"] == "title"
    assert reviews.mapping["engagement"]["stars"] == "rating"


def test_unknown_command_is_reported():
    entry = manifest.get("wporg")
    with pytest.raises(manifest.ManifestError) as exc:
        entry.command("nope")
    assert "has no command" in str(exc.value)


def test_install_verb_whitelist():
    entry = manifest.parse(
        {
            "name": "evil",
            "description": "x",
            "backend": {"type": "cli", "binary": "x", "install": {"verb": "sh", "package": "x"}},
        }
    )
    with pytest.raises(manifest.ManifestError):
        entry.install_command()


def test_install_rejects_shell_metacharacters():
    entry = manifest.parse(
        {
            "name": "evil",
            "description": "x",
            "backend": {
                "type": "cli",
                "binary": "x",
                "install": {"verb": "brew", "package": "x; rm -rf /"},
            },
        }
    )
    with pytest.raises(manifest.ManifestError):
        entry.install_command()


def test_install_command_is_argv_not_a_string():
    entry = manifest.get("wporg")
    assert entry.install_command() == [
        "go",
        "install",
        "github.com/jgalea/wporg/cmd/wporg@latest",
    ]


def test_truncate_keeps_head_and_tail():
    text = "A" * 400 + "B" * 400
    out, cut = budget.truncate_text(text, 50)
    assert cut
    assert out.startswith("A")
    assert out.endswith("B")
    assert len(out) < len(text)


def test_budget_drops_later_items():
    envelope = Envelope(
        channel="t",
        command="c",
        query="q",
        items=[Item(source="t", text="x" * 4000), Item(source="t", text="y" * 4000)],
    )
    budget.apply_budget(envelope, 200)
    assert envelope.truncated
    assert len(envelope.items) == 1


def test_budget_of_zero_is_a_noop():
    envelope = Envelope(channel="t", command="c", query="q", items=[Item(source="t", text="x" * 100)])
    budget.apply_budget(envelope, 0)
    assert not envelope.truncated
    assert len(envelope.items[0].text) == 100


def test_cache_roundtrip_and_expiry():
    envelope = Envelope(channel="t", command="c", query="q", items=[Item(source="t", title="hi")])
    cache.put("t", "c", "q", {}, envelope.to_dict())
    assert cache.get("t", "c", "q", {}, 60) is not None
    assert cache.get("t", "c", "q", {}, 0) is None
    assert cache.get("t", "c", "other", {}, 60) is None


def test_cache_clear_by_channel():
    for name in ("a", "b"):
        env = Envelope(channel=name, command="c", query="q", items=[])
        cache.put(name, "c", "q", {}, env.to_dict())
    assert cache.clear("a") == 1
    assert cache.get("b", "c", "q", {}, 60) is not None


def test_cli_backend_maps_json_to_envelope(tmp_path, monkeypatch):
    fake = tmp_path / "fakecli"
    payload = json.dumps(
        [{"title": "Great", "url": "https://example.com/1", "author": "sam", "content": "body", "rating": 5}]
    )
    fake.write_text(f"#!/bin/sh\ncat <<'EOF'\n{payload}\nEOF\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    entry = manifest.parse(
        {
            "name": "fake",
            "description": "x",
            "cache_ttl": 0,
            "backend": {"type": "cli", "binary": "fakecli"},
            "command": [
                {
                    "name": "reviews",
                    "args": ["reviews", "{query}"],
                    "map": {
                        "items": "$",
                        "title": "title",
                        "url": "url",
                        "author": "author",
                        "text": "content",
                        "engagement": {"stars": "rating"},
                    },
                }
            ],
        }
    )
    envelope = runner.run(entry, "reviews", "akismet", use_cache=False)
    assert len(envelope.items) == 1
    item = envelope.items[0]
    assert item.title == "Great"
    assert item.engagement == {"stars": 5}
    assert "Great" in render_text(envelope)


def test_cli_backend_reports_a_missing_binary():
    entry = manifest.parse(
        {
            "name": "ghost",
            "description": "x",
            "backend": {"type": "cli", "binary": "definitely-not-installed-xyz"},
            "command": [{"name": "go", "args": ["go"]}],
        }
    )
    with pytest.raises(runner.RunError) as exc:
        runner.run(entry, "go", "q", use_cache=False)
    assert "agent-reach install" in str(exc.value)


def test_rss_reads_a_local_feed():
    entry = manifest.get("rss")
    envelope = runner.run(entry, "feed", (FIXTURES / "feed.xml").as_uri(), use_cache=False)
    assert len(envelope.items) == 2
    assert envelope.items[0].title == "First post"
    assert "<p>" not in envelope.items[0].text
    assert "escaped" in envelope.items[1].text


def test_vtt_parsing_drops_timestamps_and_repeats():
    raw = (FIXTURES / "sample.vtt").read_text()
    text = youtube.parse_vtt(raw)
    assert "-->" not in text
    assert "WEBVTT" not in text
    assert text.splitlines() == ["hello there", "this is a test", "final line"]


def test_registry_and_skill_generation():
    registry.add("rss", {"auth": "none", "binary": ""})
    assert registry.is_installed("rss")
    skill = skillgen.generate()
    assert "agent-reach get rss.feed" in skill
    assert "youtube" not in skill
    assert registry.remove("rss")
    assert "None installed" in skillgen.generate()


def test_skill_flags_channels_that_use_your_account():
    registry.add("fake", {"auth": "cookie", "binary": ""})
    entry = manifest.parse(
        {
            "name": "fake",
            "description": "x",
            "auth": "cookie",
            "backend": {"type": "builtin", "module": "rss"},
            "command": [{"name": "read"}],
        }
    )
    original = manifest.available
    manifest.available = lambda: {"fake": entry}
    try:
        skill = skillgen.generate()
    finally:
        manifest.available = original
    assert "your own account" in skill


def test_builtin_without_its_binary_plans_an_install(monkeypatch):
    monkeypatch.setenv("PATH", "")
    entry = manifest.get("youtube")
    with pytest.raises(installer.InstallError):
        installer.plan(entry)
