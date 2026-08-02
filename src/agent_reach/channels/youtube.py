import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..envelope import Item

TIMESTAMP = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d{3} -->")
TAG = re.compile(r"<[^>]+>")


def probe():
    path = shutil.which("yt-dlp")
    if not path:
        return False, "'yt-dlp' not on PATH"
    proc = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
    if proc.returncode != 0:
        return False, "yt-dlp --version failed"
    return True, f"yt-dlp {proc.stdout.strip()}"


def fetch(command, query, params):
    if not query:
        raise ValueError("youtube needs a video URL or id")
    meta = _metadata(query)
    item = Item(
        source="youtube",
        url=meta.get("webpage_url", query),
        title=meta.get("title", ""),
        author=meta.get("uploader", ""),
        published_at=_date(meta.get("upload_date", "")),
        engagement={
            "views": meta.get("view_count"),
            "likes": meta.get("like_count"),
            "duration_s": meta.get("duration"),
        },
    )
    if command == "transcript":
        item.text = _transcript(query, params.get("lang", "en"))
        if not item.text:
            item.text = meta.get("description", "")
    else:
        item.text = meta.get("description", "")
    return [item]


def _metadata(target):
    proc = subprocess.run(
        ["yt-dlp", "-J", "--no-warnings", "--skip-download", target],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "yt-dlp failed")
    return json.loads(proc.stdout or "{}")


def _transcript(target, lang):
    with tempfile.TemporaryDirectory() as workdir:
        proc = subprocess.run(
            [
                "yt-dlp",
                "--skip-download",
                "--write-auto-subs",
                "--write-subs",
                "--sub-langs",
                f"{lang}.*,{lang}",
                "--sub-format",
                "vtt",
                "--no-warnings",
                "-o",
                str(Path(workdir) / "%(id)s.%(ext)s"),
                target,
            ],
            capture_output=True,
            text=True,
        )
        files = sorted(Path(workdir).glob("*.vtt"))
        if not files:
            if proc.returncode != 0:
                detail = (proc.stderr or "").strip().splitlines()
                raise RuntimeError(detail[-1] if detail else "yt-dlp failed")
            return ""
        return parse_vtt(files[0].read_text(encoding="utf-8", errors="replace"))


def parse_vtt(raw):
    lines = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if TIMESTAMP.match(line) or line.isdigit():
            continue
        line = TAG.sub("", line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return "\n".join(lines)


def _date(value):
    if len(value) == 8 and value.isdigit():
        return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    return value
