#!/usr/bin/env python3
"""The optional UI preview of a tlc-spec-lean plan: before/after mockups of the screens it changes.

Usage:
    python3 build_preview.py <plan.md or feature folder> --detect
    python3 build_preview.py <plan.md or feature folder> --out <file.html>
    python3 build_preview.py <plan.md or feature folder> --mark-published [--url <artifact url>]

--detect prints `ui: yes` (front-end files and criteria about what the user sees), `ui: code-only`
or `ui: no`. The preview's data lives in `.specs/features/<slug>/ui-preview.json` and its fragments in
`ui-preview/` (references/ui-preview.md). Only tlc-spec-lean plans have a preview.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
import profiles  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target")
    ap.add_argument("--detect", action="store_true", help="say whether the plan changes the screen")
    ap.add_argument("--out", help="the HTML file to write")
    ap.add_argument("--mark-published", action="store_true", help="record the plan that just went live")
    ap.add_argument("--url", help="with --mark-published: the preview's artifact link, stored the first time")
    args = ap.parse_args()
    if not (args.detect or args.out or args.mark_published):
        ap.error("pass --detect, --out <file.html> or --mark-published")
    try:
        info = profiles.detect([args.target], "tlc-spec-lean")
    except profiles.ProfileError as e:
        print(f"build_preview: {e} (the UI preview exists only for tlc-spec-lean plans)", file=sys.stderr)
        return 1
    feat = Path(info["feature"])
    if args.mark_published and args.url:
        pv = feat / "ui-preview.json"
        if not pv.is_file():
            print(f"build_preview: {pv} not found", file=sys.stderr)
            return 1
        data = json.loads(pv.read_text(encoding="utf-8"))
        data["artifact_url"] = args.url
        pv.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    import lean_preview
    argv = ["--root", str(feat.parent.parent.parent), feat.name]
    argv += ["--detect"] if args.detect else ["--mark-published"] if args.mark_published else ["--out", args.out]
    sys.argv = ["build_preview.py"] + argv
    return lean_preview.main()


if __name__ == "__main__":
    sys.exit(main())
