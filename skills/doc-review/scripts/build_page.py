#!/usr/bin/env python3
"""Build the HTML review page for a Markdown document: doc.md + its review state + the template.

The review state lives beside the document, in `<stem>-doc-review.json` (docs/tdd.md →
docs/tdd-doc-review.json). The build reads it when it exists; only `--mark-published` and
sync_review.py write it, so nobody edits it by hand.

Also proves coverage: every content piece of the document must be in the page data (coverage.py),
and the page carries the list so check_page.cjs can look for it in the rendered text. And it stamps
the version: the document hash and build time at the top of the page; warns when the document
changed since the last publish.

Usage:
    python3 build_page.py <doc.md> --out <file.html> [--lang en|pt]
    python3 build_page.py <doc.md> --mark-published [--url <artifact url>]
        (after publishing: records the link and the hash of the document that went live)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coverage import IMAGE, missing_in_data, rendered_pieces, unsupported_markdown  # noqa: E402
from extract_doc import extract, gh_slug, slugify  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"


def state_path(doc: Path) -> Path:
    return doc.with_name(doc.stem + "-doc-review.json")


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(path: Path, st: dict) -> None:
    path.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def doc_hash(doc: Path) -> str:
    return hashlib.sha256(doc.read_bytes()).hexdigest()[:12]


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def row_keys(doc: dict) -> dict[str, list[dict]]:
    """Table rows the user confirms one by one, per section: `{sid: [{key, n, b, r}]}`.

    `b` is the block index in the section and `r` the row index in that table. Rows are numbered
    1, 2... per section, across its tables, so the user can cite "Risks #2". Empty sections have none.
    """
    out: dict[str, list[dict]] = {}
    for s in doc["sections"]:
        if s.get("empty"):
            continue
        rows, n = [], 0
        for bi, b in enumerate(s["blocks"]):
            if b["type"] != "table":
                continue
            for ri in range(len(b["rows"])):
                n += 1
                rows.append({"key": f"row:{s['id']}:{n}", "n": n, "b": bi, "r": ri})
        if rows:
            out[s["id"]] = rows
    return out


def fingerprints(doc: dict) -> dict[str, str]:
    """Fingerprint of every section and table row the user can validate (empty sections have none)."""
    fp: dict[str, str] = {}
    secs = {s["id"]: s for s in doc["sections"]}
    for sid, s in secs.items():
        if not s.get("empty"):
            fp[sid] = _h(s["blocks"])
    for sid, rows in row_keys(doc).items():
        for x in rows:
            fp[x["key"]] = _h(secs[sid]["blocks"][x["b"]]["rows"][x["r"]])
    return fp


def validated_keys(doc: dict, st: dict) -> set[str]:
    """Validated sections and rows in the state. A row with no state of its own takes its section's."""
    review = st.get("review") or {}
    rejected = set(st.get("rejected") or [])
    keys = {k for k, ok in review.items() if ok}
    for sid, rows in row_keys(doc).items():
        if review.get(sid):
            keys |= {x["key"] for x in rows if x["key"] not in review}
    return keys - rejected


def reviewed_keys(doc: dict, st: dict) -> set[str]:
    """What the user marked, either way: both keep the fingerprint of the text they saw."""
    return validated_keys(doc, st) | set(st.get("rejected") or [])


def validate(doc: dict, st: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    secs = {s["id"]: s for s in doc["sections"]}
    if not doc["sections"]:
        errors.append("the document has no sections (no headings and no text)")
    review = st.get("review") or {}
    row_ids = {x["key"] for rows in row_keys(doc).values() for x in rows}
    for k in review:
        if k.startswith("row:"):
            if k not in row_ids:
                warns.append(f"review.{k}: not a table row of the current document; ignored")
        elif k not in secs:
            warns.append(f"review.{k}: not a section of the current document (renamed?); ignored")
        elif secs[k].get("empty"):
            warns.append(f"review.{k}: the section is empty, so there is nothing to validate; ignored")
    for k in st.get("rejected") or []:
        if k not in row_ids:
            warns.append(f"rejected has {k!r}, which is not a table row of the current document; ignored")
        elif review.get(k):
            errors.append(f"{k} is both validated and rejected in the review state: keep one")
    return errors, warns


def doc_images(doc_path: Path) -> tuple[list[str], list[str]]:
    """Images the document shows (`![name](path)`), as paths relative to it.

    The page loads each one from the same relative path, so it is copied beside the HTML and
    published with it. A URL, a path leaving the document's folder or a missing file is a warning.
    """
    images, warns = [], []
    for i, line in enumerate(doc_path.read_text(encoding="utf-8").splitlines(), 1):
        for m in IMAGE.finditer(re.sub(r"`[^`]*`", "", line)):
            src = m[2]
            if re.match(r"[a-z]+:", src, re.I):
                warns.append(f"{doc_path.name}:{i} shows the remote image {src}: the artifact may block it (the page then shows its name)")
            elif src.startswith("/") or ".." in Path(src).parts:
                warns.append(f"{doc_path.name}:{i} shows {src}, outside the document's folder: the page cannot carry it")
            elif not (doc_path.parent / src).is_file():
                warns.append(f"{doc_path.name}:{i} shows {src}, which does not exist beside the document")
            elif src not in images:
                images.append(src)
    return images, warns


def anchors(doc: dict) -> dict[str, str]:
    """Internal links (`[x](#heading)`) the page can follow: heading anchor → element id on the page."""
    out: dict[str, str] = {}
    for s in doc["sections"]:
        if not s.get("intro"):
            out.setdefault(gh_slug(s["name"]), "s-" + s["id"])
            out.setdefault(slugify(s["name"]), "s-" + s["id"])
        for bi, b in enumerate(s["blocks"]):
            if b["type"] == "h":
                hid = f"h-{s['id']}-{bi}"
                out.setdefault(gh_slug(b["text"]), hid)
                out.setdefault(slugify(b["text"]), hid)
    return out


def as_script_json(data) -> str:
    # `</` would close the <script>; U+2028/2029 break old JS strings.
    return (json.dumps(data, ensure_ascii=False)
            .replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("doc", help="the Markdown document")
    ap.add_argument("--out", help="the HTML file to write")
    ap.add_argument("--lang", choices=["en", "pt"], help="page language (default: the state's, else detected from the document)")
    ap.add_argument("--mark-published", action="store_true", help="record the hash of the document that just went live")
    ap.add_argument("--url", help="with --mark-published: the artifact link, stored the first time")
    args = ap.parse_args()
    if not args.out and not args.mark_published:
        ap.error("pass --out <file.html> or --mark-published")

    doc_path = Path(args.doc)
    if not doc_path.is_file():
        print(f"build_page: {doc_path} not found", file=sys.stderr)
        return 1
    sp = state_path(doc_path)
    st = load_state(sp)
    current = doc_hash(doc_path)
    lang = args.lang or st.get("lang")

    if args.mark_published:
        doc = extract(doc_path, lang)
        now = fingerprints(doc)
        if args.url:
            st["artifact_url"] = args.url
        if args.lang:
            st["lang"] = args.lang
        if not st.get("artifact_url"):
            print("build_page: no artifact link yet; pass --url <link> the first time", file=sys.stderr)
            return 1
        st["published_hash"] = current
        st["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # A validated item keeps the fingerprint of the text the user validated, not of this publish:
        # recomputing it here would clear "changed since" without anyone validating again.
        kept = st.get("review_fingerprints") or {}
        st["review_fingerprints"] = {k: kept.get(k) or now[k] for k in sorted(reviewed_keys(doc, st)) if k in now}
        st["published_fingerprints"] = now
        save_state(sp, st)
        print(f"build_page: {sp} marked as published ({doc_path.name} {current})")
        return 0

    published = st.get("published_hash")
    if published and published != current:
        print(f"  STALE the published page ({st.get('artifact_url') or 'no link'}) is from {doc_path.name} {published}; "
              f"the current one is {current}: build and publish again", file=sys.stderr)

    doc = extract(doc_path, lang)
    doc["path"] = str(doc_path)
    doc["hash"] = current
    doc["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    errors, warns = validate(doc, st)
    # Coverage, end 1: every content piece of the document is in the extracted data.
    for line, piece in missing_in_data(doc_path, doc):
        errors.append(f"coverage: {doc_path.name}:{line} did not reach the page data: {piece[:80]!r}")
    # End 2 goes into the page: check_page.cjs looks for each piece in the rendered text.
    doc["coverage"] = rendered_pieces(doc_path)
    for line, what in unsupported_markdown(doc_path):
        warns.append(f"{doc_path.name}:{line} uses {what}, which the page shows as raw text")
    images, img_warns = doc_images(doc_path)
    warns += img_warns
    doc["images"] = images
    doc["anchors"] = anchors(doc)

    # What changed since it was validated (review_fingerprints) or since the last publish.
    stale = {}
    old = st.get("published_fingerprints") or {}
    val_fp = st.get("review_fingerprints") or {}
    marked = reviewed_keys(doc, st)
    now = fingerprints(doc)
    for key, val in now.items():
        base = val_fp.get(key) if key in marked else old.get(key)
        if base is None or base == val:
            continue
        stale[key] = True
        if key in marked:
            print(f"  RECHECK {key}: was validated/confirmed/rejected, but the text changed since", file=sys.stderr)
    doc["stale"] = stale
    doc["rows"] = row_keys(doc)
    # The page stores the fingerprint of the text the user validated (db review/<key>.fp) and shows
    # "changed since" when it stops matching.
    doc["fingerprints"] = now
    for w in warns:
        print(f"  WARN  {w}", file=sys.stderr)
    for e in errors:
        print(f"  ERROR {e}", file=sys.stderr)
    if errors:
        print(f"build_page: {len(errors)} error(s); page not built", file=sys.stderr)
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    title = st.get("title") or doc["title"]
    html = (html.replace("__LANG__", doc["lang"])
                .replace("__TITLE__", title.replace("&", "&amp;").replace("<", "&lt;"))
                .replace("__DOC_JSON__", as_script_json(doc))
                .replace("__STATE_JSON__", as_script_json(st)))
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")
    # The images travel with the page, at the path the document uses. Resolved first: an image (a
    # symlink included) is read only from inside the document's folder and written only inside the page's.
    out_dir, doc_dir = out.resolve().parent, doc_path.parent.resolve()
    for src in list(images):
        origin, target = (doc_dir / src).resolve(), (out_dir / src).resolve()
        if not origin.is_relative_to(doc_dir) or not target.is_relative_to(out_dir):
            print(f"  WARN  {src} resolves outside the document or the page folder; not copied", file=sys.stderr)
            images.remove(src)
            continue
        if origin != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, target)
    if images:
        print(f"build_page: {len(images)} image(s) beside the page; publish each with it (files): {', '.join(images)}")
    n_rows = sum(len(v) for v in doc["rows"].values())
    n_mmd = sum(1 for s in doc["sections"] for b in s["blocks"] if b["type"] == "code" and b["lang"] == "mermaid")
    print(f"build_page: {out} ({len(doc['sections'])} sections, {n_rows} table rows, {n_mmd} diagrams, "
          f"{len(doc['coverage'])} pieces covered, lang {doc['lang']}, {doc_path.name} {current}, {len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
