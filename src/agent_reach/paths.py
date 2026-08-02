import os
from pathlib import Path


def home():
    override = os.environ.get("AGENT_REACH_HOME")
    return Path(override).expanduser() if override else Path.home() / ".agent-reach"


def cache_dir():
    return home() / "cache"


def taps_dir():
    return home() / "taps"


def installed_file():
    return home() / "installed.json"


def bundled_index():
    return Path(__file__).resolve().parent / "index"
