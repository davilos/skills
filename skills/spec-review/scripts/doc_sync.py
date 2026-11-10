"""Bring into the review state what the user validated on the page (generic and tlc-spec-driven pages).

The page writes each mark to the artifact's db at `review/<key>` (a section id, or
`row:<section>:<n>` for a reviewable row), with the state (`validated`, `rejected` or `pending`)
and the fingerprint of the text the user saw. A mark only counts if its fingerprint still matches
the current documents. Called by sync_review.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_build import ac_review, fingerprints, load_state, page_data, row_keys, save_state  # noqa: E402


def load_rows(folder: Path) -> dict[str, dict]:
    rows = {}
    base = folder / "review" if (folder / "review").is_dir() else folder
    for f in sorted(base.glob("*.json")):
        obj = json.loads(f.read_text(encoding="utf-8"))
        body = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        if isinstance(body, dict) and "state" in body:
            rows[f.stem] = body
    return rows


def sync(info: dict, sp: Path, folder: Path, dry_run: bool) -> int:
    st = load_state(sp)
    page, _, _ = page_data(info, st.get("lang"))
    fp = fingerprints(page, info)
    rows = load_rows(folder)
    if not rows:
        print(f"sync_review: no validations in {folder}", file=sys.stderr)
        return 1

    review = dict(st.get("review") or {})
    rejected = set(st.get("rejected") or [])
    val_fp = dict(st.get("review_fingerprints") or {})
    changed_after = []
    empty = {s["id"] for s in page["sections"] if s.get("empty")}
    gone_seen = dict(st.get("ac_gone_seen") or {})
    for key, row in rows.items():
        if key.startswith("gone:"):
            # "Seen" on the removed criteria of a section: stored apart, it is not a section or a row.
            (gone_seen.__setitem__(key[5:], row.get("fp")) if row.get("state") == "validated" else gone_seen.pop(key[5:], None))
            continue
        if key in empty:
            print(f"  WARN  review/{key}: the section is empty, so there is nothing to validate; ignored", file=sys.stderr)
            review.pop(key, None)
            continue
        if key not in fp:
            print(f"  WARN  review/{key}: not a section or reviewable row of the current document; ignored", file=sys.stderr)
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
    st["profile"] = info["profile"]
    st["ac_gone_seen"] = gone_seen
    # Criteria the user just marked on their current text stop being flagged as changed.
    if "ac_baseline" in st:
        _, st["ac_baseline"] = ac_review(page, info, st, fp)
    if not dry_run:
        save_state(sp, st)

    tab_of = {s["id"]: s.get("tab") for s in page["sections"]}
    names = {s["id"]: (f"{s['tab']} · " if s.get("tab") else "") + s["name"] for s in page["sections"] if not s.get("empty")}
    table_rows = row_keys(page, info)
    cite = {x["key"]: x.get("cite") or f"{names[sid].split(' · ')[-1]} #{x['n']}" for sid, xs in table_rows.items() for x in xs}

    def row_ok(key: str, sid: str) -> bool:
        # A row with no state of its own takes its section's.
        if key in rejected:
            return False
        return review[key] if key in review else bool(review.get(sid))

    def label(key: str) -> str:
        sid = key.split(":")[1]
        return (f"{tab_of[sid]} · " if tab_of.get(sid) else "") + cite[key]

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
    print(f"sync_review: {len(rows)} mark(s) read; {sp.name} {'not written (--dry-run)' if dry_run else 'updated'}")
    for key in changed_after:
        print(f"  RECHECK {key}: marked on the page, but the text changed since; does not count as validated or rejected")
    print(f"  validated: {', '.join(ok_secs) or 'no section'} ({len(ok_secs)} of {len(names)})")
    if partial:
        print(f"  partly confirmed: {', '.join(partial)}")
    print(f"  pending: {', '.join(pending) or 'nothing'}")
    if to_discuss:
        print(f"  rejected by the reviewer (discuss before changing the document): {', '.join(to_discuss)}")
    if empty:
        print(f"  nothing to validate (empty): {', '.join('`' + s['name'] + '`' for s in page['sections'] if s['id'] in empty)}")
    return 0
