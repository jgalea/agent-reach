import json

from .paths import installed_file


def load():
    path = installed_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (ValueError, OSError):
        return {}


def save(state):
    path = installed_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def is_installed(name):
    return name in load()


def add(name, record):
    state = load()
    state[name] = record
    save(state)


def remove(name):
    state = load()
    existed = state.pop(name, None) is not None
    save(state)
    return existed
