import argparse
import json
import sys
from pathlib import Path

from . import cache, doctor, installer, registry, runner, skillgen
from . import manifest as manifests
from .envelope import render_text


def _fail(message):
    print(f"agent-reach: {message}", file=sys.stderr)
    return 2


def cmd_list(args):
    available = manifests.available()
    installed = registry.load()
    names = sorted(available) if args.all else sorted(installed)
    if not names:
        print("No channels installed. `agent-reach list --all` shows the index.")
        return 0
    for name in names:
        entry = available[name]
        mark = "installed" if name in installed else "-"
        auth = "" if entry.auth == "none" else f"  auth:{entry.auth}"
        print(f"{name:<12} {mark:<10}{auth}  {entry.description}")
    return 0


def cmd_install(args):
    try:
        entry = manifests.get(args.channel)
        argv = installer.plan(entry)
    except (manifests.ManifestError, installer.InstallError) as exc:
        return _fail(str(exc))
    if args.dry_run:
        print(" ".join(argv) if argv else f"nothing to install for {args.channel}")
        return 0
    if argv:
        print(f"installing {entry.binary}: {' '.join(argv)}")
        try:
            installer.execute(argv)
        except installer.InstallError as exc:
            return _fail(str(exc))
    ok, detail = runner.probe(entry)
    registry.add(args.channel, {"auth": entry.auth, "binary": entry.binary})
    print(f"{args.channel}: {'ready' if ok else 'installed but not working'} ({detail})")
    if entry.auth != "none":
        print(f"note: this channel authenticates as your own account ({entry.auth}).")
    return 0 if ok else 1


def cmd_remove(args):
    if not registry.remove(args.channel):
        return _fail(f"'{args.channel}' is not installed")
    cache.clear(args.channel)
    print(f"removed {args.channel}")
    return 0


def cmd_doctor(args):
    rows = doctor.check(args.channels or None)
    if args.json:
        print(json.dumps(rows, indent=2))
    elif not rows:
        print("No channels installed.")
    else:
        for row in rows:
            state = "ok " if row["ok"] else "DOWN"
            print(f"{state} {row['channel']:<12} auth:{row['auth']:<7} {row['detail']}")
    return doctor.exit_code(rows)


def cmd_get(args):
    channel, _, command = args.target.partition(".")
    try:
        entry = manifests.get(channel)
    except manifests.ManifestError as exc:
        return _fail(str(exc))
    params = {}
    if args.limit:
        params["limit"] = args.limit
    if args.lang:
        params["lang"] = args.lang
    try:
        envelope = runner.run(
            entry,
            command or None,
            args.query,
            params,
            use_cache=not args.no_cache,
            max_tokens=args.max_tokens,
        )
    except (runner.RunError, manifests.ManifestError) as exc:
        return _fail(str(exc))
    except Exception as exc:
        return _fail(f"{channel}: {exc}")
    if args.json:
        print(json.dumps(envelope.to_dict(), indent=2))
    else:
        print(render_text(envelope))
    return 0


def cmd_skill(args):
    content = skillgen.generate()
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(content)
        print(f"wrote {args.write}")
    else:
        print(content, end="")
    return 0


def cmd_cache(args):
    removed = cache.clear(args.channel)
    print(f"cleared {removed} cached {'entry' if removed == 1 else 'entries'}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="agent-reach", description="Install only the channels you need.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list installed channels")
    p.add_argument("--all", action="store_true", help="list everything in the index")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("install", help="install a channel")
    p.add_argument("channel")
    p.add_argument("--dry-run", action="store_true", help="print the install command and stop")
    p.set_defaults(func=cmd_install)

    p = sub.add_parser("remove", help="remove a channel and its cache")
    p.add_argument("channel")
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("doctor", help="check which channels are working")
    p.add_argument("channels", nargs="*")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("get", help="read from a channel")
    p.add_argument("target", help="channel or channel.command")
    p.add_argument("query", nargs="?", default="")
    p.add_argument("--max-tokens", type=int, default=0)
    p.add_argument("--limit", type=int)
    p.add_argument("--lang")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("skill", help="generate the agent skill for installed channels")
    p.add_argument("--write", type=Path)
    p.set_defaults(func=cmd_skill)

    p = sub.add_parser("cache", help="clear cached responses")
    p.add_argument("--channel")
    p.set_defaults(func=cmd_cache)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
