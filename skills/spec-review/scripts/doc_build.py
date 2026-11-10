"""The page engine for the generic and tlc-spec-driven profiles: Markdown files + review state + template.

A page holds one or more files. A single generic document keeps the plain layout (no tabs, plain
section ids); a page with several files, or any tlc-spec-driven page, gets one tab per file and its
section ids start with the tab id (`spec-user-stories`).

Every table row is reviewed one by one; a profile adds more reviewable units (a list item, a
heading with what follows it, a paragraph). All of them are numbered per section, in document
order, under the key `row:<section>:<n>`, and carry the text the user cites (`Riscos #2`, `P1 AC 2`,
`T1`).

Also proves coverage: every content piece of every file must be in the page data (doc_coverage.py),
and the page carries the list so doc_check.cjs can look for it in the rendered text, per tab.
Called by build_page.py, which picks the profile and the review state file.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ac_changes  # noqa: E402
from doc_coverage import IMAGE, missing_in_data, rendered_pieces, unsupported_markdown  # noqa: E402
from doc_extract import extract, gh_slug, slugify  # noqa: E402
from profiles import load_profile  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "doc-template.html"


def load_state(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(path: Path, st: dict) -> None:
    path.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def is_multi(info: dict) -> bool:
    return info["profile"] != "generic" or len(info["tabs"]) > 1


def page_hash(info: dict) -> str:
    """One file: its hash. Several: the hash of every file's name and hash."""
    files = [t for t in info["tabs"] if t["exists"]]
    if not is_multi(info):
        return file_hash(Path(files[0]["path"]))
    return _h([[t["file"], file_hash(Path(t["path"]))] for t in files])


def page_base(info: dict) -> Path:
    """The folder every file of the page sits under: images are copied and loaded relative to it, so
    files from sibling folders (`docs/a/a.md`, `docs/b/b.md`) keep their images apart (`b/d.png`)."""
    dirs = [str(Path(t["path"]).parent.absolute()) for t in info["tabs"] if t["exists"]]
    return Path(os.path.commonpath(dirs))


def page_lang(info: dict, lang: str | None) -> str:
    """One language for the whole page: the one asked for, else detected from the first file."""
    if lang:
        return lang
    first = next(t for t in info["tabs"] if t["exists"])
    return extract(Path(first["path"]))["lang"]


def page_data(info: dict, lang: str | None) -> tuple[dict, list[str], list[str]]:
    """Every file of the page, extracted with one language, as one list of sections.

    Returns (page, errors, warnings). Coverage end 1 runs here, per file, before ids get prefixed.
    """
    multi = is_multi(info)
    lang = page_lang(info, lang)
    errors: list[str] = []
    warns: list[str] = []
    page: dict = {"lang": lang, "sections": [], "coverage": [], "images": [], "anchors": {}}
    tabs = []
    base = page_base(info)
    for t in info["tabs"]:
        if not t["exists"]:
            tabs.append({"id": t["id"], "file": t["file"], "exists": False})
            continue
        p = Path(t["path"])
        d = extract(p, lang)
        for line, piece in missing_in_data(p, d):
            errors.append(f"coverage: {p.name}:{line} did not reach the page data: {piece[:80]!r}")
        for line, what in unsupported_markdown(p):
            warns.append(f"{p.name}:{line} uses {what}, which the page shows as raw text")
        imgs, img_warns = doc_images(p)
        warns += img_warns
        pre = t["id"] + "-" if multi else ""
        for s in d["sections"]:
            s["id"] = pre + s["id"]
            s["lvl"] = d["level"]
            if multi:
                s["tab"] = t["id"]
        for line, sec, kind, text in rendered_pieces(p):
            page["coverage"].append([line, pre + sec, kind, text, t["id"]])
        tab_dir = p.parent.absolute().relative_to(base).as_posix() if multi else "."
        for src in imgs:
            rel = src if tab_dir == "." else f"{tab_dir}/{src}"
            if rel not in page["images"]:
                page["images"].append(rel)
        page["anchors"].update({k: v for k, v in anchors(d).items() if k not in page["anchors"]})
        page["sections"] += d["sections"]
        tabs.append({"id": t["id"], "file": t["file"], "exists": True, "path": str(p), "title": d["title"],
                     "front": d["front"], "level": d["level"], "hash": file_hash(p),
                     "dir": "" if tab_dir == "." else tab_dir})
    first = next(x for x in tabs if x["exists"])
    page.update(title=first["title"], front=first["front"], level=first["level"], path=first["path"])
    if multi:
        page["tabs"] = tabs
        page["path"] = str(Path(first["path"]).parent)
        page["front"] = []  # each tab shows its own front matter, under its own title
        if info["profile"] == "tlc-spec-driven":
            # The page is the feature; "Lembrete Specification" stays the title of the spec tab.
            page["title"] = re.sub(r"\s+(?:Specification|Spec|Design|Tasks|Context|Validation|Verification)\s*$", "",
                                   first["title"], flags=re.I) or Path(page["path"]).name
    if not page["sections"]:
        errors.append("the document has no sections (no headings and no text)")
    return page, errors, warns


# ---------- reviewable units ----------

def _cite(fmt: str, **kw) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(kw.get(m[1], m[0])), fmt)


def _item_rules(info: dict) -> tuple[list[dict], list[dict], dict]:
    if info["profile"] == "generic":
        return [], [], {}
    prof = load_profile(info["profile"])
    return prof.get("items", []), prof.get("ids", []), prof.get("covers", {})


def _rule_applies(rule: dict, s: dict) -> bool:
    return rule.get("tab") == s.get("tab") and (not rule.get("section") or re.search(rule["section"], s["name"], re.I))


def h_span(blocks: list[dict], bi: int) -> list[dict]:
    """A heading and everything under it, up to the next heading at its level or above."""
    lv = blocks[bi]["level"]
    end = next((j for j in range(bi + 1, len(blocks)) if blocks[j]["type"] == "h" and blocks[j]["level"] <= lv), len(blocks))
    return blocks[bi:end]


def row_keys(page: dict, info: dict) -> dict[str, list[dict]]:
    """Units the user confirms one by one, per section: `{sid: [{key, n, b, kind, r | i, cite?}]}`.

    `b` is the block index in the section; `r` the row of a table, `i` the item of a list. Units are
    numbered 1, 2... per section in document order. Empty sections have none.
    """
    rules = _item_rules(info)[0]
    out: dict[str, list[dict]] = {}
    for s in page["sections"]:
        if s.get("empty"):
            continue
        units, n, under, seen = [], 0, None, {}
        mine = [r for r in rules if _rule_applies(r, s)]
        for bi, b in enumerate(s["blocks"]):
            if b["type"] == "table":
                for ri in range(len(b["rows"])):
                    n += 1
                    units.append({"key": f"row:{s['id']}:{n}", "n": n, "b": bi, "kind": "table", "r": ri})
                continue
            if b["type"] == "h":
                under = b["text"]
            for rule in mine:
                if rule["kind"] == "h" and b["type"] == "h" and (m := re.search(rule["text"], b["text"])):
                    n += 1
                    units.append({"key": f"row:{s['id']}:{n}", "n": n, "b": bi, "kind": "h",
                                  "cite": _cite(rule["cite"], **{"1": m.group(1) if m.groups() else m[0]})})
                elif rule["kind"] == "p" and b["type"] == "p" and (m := re.search(rule["text"], b["text"])):
                    n += 1
                    units.append({"key": f"row:{s['id']}:{n}", "n": n, "b": bi, "kind": "p",
                                  "cite": _cite(rule["cite"], **{"1": m.group(1) if m.groups() else m[0]})})
                elif rule["kind"] == "li" and b["type"] == rule.get("list", b["type"]) and b["type"] in ("ol", "ul"):
                    um = re.search(rule["under"], under or "") if rule.get("under") else None
                    if rule.get("under") and not um:
                        continue
                    for ii, it in enumerate(b["items"]):
                        if not re.search(rule["text"], it["text"]):
                            continue
                        n += 1
                        k = rule.get("cite", "")
                        seen[k] = seen.get(k, 0) + 1
                        units.append({"key": f"row:{s['id']}:{n}", "n": n, "b": bi, "kind": "li", "i": ii,
                                      "cite": _cite(k, under=um.group(1) if um else "", n=it.get("n", ii + 1),
                                                    i=seen[k], section=s["name"])})
                        if rule.get("ac"):
                            units[-1]["ac"] = True
                else:
                    continue
                break
        if units:
            out[s["id"]] = units
    if is_multi(info):
        unique_cites(page, out)
    return out


def unique_cites(page: dict, units: dict[str, list[dict]]) -> None:
    """Every unit of a page with tabs gets a citation no other unit has.

    The profile's citation (`P1 AC 2`) is kept when it is unique in its tab; repeated (two P1 stories),
    it falls back to `Section #N`, unique in its section. A citation repeated across tabs (two files
    with the same section name) is prefixed with the tab: `spec · Risks #2`.
    """
    secs = {s["id"]: s for s in page["sections"]}
    per_tab: dict[tuple, int] = {}
    for sid, us in units.items():
        for u in us:
            if u.get("cite"):
                k = (secs[sid].get("tab"), u["cite"])
                per_tab[k] = per_tab.get(k, 0) + 1
    for sid, us in units.items():
        for u in us:
            if not u.get("cite") or per_tab[(secs[sid].get("tab"), u["cite"])] > 1:
                u["cite"] = f"{secs[sid]['name']} #{u['n']}"
    across: dict[str, int] = {}
    for us in units.values():
        for u in us:
            across[u["cite"]] = across.get(u["cite"], 0) + 1
    for sid, us in units.items():
        for u in us:
            if across[u["cite"]] > 1:
                u["cite"] = f"{secs[sid].get('tab')} · {u['cite']}"


def unit_text(s: dict, u: dict):
    b = s["blocks"][u["b"]]
    return {"table": lambda: b["rows"][u["r"]], "li": lambda: b["items"][u["i"]],
            "h": lambda: h_span(s["blocks"], u["b"]), "p": lambda: b}[u.get("kind", "table")]()


def fingerprints(page: dict, info: dict) -> dict[str, str]:
    """Fingerprint of every section and unit the user can validate (empty sections have none)."""
    fp: dict[str, str] = {}
    secs = {s["id"]: s for s in page["sections"]}
    for sid, s in secs.items():
        if not s.get("empty"):
            fp[sid] = _h(s["blocks"])
    for sid, units in row_keys(page, info).items():
        for u in units:
            fp[u["key"]] = _h(unit_text(secs[sid], u))
    return fp


def _item_text(it: dict) -> str:
    parts = [it.get("text", "")]
    for sub in it.get("sub") or []:
        parts += [_item_text(x) for x in sub["items"]] if sub["type"] in ("ul", "ol") else [sub.get("text", "")]
    return " ".join(p for p in parts if p)


def ac_review(page: dict, info: dict, st: dict, now: dict[str, str]) -> tuple[dict, dict]:
    """Acceptance criteria (the profile's items with `"ac": true`) that changed since the reviewer
    last saw them, and the next `ac_baseline` (see ac_changes.py). A criterion is acknowledged when
    it, or its section, was marked on its current text."""
    secs = {s["id"]: s for s in page["sections"]}
    current = {sid: [(u["key"], _item_text(unit_text(secs[sid], u))) for u in us if u.get("ac")]
               for sid, us in row_keys(page, info).items()}
    current = {sid: xs for sid, xs in current.items() if xs}
    if not current and not st.get("ac_baseline"):
        return {"items": {}, "removed": {}}, {}
    val_fp = st.get("review_fingerprints") or {}
    marked = reviewed_keys(page, info, st)
    on_now = {k for k in marked if k in now and (val_fp.get(k) or now[k]) == now[k]}
    groups = {sid for sid in current if sid in on_now and sid in (st.get("review") or {})}
    data, nxt = ac_changes.changes(st.get("ac_baseline"), current, on_now, groups, st.get("ac_gone_seen"))
    cite = {u["key"]: u.get("cite") for us in row_keys(page, info).values() for u in us}
    for key, x in data["items"].items():
        x["cite"] = cite.get(key) or key
    for sid, x in data["removed"].items():
        x["name"] = secs[sid]["name"] if sid in secs else sid
    return data, nxt


def xrefs(page: dict, info: dict, units: dict) -> tuple[dict, dict]:
    """IDs the text uses (`T1`, `C2`, `LEMB-01`, `P1`) → the element they name, and for each
    requirement ID the units that cite it. Only IDs the documents define; nothing is invented."""
    _, id_rules, covers = _item_rules(info)
    if not id_rules:
        return {}, {}
    where: dict[str, str] = {}
    seen: dict[str, int] = {}  # an ID defined twice (two "P1" stories) is ambiguous: it gets no link
    unit_at = {(sid, u["b"], u.get("r"), u.get("i")): u for sid, us in units.items() for u in us}
    for s in page["sections"]:
        for rule in id_rules:
            if not _rule_applies(rule, s):
                continue
            for bi, b in enumerate(s["blocks"]):
                if rule["kind"] in ("h", "p") and b["type"] == rule["kind"] and (m := re.search(rule["text"], b["text"])):
                    u = unit_at.get((s["id"], bi, None, None))
                    seen[m.group(1)] = seen.get(m.group(1), 0) + 1
                    where.setdefault(m.group(1), f"row-{s['id']}-{u['n']}" if u else f"h-{s['id']}-{bi}")
                elif rule["kind"] == "cell" and b["type"] == "table":
                    for ri, row in enumerate(b["rows"]):
                        m = re.search(rule["text"], (row[0] if row else "").strip().strip("`"))
                        u = unit_at.get((s["id"], bi, ri, None))
                        if m and u:
                            seen[m.group(1)] = seen.get(m.group(1), 0) + 1
                            where.setdefault(m.group(1), f"row-{s['id']}-{u['n']}")
    where = {k: v for k, v in where.items() if seen.get(k, 0) == 1}
    cov: dict[str, list] = {}
    if covers:
        by = [x.split(":") for x in covers.get("by", [])]
        secs = {s["id"]: s for s in page["sections"]}
        for rid in [k for k in where if re.match(covers["ids"], k)]:
            word = re.compile(rf"(?<![\w-]){re.escape(rid)}(?![\w-])")
            for sid, us in units.items():
                s = secs[sid]
                for u in us:
                    if [s.get("tab"), u["kind"]] in by and word.search(json.dumps(unit_text(s, u), ensure_ascii=False)):
                        cov.setdefault(rid, []).append([u.get("cite") or f"{s['name']} #{u['n']}", f"row-{sid}-{u['n']}"])
    return where, cov


# ---------- review state ----------

def validated_keys(page: dict, info: dict, st: dict) -> set[str]:
    """Validated sections and units in the state. A unit with no state of its own takes its section's."""
    review = st.get("review") or {}
    rejected = set(st.get("rejected") or [])
    keys = {k for k, ok in review.items() if ok}
    for sid, rows in row_keys(page, info).items():
        if review.get(sid):
            keys |= {x["key"] for x in rows if x["key"] not in review}
    return keys - rejected


def reviewed_keys(page: dict, info: dict, st: dict) -> set[str]:
    """What the user marked, either way: both keep the fingerprint of the text they saw."""
    return validated_keys(page, info, st) | set(st.get("rejected") or [])


def validate(page: dict, info: dict, st: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    secs = {s["id"]: s for s in page["sections"]}
    review = st.get("review") or {}
    row_ids = {x["key"] for rows in row_keys(page, info).values() for x in rows}
    for k in review:
        if k.startswith("row:"):
            if k not in row_ids:
                warns.append(f"review.{k}: not a reviewable row of the current document; ignored")
        elif k not in secs:
            warns.append(f"review.{k}: not a section of the current document (renamed?); ignored")
        elif secs[k].get("empty"):
            warns.append(f"review.{k}: the section is empty, so there is nothing to validate; ignored")
    for k in st.get("rejected") or []:
        if k not in row_ids:
            warns.append(f"rejected has {k!r}, which is not a reviewable row of the current document; ignored")
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
    """Internal links (`[x](#heading)`) the page can follow: heading anchor → element id on the page.
    Section ids must already carry the tab prefix when the page has tabs."""
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


# ---------- entry points (called by build_page.py) ----------

def mark_published(info: dict, sp: Path, url: str | None, lang: str | None) -> int:
    st = load_state(sp)
    lang = lang or st.get("lang")
    page, _, _ = page_data(info, lang)
    now = fingerprints(page, info)
    if url:
        st["artifact_url"] = url
    if lang:
        st["lang"] = lang
    if not st.get("artifact_url"):
        print("build_page: no artifact link yet; pass --url <link> the first time", file=sys.stderr)
        return 1
    st["profile"] = info["profile"]
    st["published_hash"] = page_hash(info)
    st["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    # A validated item keeps the fingerprint of the text the user validated, not of this publish:
    # recomputing it here would clear "changed since" without anyone validating again.
    kept = st.get("review_fingerprints") or {}
    st["review_fingerprints"] = {k: kept.get(k) or now[k] for k in sorted(reviewed_keys(page, info, st)) if k in now}
    st["published_fingerprints"] = now
    _, nxt = ac_review(page, info, st, now)
    if nxt or "ac_baseline" in st:  # a document with no criteria (generic) gets no baseline
        st["ac_baseline"] = nxt
    save_state(sp, st)
    print(f"build_page: {sp} marked as published ({st['published_hash']})")
    return 0


def build(info: dict, sp: Path, out: Path, lang: str | None) -> int:
    st = load_state(sp)
    current = page_hash(info)
    published = st.get("published_hash")
    if published and published != current:
        print(f"  STALE the published page ({st.get('artifact_url') or 'no link'}) is from {published}; "
              f"the current one is {current}: build and publish again", file=sys.stderr)

    page, errors, warns = page_data(info, lang or st.get("lang"))
    page["hash"] = current
    page["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    page["profile"] = info["profile"]
    if info.get("version"):
        page["version"] = info["version"]
    e2, w2 = validate(page, info, st)
    errors += e2
    warns += w2

    # What changed since it was validated (review_fingerprints) or since the last publish.
    stale = {}
    old = st.get("published_fingerprints") or {}
    val_fp = st.get("review_fingerprints") or {}
    marked = reviewed_keys(page, info, st)
    now = fingerprints(page, info)
    for key, val in now.items():
        base = val_fp.get(key) if key in marked else old.get(key)
        if base is None or base == val:
            continue
        stale[key] = True
        if key in marked:
            print(f"  RECHECK {key}: was validated/confirmed/rejected, but the text changed since", file=sys.stderr)
    page["stale"] = stale
    page["rows"] = row_keys(page, info)
    page["xref"], page["covers"] = xrefs(page, info, page["rows"])
    # The page stores the fingerprint of the text the user validated (db review/<key>.fp) and shows
    # "changed since" when it stops matching.
    page["fingerprints"] = now
    page["acChanges"], _ = ac_review(page, info, st, now)
    for key, x in page["acChanges"]["items"].items():
        print(f"  AC-{x['st'].upper()} {x['cite']}: {'new criterion' if x['st'] == 'new' else 'was: ' + x['was'][:70]}", file=sys.stderr)
    for sid, x in page["acChanges"]["removed"].items():
        print(f"  AC-REMOVED {sid}: {len(x['texts'])} criterion(s) no longer in the document", file=sys.stderr)
    for w in warns:
        print(f"  WARN  {w}", file=sys.stderr)
    for e in errors:
        print(f"  ERROR {e}", file=sys.stderr)
    if errors:
        print(f"build_page: {len(errors)} error(s); page not built", file=sys.stderr)
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    title = st.get("title") or page["title"]
    html = (html.replace("__LANG__", page["lang"])
                .replace("__TITLE__", title.replace("&", "&amp;").replace("<", "&lt;"))
                .replace("__DOC_JSON__", as_script_json(page))
                .replace("__STATE_JSON__", as_script_json(st)))
    out.write_text(html, encoding="utf-8")
    # The images travel with the page, at the path the document uses. Resolved first: an image (a
    # symlink included) is read only from inside the documents' folder and written only inside the page's.
    images = page["images"]
    out_dir = out.resolve().parent
    doc_dir = page_base(info).resolve()
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
    n_rows = sum(len(v) for v in page["rows"].values())
    n_mmd = sum(1 for s in page["sections"] for b in s["blocks"] if b["type"] == "code" and b["lang"] == "mermaid")
    per_tab = ""
    if page.get("tabs"):
        counts = {}
        for c in page["coverage"]:
            counts[c[4]] = counts.get(c[4], 0) + 1
        per_tab = " (" + " · ".join(f"{t['id']} {counts.get(t['id'], 0)}" if t["exists"] else f"{t['id']} -" for t in page["tabs"]) + ")"
    print(f"build_page: {out} ({len(page['sections'])} sections, {n_rows} reviewable rows, {n_mmd} diagrams, "
          f"{len(page['coverage'])} pieces covered{per_tab}, lang {page['lang']}, {current}, {len(warns)} warning(s))")
    return 0
