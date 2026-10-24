#!/usr/bin/env python3
"""Bring into review-page.json what the user validated on the page itself.

The page writes each validation to the artifact's db at `review/<key>` (`problem`,
`S1`, `door:1`...), with the state and the fingerprint of the validated text. Read the
collection with ArtifactData (`action: "list"`, `collection: "review"`, `out_dir: <dir>`)
and pass that directory here: a validation only counts if its fingerprint still matches
the current plan.md.

Usage:
    python3 sync_review.py --root <project> <feature> --dir <out_dir directory>
        [--dry-run]

Updates `review` and `doors_confirmed` in review-page.json and prints the validation
part of the plan.md `**Status**:` line, which whoever runs the skill copies into the plan.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_page import DERIVED, fingerprints  # noqa: E402
from extract_plan import extract  # noqa: E402


def load_rows(folder: Path) -> dict[str, dict]:
    rows = {}
    base = folder / "review" if (folder / "review").is_dir() else folder
    for f in sorted(base.glob("*.json")):
        obj = json.loads(f.read_text(encoding="utf-8"))
        body = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        if isinstance(body, dict) and "state" in body:
            rows[f.stem] = body
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--dir", required=True, help="directory where ArtifactData saved the review collection")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("feature")
    args = ap.parse_args()

    feat = Path(args.root) / ".specs" / "features" / args.feature
    pg_path = feat / "review-page.json"
    plan = extract(feat / "plan.md")
    pg = json.loads(pg_path.read_text(encoding="utf-8"))
    fp = {k: v for k, v in fingerprints(plan, pg).items() if not k.startswith(DERIVED)}
    rows = load_rows(Path(args.dir))
    if not rows:
        print(f"sync_review: no validations in {args.dir}", file=sys.stderr)
        return 1

    review = dict(pg.get("review", {}))
    doors = set(pg.get("doors_confirmed", []))
    # Fingerprint of the validated text: the build compares against it to show "changed since".
    val_fp = dict(pg.get("review_fingerprints") or {})
    changed_after = []
    for key, row in rows.items():
        if key not in fp:
            print(f"  WARN  review/{key}: not a section, slice or door of the current plan; ignored", file=sys.stderr)
            continue
        ok = row.get("state") == "validated"
        if ok and row.get("fp") != fp[key]:
            changed_after.append(key)
            ok = False
        if key.startswith("door:"):
            (doors.add if ok else doors.discard)(int(key[5:]))
        else:
            review[key] = ok
        if ok:
            val_fp[key] = row["fp"]
        else:
            val_fp.pop(key, None)

    pg["review"] = review
    pg["doors_confirmed"] = sorted(doors)
    pg["review_fingerprints"] = val_fp
    if not args.dry_run:
        pg_path.write_text(json.dumps(pg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    names = {s["id"]: s["name"] for s in plan["sections"]}
    slices = [s["id"] for x in plan["sections"] if x["id"] == "criteria" for s in x["criteria"]["slices"]]
    ok_secs = [f"`{names[k]}`" for k in names if review.get(k)]
    pending = [f"`{names[k]}`" for k in names if not review.get(k)]
    ok_slices = [k for k in slices if review.get(k)]
    print(f"sync_review: {len(rows)} validation(s) read; review-page.json {'not written (--dry-run)' if args.dry_run else 'updated'}")
    for key in changed_after:
        print(f"  RECHECK {key}: validated on the page, but the text changed since; does not count as validated")
    print("Status (validations):")
    print(f"  validated by the reviewer: {', '.join(ok_secs) or 'no section'}"
          + (f"; slices {', '.join(ok_slices)}" if ok_slices else "")
          + (f"; doors {', '.join(str(d) for d in sorted(doors))} confirmed" if doors else ""))
    print(f"  pending: {', '.join(pending) or 'nothing'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
