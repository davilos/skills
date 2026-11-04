#!/usr/bin/env python3
"""Build the review page of a document, a plan or a feature: picks the profile, then its engine.

Usage:
    python3 build_page.py <target>... --out <file.html> [--profile P] [--lang en|pt]
    python3 build_page.py <target>... --mark-published [--url <artifact url>] [--profile P]

<target>: a Markdown file; several (one tab each); a tlc-spec-lean `plan.md`; or a tlc-spec-driven
feature folder (`.specs/features/<slug>`, or any of its files).
--profile: the profile the user named (generic, tlc-spec-lean, tlc-spec-driven). It wins over
detection; the build warns when detection disagrees.

Prints the profile and why first. Exit 1: a piece of the document did not reach the page data, or
the review state contradicts the document. Exit 3: two profiles fit; ask the user and pass --profile.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
import profiles  # noqa: E402


def resolve(targets: list[str], forced: str | None) -> dict | None:
    """The profile for these targets, announced on stderr; None (and a message) when it cannot."""
    try:
        info = profiles.detect(targets, forced, None if forced else profiles.recorded_profile(targets))
    except profiles.ProfileError as e:
        print(f"build_page: {e}", file=sys.stderr)
        info = None
        if str(e).startswith("ambiguous"):
            sys.exit(3)
        return None
    extra = f" {info['version']}" if info.get("version") else ""
    print(f"  PROFILE {info['profile']}{extra} ({info['reason']})", file=sys.stderr)
    if info.get("warn"):
        print(f"  WARN  {info['warn']}", file=sys.stderr)
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", nargs="+")
    ap.add_argument("--out", help="the HTML file to write")
    ap.add_argument("--profile", choices=["generic", "tlc-spec-lean", "tlc-spec-driven"])
    ap.add_argument("--lang", choices=["en", "pt"], help="page language (default: the state's, else detected from the first file)")
    ap.add_argument("--mark-published", action="store_true", help="record the hash of what just went live")
    ap.add_argument("--url", help="with --mark-published: the artifact link, stored the first time")
    args = ap.parse_args()
    if not args.out and not args.mark_published:
        ap.error("pass --out <file.html> or --mark-published")

    info = resolve(args.target, args.profile)
    if not info:
        return 1
    sp = profiles.state_path(info)

    if info["profile"] == "tlc-spec-lean":
        import lean_build
        feat = Path(info["feature"])
        if args.mark_published and args.url:
            import json
            st = json.loads(sp.read_text(encoding="utf-8")) if sp.is_file() else {}
            st["artifact_url"] = args.url
            sp.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        argv = ["--root", str(feat.parent.parent.parent), "--data", str(sp), feat.name]
        argv += ["--mark-published"] if args.mark_published else ["--out", args.out]
        sys.argv = ["build_page.py"] + argv
        return lean_build.main()

    import doc_build
    if args.mark_published:
        return doc_build.mark_published(info, sp, args.url, args.lang)
    return doc_build.build(info, sp, Path(args.out), args.lang)


if __name__ == "__main__":
    sys.exit(main())
