#!/usr/bin/env python3
"""Bring into review-page.json what the user validated on the page itself.

The page writes each validation to the artifact's db at `review/<key>` (`problem`,
`S1`, `door:1`, `row:assumptions:2`...), with the state (`validated`, `rejected` or
`pending`) and the fingerprint of the text the user saw. Read the
collection with ArtifactData (`action: "list"`, `collection: "review"`, `out_dir: <dir>`)
and pass that directory here: a validation only counts if its fingerprint still matches
the current plan.md.

Usage:
    python3 sync_review.py --root <project> <feature> --dir <out_dir directory>
        [--dry-run]

Updates `review`, `doors_confirmed` and `rejected` in review-page.json and prints a summary
of the validations, plus the rejected rows: what the user wants to discuss, and whether the
plan carries `**Approved**:`. Validating is not approving: that line is the user's word, written
by tlc-spec-lean. An older plan with a `**Status**:` line takes the summary into that line.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_page import DERIVED, fingerprints, row_keys  # noqa: E402
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
    rejected = set(pg.get("rejected", []))
    # Fingerprint of the validated text: the build compares against it to show "changed since".
    val_fp = dict(pg.get("review_fingerprints") or {})
    changed_after = []
    empty = {s["id"] for s in plan["sections"] if s.get("empty")}
    for key, row in rows.items():
        if key in empty:
            print(f"  WARN  review/{key}: the section is empty in the plan, so there is nothing to validate; ignored", file=sys.stderr)
            review.pop(key, None)
            continue
        if key not in fp:
            print(f"  WARN  review/{key}: not a section, slice, door or table row of the current plan; ignored", file=sys.stderr)
            continue
        ok, rej = row.get("state") == "validated", row.get("state") == "rejected"
        if (ok or rej) and row.get("fp") != fp[key]:
            changed_after.append(key)
            ok = rej = False
        (rejected.add if rej else rejected.discard)(key)
        if key.startswith("door:"):
            (doors.add if ok else doors.discard)(int(key[5:]))
        else:
            review[key] = ok
        if ok or rej:
            val_fp[key] = row["fp"]
        else:
            val_fp.pop(key, None)

    pg["review"] = review
    pg["doors_confirmed"] = sorted(doors)
    pg["rejected"] = sorted(rejected)
    pg["review_fingerprints"] = val_fp
    if not args.dry_run:
        pg_path.write_text(json.dumps(pg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    names = {s["id"]: s["name"] for s in plan["sections"] if not s.get("empty")}
    slices = [s["id"] for x in plan["sections"] if x["id"] == "criteria" for s in x["criteria"]["slices"]]
    table_rows = row_keys(plan)

    def row_ok(key: str, sid: str) -> bool:
        # A row with no state of its own takes its section's (doors excepted).
        if key in rejected:
            return False
        if key.startswith("door:"):
            return int(key[5:]) in doors
        return review[key] if key in review else bool(review.get(sid))

    def label(key: str) -> str:
        return f"door {key[5:]}" if key.startswith("door:") else f"{names[key.split(':')[1]]} #{key.split(':')[2]}"

    # A section with rows counts as validated only when the section and every row in it are.
    ok_secs, partial, pending = [], [], []
    for k in names:
        n_ok = sum(row_ok(x["key"], k) for x in table_rows.get(k, []))
        if review.get(k) and n_ok == len(table_rows.get(k, [])):
            ok_secs.append(f"`{names[k]}`")
        elif n_ok:
            partial.append(f"`{names[k]}` ({n_ok} of {len(table_rows[k])} {'doors' if k == 'landing' else 'rows'} confirmed)")
        else:
            pending.append(f"`{names[k]}`")
    ok_slices = [k for k in slices if review.get(k)]
    to_discuss = [label(x["key"]) for k in table_rows for x in table_rows[k] if x["key"] in rejected]
    print(f"sync_review: {len(rows)} validation(s) read; review-page.json {'not written (--dry-run)' if args.dry_run else 'updated'}")
    for key in changed_after:
        print(f"  RECHECK {key}: marked on the page, but the text changed since; does not count as validated or rejected")
    print(f"Approved: {plan['approved']}" if plan.get("approved") else
          "Approved: not yet - approval is the user's word, which tlc-spec-lean writes as `**Approved**:` under the title")
    print("Validations" + (" (copy into the plan's `**Status**:` line):" if plan.get("status") else ":"))
    print(f"  validated by the reviewer: {', '.join(ok_secs) or 'no section'}"
          + (f"; slices {', '.join(ok_slices)}" if ok_slices else "")
          + (f"; doors {', '.join(str(d) for d in sorted(doors))} confirmed" if doors else ""))
    if partial:
        print(f"  partly confirmed: {', '.join(partial)}")
    print(f"  pending: {', '.join(pending) or 'nothing'}")
    if to_discuss:
        print(f"  rejected by the reviewer (discuss before changing the plan): {', '.join(to_discuss)}")
    if empty:
        na = [f"`{s['name']}`" for s in plan["sections"] if s["id"] in empty]
        print(f"  nothing to validate (empty in the plan): {', '.join(na)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
