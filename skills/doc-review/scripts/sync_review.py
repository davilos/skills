#!/usr/bin/env python3
"""Bring into the review state what the user validated on the page itself.

The page writes each mark to the artifact's db at `review/<key>` (a section id, or
`row:<section>:<n>` for a table row), with the state (`validated`, `rejected` or `pending`) and
the fingerprint of the text the user saw. Read the collection with ArtifactData (`action: "list"`,
`collection: "review"`, `out_dir: <dir>`) and pass that directory here: a mark only counts if its
fingerprint still matches the current document.

Usage:
    python3 sync_review.py <doc.md> --dir <out_dir directory> [--dry-run]

Updates `review`, `rejected` and `review_fingerprints` in `<stem>-doc-review.json` and prints a
summary: validated sections, partly confirmed ones, pending ones, and the rejected rows (what the
user wants to discuss).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_page import fingerprints, load_state, row_keys, save_state, state_path  # noqa: E402
from extract_doc import extract  # noqa: E402


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
    ap.add_argument("doc", help="the Markdown document")
    ap.add_argument("--dir", required=True, help="directory where ArtifactData saved the review collection")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    doc_path = Path(args.doc)
    sp = state_path(doc_path)
    st = load_state(sp)
    doc = extract(doc_path, st.get("lang"))
    fp = fingerprints(doc)
    rows = load_rows(Path(args.dir))
    if not rows:
        print(f"sync_review: no validations in {args.dir}", file=sys.stderr)
        return 1

    review = dict(st.get("review") or {})
    rejected = set(st.get("rejected") or [])
    val_fp = dict(st.get("review_fingerprints") or {})
    changed_after = []
    empty = {s["id"] for s in doc["sections"] if s.get("empty")}
    for key, row in rows.items():
        if key in empty:
            print(f"  WARN  review/{key}: the section is empty, so there is nothing to validate; ignored", file=sys.stderr)
            review.pop(key, None)
            continue
        if key not in fp:
            print(f"  WARN  review/{key}: not a section or table row of the current document; ignored", file=sys.stderr)
            continue
        ok, rej = row.get("state") == "validated", row.get("state") == "rejected"
        if (ok or rej) and row.get("fp") != fp[key]:
            changed_after.append(key)
            ok = rej = False
        (rejected.add if rej else rejected.discard)(key)
        review[key] = ok
        if ok or rej:
            val_fp[key] = row["fp"]
        else:
            val_fp.pop(key, None)

    st["review"] = review
    st["rejected"] = sorted(rejected)
    st["review_fingerprints"] = val_fp
    if not args.dry_run:
        save_state(sp, st)

    names = {s["id"]: s["name"] for s in doc["sections"] if not s.get("empty")}
    table_rows = row_keys(doc)

    def row_ok(key: str, sid: str) -> bool:
        # A row with no state of its own takes its section's.
        if key in rejected:
            return False
        return review[key] if key in review else bool(review.get(sid))

    def label(key: str) -> str:
        _, sid, n = key.split(":")
        return f"{names[sid]} #{n}"

    # A section with rows counts as validated only when the section and every row in it are.
    ok_secs, partial, pending = [], [], []
    for k in names:
        n_ok = sum(row_ok(x["key"], k) for x in table_rows.get(k, []))
        if review.get(k) and n_ok == len(table_rows.get(k, [])):
            ok_secs.append(f"`{names[k]}`")
        elif n_ok:
            partial.append(f"`{names[k]}` ({n_ok} of {len(table_rows[k])} rows confirmed)")
        else:
            pending.append(f"`{names[k]}`")
    to_discuss = [label(x["key"]) for k in table_rows for x in table_rows[k] if x["key"] in rejected]
    print(f"sync_review: {len(rows)} mark(s) read; {sp.name} {'not written (--dry-run)' if args.dry_run else 'updated'}")
    for key in changed_after:
        print(f"  RECHECK {key}: marked on the page, but the text changed since; does not count as validated or rejected")
    print(f"  validated: {', '.join(ok_secs) or 'no section'} ({len(ok_secs)} of {len(names)})")
    if partial:
        print(f"  partly confirmed: {', '.join(partial)}")
    print(f"  pending: {', '.join(pending) or 'nothing'}")
    if to_discuss:
        print(f"  rejected by the reviewer (discuss before changing the document): {', '.join(to_discuss)}")
    if empty:
        print(f"  nothing to validate (empty): {', '.join('`' + s['name'] + '`' for s in doc['sections'] if s['id'] in empty)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
