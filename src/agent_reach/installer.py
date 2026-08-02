import shutil
import subprocess

from .manifest import ManifestError


class InstallError(Exception):
    pass


def plan(manifest):
    needed = manifest.binary if manifest.kind == "cli" else manifest.backend.get("requires", "")
    if not needed:
        return None
    if shutil.which(needed):
        return None
    try:
        argv = manifest.install_command()
    except ManifestError as exc:
        raise InstallError(str(exc))
    if not argv:
        raise InstallError(
            f"channel '{manifest.name}' needs '{needed}' but declares no install command"
        )
    if not shutil.which(argv[0]):
        raise InstallError(f"'{argv[0]}' is not on PATH, so '{needed}' cannot be installed")
    return argv


def execute(argv):
    proc = subprocess.run(argv)
    if proc.returncode != 0:
        raise InstallError(f"{' '.join(argv)} exited {proc.returncode}")
