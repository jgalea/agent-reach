import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .paths import bundled_index, taps_dir

INSTALL_VERBS = {
    "uv": ["uv", "tool", "install", "{package}"],
    "pipx": ["pipx", "install", "{package}"],
    "go": ["go", "install", "{package}"],
    "brew": ["brew", "install", "{package}"],
}

SAFE_PACKAGE = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_/@:+="
)

AUTH_KINDS = {"none", "cookie", "token", "oauth"}


class ManifestError(Exception):
    pass


@dataclass
class Command:
    name: str
    args: list = field(default_factory=list)
    mapping: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)


@dataclass
class Manifest:
    name: str
    description: str
    auth: str
    cache_ttl: int
    backend: dict
    commands: dict
    source: Path = None

    @property
    def kind(self):
        return self.backend.get("type", "cli")

    @property
    def binary(self):
        return self.backend.get("binary", "")

    @property
    def install(self):
        return self.backend.get("install", {})

    def command(self, name=None):
        if not self.commands:
            raise ManifestError(f"channel '{self.name}' declares no commands")
        if name is None:
            return next(iter(self.commands.values()))
        if name not in self.commands:
            known = ", ".join(self.commands)
            raise ManifestError(f"channel '{self.name}' has no command '{name}' (has: {known})")
        return self.commands[name]

    def install_command(self):
        spec = self.install
        if not spec:
            return None
        verb = spec.get("verb")
        package = spec.get("package", "")
        if verb not in INSTALL_VERBS:
            raise ManifestError(f"channel '{self.name}' uses install verb '{verb}', which is not allowed")
        if not package or set(package) - SAFE_PACKAGE:
            raise ManifestError(f"channel '{self.name}' has an unsafe package string")
        return [part.replace("{package}", package) for part in INSTALL_VERBS[verb]]


def parse(data, source=None):
    for key in ("name", "description"):
        if key not in data:
            raise ManifestError(f"manifest missing required key '{key}' ({source})")
    auth = data.get("auth", "none")
    if auth not in AUTH_KINDS:
        raise ManifestError(f"channel '{data['name']}' declares unknown auth '{auth}'")
    backend = data.get("backend", {})
    if backend.get("type", "cli") not in ("cli", "builtin"):
        raise ManifestError(f"channel '{data['name']}' declares unknown backend type")
    commands = {}
    for entry in data.get("command", []):
        commands[entry["name"]] = Command(
            name=entry["name"],
            args=entry.get("args", []),
            mapping=entry.get("map", {}),
            params=entry.get("params", {}),
        )
    return Manifest(
        name=data["name"],
        description=data["description"],
        auth=auth,
        cache_ttl=int(data.get("cache_ttl", 0)),
        backend=backend,
        commands=commands,
        source=source,
    )


def load_file(path):
    with open(path, "rb") as handle:
        return parse(tomllib.load(handle), source=path)


def search_paths():
    paths = [bundled_index()]
    taps = taps_dir()
    if taps.is_dir():
        paths.extend(sorted(p for p in taps.iterdir() if p.is_dir()))
    return [p for p in paths if p.is_dir()]


def available():
    found = {}
    for directory in search_paths():
        for path in sorted(directory.glob("*.toml")):
            manifest = load_file(path)
            found.setdefault(manifest.name, manifest)
    return found


def get(name):
    manifest = available().get(name)
    if manifest is None:
        raise ManifestError(f"no channel named '{name}' in the index")
    return manifest
