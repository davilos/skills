#!/usr/bin/env python3
"""Build the HTML review page for a plan: plan.md + review-page.json + template.

Validates review-page.json against the plan before building. Error (exit 1) when the
page would misstate or hide something in the plan; warning when it is only poorer.

Also proves coverage: every content piece of plan.md must be in the page data
(coverage.py), and the page carries the list so check_page.cjs can look for it in
the rendered text. And it stamps the version: plan.md hash and build time at the top
of the page; warns when the plan changed since the last publish.

Usage:
    python3 build_page.py --root <project> <feature> --out <file.html>
        [--data <path to review-page.json>]   (default: .specs/features/<feature>/review-page.json)
    python3 build_page.py --root <project> <feature> --mark-published
        (after publishing: records in review-page.json the hash of the plan that went live)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from coverage import missing_in_data, rendered_pieces, unsupported_markdown  # noqa: E402
from extract_plan import extract  # noqa: E402


def plan_hash(plan_path: Path) -> str:
    return hashlib.sha256(plan_path.read_bytes()).hexdigest()[:12]


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def fingerprints(plan: dict, pg: dict) -> dict[str, str]:
    """Fingerprint of every part of the plan something on the page depends on.

    Sections, slices and doors: what the user validates. Derived items (Impact card,
    Flow path, change, symptom, Problem visual): the part of the plan they were drawn
    from. Recorded by --mark-published; on the next build, whatever differs becomes
    "changed since" / "re-check: the plan changed here" on the page.
    """
    fp: dict[str, str] = {}
    secs = {s["id"]: s for s in plan["sections"]}
    for sid, s in secs.items():
        fp[sid] = _h(s.get("blocks") or s.get("criteria"))
    slices = secs.get("criteria", {}).get("criteria", {}).get("slices", [])
    acs = {}
    for sl in slices:
        fp[sl["id"]] = _h(sl)
        for a in sl["acs"]:
            acs[a["n"]] = a["text"]
    land = [b for b in secs.get("landing", {}).get("blocks", []) if b["type"] == "table"]
    for k, row in enumerate(land[0]["rows"] if land else [], 1):
        fp[f"door:{k}"] = _h(row)

    def cited(text):
        return [acs.get(n) for n in cited_acs(text)]

    problem = secs.get("problem", {}).get("blocks")
    pv = pg.get("problem_visual") or {}
    if pv:
        fp["problem-visual"] = _h(problem)
    for i, x in enumerate(pv.get("symptoms", [])):
        fp[f"symptom:{i}"] = _h([problem, cited((x.get("fix") or {}).get("proof"))])
    flow_items = [it for b in secs.get("flow", {}).get("blocks", []) if b["type"] == "ol" for it in b["items"]]
    for i, p in enumerate((pg.get("flow_visual") or {}).get("paths", [])):
        hop = p.get("hop")
        fp[f"flow:{i}"] = _h(flow_items[hop - 1] if hop and hop <= len(flow_items) else None)
    imp = [b for b in secs.get("impact", {}).get("blocks", []) if b["type"] == "table"]
    rows = imp[0]["rows"] if imp else []
    for i, c in enumerate((pg.get("impact_visual") or {}).get("cards", [])):
        r = c.get("row")
        fp[f"impact:{i}"] = _h([rows[r] if r is not None and r < len(rows) else None, cited(c.get("proof"))])
    for i, c in enumerate(pg.get("changes", [])):
        fp[f"change:{i}"] = _h([c.get("s"), cited(c.get("proof"))])
    land_rows = land[0]["rows"] if land else []
    for d in (pg.get("landing_visual") or {}).get("doors", []):
        n = d.get("n")
        if isinstance(n, int) and 1 <= n <= len(land_rows):
            fp[f"landing:{n}"] = _h([land_rows[n - 1], cited(d.get("proof"))])
    return fp

def validated_keys(pg: dict) -> set[str]:
    """Validated sections and slices and confirmed doors in review-page.json."""
    keys = {k for k, ok in (pg.get("review") or {}).items() if ok}
    return keys | {f"door:{n}" for n in pg.get("doors_confirmed", [])}


TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "template.html"
AC_NUM = re.compile(r"\d+")
# The same runs the template turns into links: "AC 10 to 12", "AC 1–3", "AC 10, 12", "AC 5 and 6".
# Portuguese "a" / "e" still read as "to" / "and".
AC_RUN = re.compile(r"\bAC\s+\d+(?:\s*(?:,|–|-|\bto\b|\band\b|\ba\b|\be\b)\s*\d+)*")
AC_STEP = re.compile(r"(\d+)|(–|-|\bto\b|\ba\b)")
DERIVED = ("impact:", "flow:", "change:", "symptom:", "problem-visual", "landing:")


def cited_acs(text: str) -> list[int]:
    """Cited criteria, ranges expanded: "AC 13–15, 18" → [13, 14, 15, 18]."""
    out: list[int] = []
    for run in AC_RUN.findall(text or ""):
        prev, ranged = None, False
        for num, sep in AC_STEP.findall(run[2:]):
            if sep:
                ranged = True
                continue
            n = int(num)
            if ranged and prev is not None:
                out.extend(range(prev + 1, n + 1))
            else:
                out.append(n)
            prev, ranged = n, False
    return out


def as_script_json(data) -> str:
    # `</` would close the <script>; U+2028/2029 break old JS strings.
    return (json.dumps(data, ensure_ascii=False)
            .replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def validate(plan: dict, pg: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    sections = {s["id"]: s for s in plan["sections"]}
    crit = sections.get("criteria", {}).get("criteria", {"slices": []})
    slice_ids = [s["id"] for s in crit["slices"]]
    ac_nums = {a["n"] for s in crit["slices"] for a in s["acs"]}

    if not plan["title"]:
        errors.append("plan.md has no title (# ...)")
    for want in ("problem", "flow", "impact", "landing", "criteria"):
        if want not in sections:
            warns.append(f"plan has no {want} section")

    review = pg.get("review", {})
    for k in review:
        if k not in sections and k not in slice_ids:
            errors.append(f"review.{k}: not a section or slice of the plan")
    for sid in sections:
        if sid not in review:
            warns.append(f"review has no '{sid}': the section shows as 'not reviewed'")

    changes = pg.get("changes", [])
    for i, c in enumerate(changes):
        where = f"changes[{i}]"
        if c.get("s") not in slice_ids:
            errors.append(f"{where}.s = {c.get('s')!r} is not a slice of the plan ({', '.join(slice_ids)})")
        for key in ("neu", "where", "why", "proof"):
            if not c.get(key):
                errors.append(f"{where} has no '{key}' (Where / Why / Proof are required)")
        for n in AC_NUM.findall(c.get("proof", "")):
            if int(n) not in ac_nums:
                errors.append(f"{where}.proof cites criterion {n}, which is not in the plan")

    pv = pg.get("problem_visual")
    if pv:
        n_pays = len(pv.get("pays", []))
        for i, x in enumerate(pv.get("symptoms", [])):
            where = f"problem_visual.symptoms[{i}]"
            for key in ("what", "today"):
                if not x.get(key):
                    errors.append(f"{where} has no '{key}'")
            if not x.get("where"):
                warns.append(f"{where} has no 'where' (the open card shows no Where)")
            fix = x.get("fix")
            if not fix:
                warns.append(f"{where} has no 'fix' (the open card does not say what fixes it)")
            else:
                if fix.get("slice") not in slice_ids:
                    errors.append(f"{where}.fix.slice = {fix.get('slice')!r} is not a slice of the plan")
                for n in AC_NUM.findall(fix.get("proof", "")):
                    if int(n) not in ac_nums:
                        errors.append(f"{where}.fix.proof cites criterion {n}, which is not in the plan")
            for p in x.get("pays", []):
                if not (0 <= p < n_pays):
                    errors.append(f"{where}.pays has {p}, outside problem_visual.pays ({n_pays})")
        hit = {p for x in pv.get("symptoms", []) for p in x.get("pays", [])}
        for p in range(n_pays):
            if p not in hit:
                warns.append(f"problem_visual.pays[{p}] highlights no symptom")

    fv = pg.get("flow_visual")
    if fv:
        flow_items = [b for b in sections.get("flow", {}).get("blocks", []) if b["type"] == "ol"]
        n_hops = sum(len(b["items"]) for b in flow_items)
        hops_seen = set()
        # A node repeated across paths opens its card only the first time; elsewhere it stays
        # green and unclickable, so the page does not repeat the same Where / Why / Proof.
        card_at = {}
        for pi, p in enumerate(fv.get("paths", [])):
            for ni, nd in enumerate(p.get("nodes", [])):
                if nd.get("change") is not None:
                    if nd.get("n") in card_at:
                        errors.append(f"flow_visual.paths[{pi}].nodes[{ni}] repeats the card of `{nd['n']}`, which already opens in paths[{card_at[nd['n']]}]: remove `change` here")
                    else:
                        card_at[nd.get("n")] = pi
        for pi, p in enumerate(fv.get("paths", [])):
            if p.get("hop"):
                hops_seen.add(p["hop"])
                if n_hops and p["hop"] > n_hops:
                    errors.append(f"flow_visual.paths[{pi}].hop = {p['hop']}, but the Flow has {n_hops} hops")
            for ni, nd in enumerate(p.get("nodes", [])):
                if nd.get("change") is not None and not (0 <= nd["change"] < len(changes)):
                    errors.append(f"flow_visual.paths[{pi}].nodes[{ni}].change is outside changes")
                if (nd.get("o") or nd.get("note")) and nd.get("change") is None and nd.get("n") not in card_at:
                    warns.append(f"flow_visual.paths[{pi}].nodes[{ni}] changes but points to no change (no Where/Why/Proof)")
        missing = [h for h in range(1, n_hops + 1) if h not in hops_seen]
        if n_hops and missing:
            errors.append(f"flow_visual does not cover Flow hops {missing}")

    iv = pg.get("impact_visual")
    if iv:
        tables = [b for b in sections.get("impact", {}).get("blocks", []) if b["type"] == "table"]
        rows = tables[0]["rows"] if tables else []
        covered = set()
        groups = {g[0] for g in iv.get("groups", [])}
        for ci, c in enumerate(iv.get("cards", [])):
            r = c.get("row")
            if r is None or not (0 <= r < len(rows)):
                errors.append(f"impact_visual.cards[{ci}].row = {r!r} is outside the Impact table ({len(rows)} rows)")
            else:
                covered.add(r)
            if c.get("g") not in groups:
                errors.append(f"impact_visual.cards[{ci}].g = {c.get('g')!r} is not in groups")
            # A card with the `keep` list: the list is the content, and Where is optional.
            for key in ("why", "proof") if c.get("keep") else ("where", "why", "proof"):
                if not c.get(key):
                    errors.append(f"impact_visual.cards[{ci}] has no '{key}'")
            # Proof becomes a link to every criterion cited in "AC ..."; all must exist.
            for run in AC_RUN.findall(c.get("proof", "")):
                for n in AC_NUM.findall(run):
                    if int(n) not in ac_nums:
                        errors.append(f"impact_visual.cards[{ci}].proof cites criterion {n}, which is not in the plan")
            for a in c.get("who", []):
                if a not in iv.get("audiences", []):
                    errors.append(f"impact_visual.cards[{ci}].who has {a!r}, which is not in audiences")
        uncovered = [i for i in range(len(rows)) if i not in covered]
        if uncovered:
            errors.append(f"impact_visual has no card for Impact rows {uncovered} (the page must show everything)")

    landing = sections.get("landing")
    if landing:
        tables = [b for b in landing.get("blocks", []) if b["type"] == "table"]
        n_doors = len(tables[0]["rows"]) if tables else 0
        for n in pg.get("doors_confirmed", []):
            if not (1 <= n <= n_doors):
                errors.append(f"doors_confirmed has {n}, but the Landing has {n_doors} doors")
        # Landing in plain language: every door in the plan has its explanation, and only those.
        lv = pg.get("landing_visual")
        if n_doors and not lv:
            errors.append(f"the Landing has {n_doors} door(s) and review-page.json has no landing_visual: "
                          "the page must explain each door in plain language (references/review-page-json.md)")
        if lv:
            seen = set()
            for i, d in enumerate(lv.get("doors", [])):
                n = d.get("n")
                if not (isinstance(n, int) and 1 <= n <= n_doors):
                    errors.append(f"landing_visual.doors[{i}].n = {n!r}, but the Landing has {n_doors} doors")
                    continue
                seen.add(n)
                for key in ("title", "decide", "choice", "hard"):
                    if not d.get(key):
                        errors.append(f"landing_visual.doors[{i}] (door {n}) has no '{key}'")
                for a in cited_acs(d.get("proof") or ""):
                    if a not in ac_nums:
                        errors.append(f"landing_visual.doors[{i}].proof cites criterion {a}, which is not in the plan")
            missing = [n for n in range(1, n_doors + 1) if n not in seen]
            if missing:
                errors.append(f"landing_visual does not explain Landing doors {missing}")
    return errors, warns


# File reference with optional lines ("executor.py:49-55,895-917").
FILE_REF = re.compile(r"([\w./-]*\w\.[A-Za-z][A-Za-z0-9]{0,9})(?::(\d[\d,\-–]*\d|\d))?")
# A Where item: a file with an extension and optional lines, or a folder path ending in /.
CODE_REF = re.compile(r"[\w./{}-]+(?:\.\w+(?::\d[\d,\-–]*)?|/)")
# An identifier as the page shows it in code: has _, / or an extension.
IDENT = re.compile(r"[A-Za-z0-9/][\w/.{}-]*(?:_|/|\.[a-z]{2,4}\b)[\w/.{}-]*")


def _ranges(spec: str) -> list[tuple[int, int]]:
    out = []
    for part in (spec or "").split(","):
        m = re.fullmatch(r"\s*(\d+)\s*(?:[-–]\s*(\d+))?\s*", part)
        if m:
            out.append((int(m[1]), int(m[2] or m[1])))
    return out


def _same_file(a: str, b: str) -> bool:
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def check_refs(plan_text: str, pg: dict) -> tuple[list[str], list[str]]:
    """What the page states agrees with the plan, without reading the code (that is the plan author's job).

    Rejects: a new name the plan does not have (without `tbd`); a Where with prose instead of only
    references; a line range that diverges from the same range in the plan. Warns: the same Where on
    two items of the same kind; different Flow nodes opening the same change without `shared: true`.
    """
    errors, warns = [], []
    # 1. New name: every identifier in it is in the plan, or the item says `tbd`.
    named = [(f"changes[{i}].neu", c.get("neu"), c) for i, c in enumerate(pg.get("changes", []))]
    named += [(f"impact_visual.cards[{i}].after", c.get("after"), c) for i, c in enumerate((pg.get("impact_visual") or {}).get("cards", []))]
    for pi, p in enumerate((pg.get("flow_visual") or {}).get("paths", [])):
        named += [(f"flow_visual.paths[{pi}].nodes[{ni}].n", x.get("n"), x) for ni, x in enumerate(p.get("nodes", [])) if x.get("o") or x.get("note")]
    for label, name, it in named:
        if not name or it.get("tbd"):
            continue
        # A name made of parts the plan fixes (new package + existing function) is not invented.
        absent = [t for t in IDENT.findall(name) if t.rstrip(".,-") not in plan_text
                  and not all(p in plan_text for p in re.split(r"[/.]", t.rstrip(".,-")) if p)]
        if absent:
            errors.append(f"{label} = {name!r}: {', '.join(absent)} is not in the plan; a name the plan does not fix takes tbd: true (never invented)")

    # 2 to 4. Where.
    plan_refs = [(m[1], _ranges(m[2])) for m in FILE_REF.finditer(plan_text) if m[2]]
    items = [(f"changes[{i}]", c) for i, c in enumerate(pg.get("changes", []))]
    items += [(f"impact_visual.cards[{i}]", c) for i, c in enumerate((pg.get("impact_visual") or {}).get("cards", []))]
    items += [(f"problem_visual.symptoms[{i}]", c) for i, c in enumerate((pg.get("problem_visual") or {}).get("symptoms", []))]
    seen = {}
    for label, it in items:
        w = (it.get("where") or "").strip()
        if not w:
            continue
        # Where is code references only; the explanation goes in Why.
        prose = [x for x in re.split(r"\s+·\s+", w) if not CODE_REF.fullmatch(x)]
        if prose:
            errors.append(f"{label}.where has prose, not only code references: {prose}; Where takes file[:lines] or folder/, separated by ' · ', and the explanation goes in why")
        for field in ("where", "why"):
            loose = re.findall(r"\(:\d[\d,\-–]*\)", it.get(field) or "")
            if loose:
                errors.append(f"{label}.{field} has a line without a file {', '.join(loose)}: write file:line (e.g. billing.py:187)")
        # A range overlapping a plan range in the same file must equal it. A single line, or a range
        # the plan does not cite, is the page author's own reading and passes.
        for m in FILE_REF.finditer(w):
            for a, b in _ranges(m[2]):
                if a == b:
                    continue
                for pf, pr in plan_refs:
                    if not _same_file(m[1], pf):
                        continue
                    clash = [(x, y) for x, y in pr if y > x and x <= b and a <= y and (x, y) != (a, b)]
                    if clash:
                        x, y = clash[0]
                        errors.append(f"{label}.where cites {m[1]}:{a}-{b}, but the plan cites {pf}:{x}-{y}: copy the plan's lines")
        key = (label.split("[")[0], w)
        if key in seen:
            warns.append(f"{label}.where equals that of {seen[key]}: each item shows its own Where")
        else:
            seen[key] = label

    # 5. Different nodes with the same change.
    by_change = {}
    for pi, p in enumerate((pg.get("flow_visual") or {}).get("paths", [])):
        for x in p.get("nodes", []):
            if x.get("change") is not None and not x.get("shared"):
                by_change.setdefault(x["change"], set()).add(x.get("n"))
    for ch, names in sorted(by_change.items()):
        if len(names) > 1:
            warns.append(f"flow_visual: {', '.join(sorted(names))} open the same change changes[{ch}]; if Where / Why / Proof "
                         "are not the same, give each its own; if they are, mark shared: true")
    return errors, warns


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--data")
    ap.add_argument("--out")
    ap.add_argument("--mark-published", action="store_true",
                    help="record in review-page.json the hash of the plan.md that just went live")
    ap.add_argument("feature")
    args = ap.parse_args()
    if not args.out and not args.mark_published:
        ap.error("pass --out <file.html> or --mark-published")

    feat = Path(args.root) / ".specs" / "features" / args.feature
    plan_path = feat / "plan.md"
    pg_path = Path(args.data) if args.data else feat / "review-page.json"
    if not plan_path.exists():
        print(f"build_page: {plan_path} not found", file=sys.stderr)
        return 1
    if not pg_path.exists():
        print(f"build_page: {pg_path} not found (write review-page.json: references/review-page-json.md)", file=sys.stderr)
        return 1

    pg = json.loads(pg_path.read_text(encoding="utf-8"))
    current = plan_hash(plan_path)

    if args.mark_published:
        now = fingerprints(extract(plan_path), pg)
        pg["published_plan_hash"] = current
        pg["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        # A validated section's fingerprint is that of the text the user validated, not of this
        # publish: if it were recomputed here, "changed since" would vanish on the next publish
        # without anyone validating again. Only items without a fingerprint get one.
        # Old file without the map: the best reference is the previous publish.
        kept = pg["review_fingerprints"] if "review_fingerprints" in pg else (pg.get("published_fingerprints") or {})
        pg["review_fingerprints"] = {k: kept.get(k) or now[k] for k in sorted(validated_keys(pg)) if k in now}
        pg["published_fingerprints"] = now
        pg_path.write_text(json.dumps(pg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"build_page: {pg_path} marked as published (plan.md {current})")
        return 0

    published = pg.get("published_plan_hash")
    if published and published != current:
        print(f"  STALE the published page ({pg.get('artifact_url') or 'no link'}) is from plan.md {published}; "
              f"the current plan.md is {current}: build and publish again", file=sys.stderr)

    plan = extract(plan_path)
    plan["path"] = str(plan_path.relative_to(args.root)) if plan_path.is_relative_to(args.root) else str(plan_path)
    plan["hash"] = current
    plan["generated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    errors, warns = validate(plan, pg)
    ref_errors, ref_warns = check_refs(plan_path.read_text(encoding="utf-8"), pg)
    errors += ref_errors
    warns += ref_warns
    # Coverage, end 1: every content piece of plan.md is in the extracted data.
    for line, piece in missing_in_data(plan_path, plan):
        errors.append(f"coverage: plan.md:{line} did not reach the page data: {piece[:80]!r}")
    # End 2 goes into the page: check_page.cjs looks for each piece in the rendered text.
    plan["coverage"] = rendered_pieces(plan_path)
    for line, what in unsupported_markdown(plan_path):
        warns.append(f"plan.md:{line} uses {what}, which the page shows as raw text")

    # What changed in the plan since the last publish.
    # Derived item: compared with the last publish. Validated section, slice and door: with the
    # text the user validated (review_fingerprints), which publishing does not recompute.
    stale = {"sections": {}, "derived": {}}
    old = pg.get("published_fingerprints") or {}
    # Validated by hand with no fingerprint yet: the current text counts. Old file without the map: the previous publish.
    val_fp = pg["review_fingerprints"] if "review_fingerprints" in pg else old
    validated = validated_keys(pg)
    now = fingerprints(plan, pg)
    for key, val in now.items():
        if key.startswith(DERIVED):
            if key in old and old[key] != val:
                stale["derived"][key] = True
                print(f"  RECHECK {key}: the part of the plan this was drawn from changed; review Where / Why / Proof", file=sys.stderr)
            continue
        base = val_fp.get(key) if key in validated else old.get(key)
        if base is None or base == val:
            continue
        stale["sections"][key] = True
        if key in validated:
            print(f"  RECHECK {key}: was validated/confirmed, but the text changed since", file=sys.stderr)
    plan["stale"] = stale
    # Current fingerprint of each section, slice and door: the page records the one of the text the
    # user validated (db review/<key>.fp) and shows "changed since" when it stops matching.
    plan["fingerprints"] = {k: v for k, v in fingerprints(plan, pg).items() if not k.startswith(DERIVED)}
    for w in warns:
        print(f"  WARN  {w}", file=sys.stderr)
    for e in errors:
        print(f"  ERROR {e}", file=sys.stderr)
    if errors:
        print(f"build_page: {len(errors)} error(s); page not built", file=sys.stderr)
        return 1

    html = TEMPLATE.read_text(encoding="utf-8")
    title = pg.get("title") or plan["title"]
    html = (html.replace("__TITLE__", title.replace("<", "&lt;"))
                .replace("__PLAN_JSON__", as_script_json(plan))
                .replace("__PAGE_DATA_JSON__", as_script_json(pg)))
    Path(args.out).write_text(html, encoding="utf-8")
    n_acs = sum(len(s["acs"]) for s in next((x["criteria"]["slices"] for x in plan["sections"] if x["id"] == "criteria"), []))
    print(f"build_page: {args.out} ({len(plan['sections'])} sections, {n_acs} criteria, {len(pg.get('changes', []))} changes, "
          f"{len(plan['coverage'])} plan pieces covered, plan.md {current}, {len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
