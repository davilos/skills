#!/usr/bin/env python3
"""Show what the page will hold: the profile, its tabs and the sections of each file.

Usage:
    python3 extract.py <target>... [--profile P] [--json]

Without --json it prints a short outline (profile, tabs, sections, reviewable rows); with --json,
the full extracted data. A cut that looks wrong (one giant section, sections that should be
subheadings) is a problem in the document's headings: tell the user.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_page import resolve  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", nargs="+")
    ap.add_argument("--profile", choices=["generic", "tlc-spec-lean", "tlc-spec-driven"])
    ap.add_argument("--json", action="store_true", help="print the full extracted data")
    args = ap.parse_args()
    info = resolve(args.target, args.profile)
    if not info:
        return 1
    if info["profile"] == "tlc-spec-lean":
        from lean_extract import extract
        data = extract(Path(info["plan"]))
        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0
        print(f"{data['title']}  ({info['plan']})")
        for s in data["sections"]:
            print(f"  {s['name']}" + ("  (empty)" if s.get("empty") else ""))
        return 0
    from doc_build import page_data, row_keys
    page, errors, warns = page_data(info, None)
    if args.json:
        print(json.dumps(page, ensure_ascii=False, indent=2))
        return 0
    rows = row_keys(page, info)
    for t in page.get("tabs") or [{"id": None, "file": Path(page["path"]).name, "exists": True}]:
        if t["id"]:
            print(f"[{t['id']}] {t['file']}" + ("" if t["exists"] else "  (missing: tab shown switched off)"))
        for s in page["sections"]:
            if s.get("tab") != t["id"]:
                continue
            units = rows.get(s["id"], [])
            cites = [u.get("cite") for u in units if u.get("cite")]
            print(f"  {s['name']}" + ("  (empty)" if s.get("empty") else "") +
                  (f"  {len(units)} reviewable row(s)" if units else "") + (f": {', '.join(cites)}" if cites else ""))
    for e in errors:
        print(f"  ERROR {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
