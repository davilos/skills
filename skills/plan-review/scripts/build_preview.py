#!/usr/bin/env python3
"""Build the optional UI preview for a plan: before/after mockups of the screens it changes.

The preview is a separate page from the review page: plan.md + ui-preview.json + one static HTML
fragment per screen state (ui-preview/<file>). It is a reading of the code and the plan, never the
plan itself. Validates ui-preview.json against the plan before building: every mark names a slice
and criteria the plan has and points at an element of the mockup; fragments stay static and offline.

Usage:
    python3 build_preview.py --root <project> <feature> --detect
        (does the plan change what the user sees? ui: yes / code-only / no, with the evidence; exit 0)
    python3 build_preview.py --root <project> <feature> --out <file.html>
    python3 build_preview.py --root <project> <feature> --mark-published
        (after publishing: records in ui-preview.json the plan that went live)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # no __pycache__ in the skill folder: the registry would ship it
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_page import AC_NUM, CODE_REF, _h, as_script_json, cited_acs, plan_hash  # noqa: E402
from extract_plan import extract  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "preview-template.html"
# A file the user sees rendered: markup, styles, templates. Only an offer to build the preview, so
# a false positive costs one question.
UI_FILE = re.compile(r"[\w./{}\[\]-]+\.(?:tsx|jsx|vue|svelte|astro|html?|css|scss|sass|less|erb|hbs|ejs|njk|twig|cshtml|razor|blade\.php)\b")
UI_DIR = re.compile(r"[\w./-]*\b(?:components|pages|views|screens|layouts|ui|templates)/[\w./{}\[\]-]*")
# A criterion about what the user sees: on screen, in words or state (English and Portuguese plans).
# Only filters the offer: code-only front-end plans (a hook, a renamed CSS variable) are not asked.
VISIBLE = re.compile(
    r"\b(?:shows?|shown|displays?|displayed|renders?|rendered|visible|hidden|hides?|appears?|"
    r"button|link|label|copy|title|heading|text|message|page|screen|card|dialog|modal|menu|tab|form|field|input|"
    r"icon|colou?r|amber|red|green|layout|header|footer|banner|toast|tooltip|badge|bar|disabled|enabled|empty state|"
    r"placeholder|highlight|hints?|says?|panel|switch|toggle|warning|indicator|selector|"
    r"mostra|mostrar|exibe|exibir|aparece|aparecer|diz|dizer|botão|botões|tela|página|texto|campo|cor|títulos?|ícones?|"
    r"rótulos?|cartão|cartões|avisos?|painel|indicador|seletor|desabilitad[oa]|habilitad[oa])\b",
    re.I)
MARK = re.compile(r"""\bdata-mark\s*=\s*["']?(\d+)""")
# What a fragment must not carry: it renders inside the page, offline and without code.
UNSAFE = [
    (re.compile(r"<\s*script\b", re.I), "a <script> (mockups are static)"),
    (re.compile(r"\son[a-z]+\s*=", re.I), "an inline event handler (on...=)"),
    (re.compile(r"<\s*(?:iframe|object|embed|link|meta|base)\b", re.I), "an <iframe>/<object>/<embed>/<link>/<meta>/<base>"),
    (re.compile(r"""(?:src|href|action)\s*=\s*["']?\s*(?:https?:|//|javascript:)""", re.I), "an external or javascript: URL"),
    (re.compile(r"""url\(\s*["']?\s*(?:https?:|//)""", re.I), "an external url() in CSS"),
    (re.compile(r"@import\b", re.I), "a CSS @import"),
]
# What a mark says about its element: it arrives, changes or goes away. "same" and "effect" have no
# element: a criterion the screen keeps as today, or one that acts elsewhere (a request, another screen).
DRAWN_KINDS = ("add", "change", "remove")
NOTE_KINDS = ("same", "effect")
BIG_FRAGMENT = 30_000  # bytes: above it the mockup likely draws more than the change needs


def detect(plan_text: str) -> list[str]:
    hits = []
    for m in list(UI_FILE.finditer(plan_text)) + list(UI_DIR.finditer(plan_text)):
        ref = m[0].strip(".,;:")
        if ref not in hits:
            hits.append(ref)
    # `PlanCard.tsx` cited alone is the same file as `src/components/PlanCard.tsx`.
    return [h for h in hits if not any(o != h and o.endswith("/" + h) for o in hits)]


def visible_criteria(plan: dict) -> list[tuple[int, str]]:
    """Criteria that describe something the user sees: the evidence that a preview has anything to show."""
    return [(a["n"], a["text"]) for s in slice_map(plan).values() for a in s["acs"] if VISIBLE.search(a["text"])]


def slice_map(plan: dict) -> dict[str, dict]:
    crit = next((s for s in plan["sections"] if s["id"] == "criteria"), {}).get("criteria", {"slices": []})
    return {s["id"]: s for s in crit["slices"]}


def fingerprints(plan: dict, pv: dict) -> dict[str, str]:
    """Fingerprint of the slice and criteria each mark was drawn from: if they change, re-check the mark."""
    slices = slice_map(plan)
    acs = {a["n"]: a["text"] for s in slices.values() for a in s["acs"]}
    fp = {}
    for sc in pv.get("screens", []):
        for j, mk in enumerate(sc.get("marks", [])):
            key = f"note:{sc.get('id')}:{j}" if mk.get("kind") in NOTE_KINDS else f"mark:{sc.get('id')}:{mk.get('n')}"
            fp[key] = _h([slices.get(mk.get("s")), [acs.get(n) for n in cited_acs(mk.get("proof"))]])
    return fp


def views(sc: dict) -> list[tuple[str | None, str | None, str | None]]:
    """(state, before, after) for each state of a screen; a state without its own before or after uses the screen's."""
    if not sc.get("states"):
        return [(None, sc.get("before"), sc.get("after"))]
    return [(st.get("id"), st["before"] if "before" in st else sc.get("before"),
             st["after"] if "after" in st else sc.get("after")) for st in sc["states"]]


def validate(plan: dict, pv: dict, frag_dir: Path) -> tuple[list[str], list[str], dict[str, str]]:
    errors, warns, frags = [], [], {}
    slices = slice_map(plan)
    ac_nums = {a["n"] for s in slices.values() for a in s["acs"]}
    screens = pv.get("screens") or []
    if not screens:
        errors.append("ui-preview.json has no screens")
    ids = set()
    for i, sc in enumerate(screens):
        where = f"screens[{i}]"
        sid = sc.get("id")
        if not sid or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
            errors.append(f"{where}.id = {sid!r}: use a kebab-case id (it becomes the screen's anchor)")
        elif sid in ids:
            errors.append(f"{where}.id = {sid!r} repeats another screen")
        ids.add(sid)
        if not sc.get("name"):
            errors.append(f"{where} has no 'name'")
        states = sc.get("states")
        state_ids = []
        if states is not None and (not isinstance(states, list) or not states):
            errors.append(f"{where}.states is empty: leave it out for a screen with a single state")
            states = sc["states"] = []
        for k, st in enumerate(states or []):
            st_id = st.get("id")
            if not st_id or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", st_id):
                errors.append(f"{where}.states[{k}].id = {st_id!r}: use a kebab-case id")
            elif st_id in state_ids:
                errors.append(f"{where}.states[{k}].id = {st_id!r} repeats another state")
            state_ids.append(st_id)
            if not st.get("label"):
                errors.append(f"{where}.states[{k}] has no 'label' (the tab the reviewer clicks)")
        vws = views(sc)
        if not any(b or a for _, b, a in vws):
            errors.append(f"{where} has neither 'before' nor 'after'")
        w = (sc.get("where") or "").strip()
        if not w:
            warns.append(f"{where} has no 'where' (which files the mockup was drawn from)")
        prose = [x for x in re.split(r"\s+·\s+", w) if w and not CODE_REF.fullmatch(x)]
        if prose:
            errors.append(f"{where}.where has prose, not only code references: {prose}; the explanation goes in a mark's text")
        marked = {}  # fragment file -> numbers of the data-mark elements in it
        files = [(key, sc.get(key)) for key in ("before", "after", "css")]
        files += [(f"states[{k}].{side}", st.get(side)) for k, st in enumerate(states or []) for side in ("before", "after")]
        for key, name in files:
            if not name:
                continue
            if name not in frags:
                path = frag_dir / name
                if path.parent != frag_dir or not path.exists():
                    errors.append(f"{where}.{key} = {name!r} is not a file in {frag_dir}")
                    continue
                text = frags[name] = path.read_text(encoding="utf-8")
                for rx, what in UNSAFE:
                    if rx.search(text):
                        errors.append(f"{name} has {what}: fragments are static HTML and CSS, with no external resources")
                if len(text.encode()) > BIG_FRAGMENT:
                    warns.append(f"{name} has {len(text.encode()) // 1000} KB: draw only the region that changes, the rest as .ph placeholders (references/ui-preview.md)")
            if key != "css":
                marked[name] = {int(n) for n in MARK.findall(frags[name])}
        if not states and sc.get("before") and sc.get("after") and sc["before"] == sc["after"]:
            errors.append(f"{where}: before and after are the same file")
        seen = set()
        for j, mk in enumerate(sc.get("marks") or []):
            at = f"{where}.marks[{j}]"
            n, kind = mk.get("n"), mk.get("kind")
            if kind is not None and kind not in DRAWN_KINDS + NOTE_KINDS:
                errors.append(f"{at}.kind = {kind!r}: use one of {', '.join(DRAWN_KINDS + NOTE_KINDS)}, or leave it out")
            note = kind in NOTE_KINDS
            if note:
                if n is not None:
                    errors.append(f"{at}: a '{kind}' mark has no number and no element; drop 'n' (or use add/change/remove)")
            elif not isinstance(n, int) or n < 1:
                errors.append(f"{at}.n = {n!r}: marks are numbered 1, 2, 3...")
                continue
            elif n in seen:
                errors.append(f"{at}.n = {n} repeats another mark of this screen")
            seen.add(n)
            for key in ("text", "s", "proof"):
                if not mk.get(key):
                    errors.append(f"{at} has no '{key}' (what changes, the slice and the criteria that require it)")
            if mk.get("s") and mk["s"] not in slices:
                errors.append(f"{at}.s = {mk['s']!r} is not a slice of the plan ({', '.join(slices)})")
            for num in AC_NUM.findall(mk.get("proof") or ""):
                if int(num) not in ac_nums:
                    errors.append(f"{at}.proof cites criterion {num}, which is not in the plan")
            ms = mk.get("states")
            if ms is not None:
                if not states:
                    errors.append(f"{at}.states: the screen has no states; leave it out")
                elif not isinstance(ms, list) or not ms:
                    errors.append(f"{at}.states is empty: leave it out for a mark that holds in every state")
                else:
                    for x in ms:
                        if x not in state_ids:
                            errors.append(f"{at}.states names {x!r}, which is not a state of this screen ({', '.join(map(str, state_ids))})")
            for st_id, b, a in [] if note else vws:
                if states and isinstance(ms, list) and ms and st_id not in ms:
                    continue
                if not any(n in marked.get(f, ()) for f in (b, a) if f):
                    in_state = f" of state {st_id!r}" if st_id else ""
                    errors.append(f"{at}: no element in the mockup{in_state} has data-mark=\"{n}\" (put it on the element that changes)")
            mw = (mk.get("where") or "").strip()
            if mw and any(not CODE_REF.fullmatch(x) for x in re.split(r"\s+·\s+", mw)):
                errors.append(f"{at}.where has prose; Where takes file[:lines] or folder/, separated by ' · '")
        # Every highlight a state shows needs a mark that holds in that state.
        for st_id, b, a in vws:
            holds = {mk.get("n") for mk in sc.get("marks") or [] if mk.get("kind") not in NOTE_KINDS
                     if not states or not isinstance(mk.get("states"), list) or not mk["states"] or st_id in mk["states"]}
            for f in (b, a):
                for n in sorted(marked.get(f, set()) - holds):
                    in_state = f" (state {st_id!r})" if st_id else ""
                    errors.append(f"{where}: data-mark=\"{n}\" in {f}{in_state} has no entry in marks (every highlight says what changes and why)")
        if not sc.get("marks"):
            warns.append(f"{where} has no marks: the reviewer sees two pictures and no explanation of what changed")
    # A fragment shared by several states would repeat the same error once per state.
    return list(dict.fromkeys(errors)), warns, frags


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--data")
    ap.add_argument("--out")
    ap.add_argument("--detect", action="store_true", help="list the front-end files the plan cites")
    ap.add_argument("--mark-published", action="store_true",
                    help="record in ui-preview.json the plan.md that just went live")
    ap.add_argument("feature")
    args = ap.parse_args()
    if not (args.out or args.mark_published or args.detect):
        ap.error("pass --detect, --out <file.html> or --mark-published")

    feat = Path(args.root) / ".specs" / "features" / args.feature
    plan_path = feat / "plan.md"
    if not plan_path.exists():
        print(f"build_preview: {plan_path} not found", file=sys.stderr)
        return 1
    plan_text = plan_path.read_text(encoding="utf-8")

    if args.detect:
        hits = detect(plan_text)
        seen = visible_criteria(extract(plan_path)) if hits else []
        # yes: front-end files and criteria about what the user sees; code-only: the files change, the screen does not.
        print(f"ui: {'yes' if seen else 'code-only' if hits else 'no'}")
        if hits:
            print("  files: " + " · ".join(hits))
        for n, text in seen:
            print(f"  AC {n}: {text[:100]}")
        return 0

    pv_path = Path(args.data) if args.data else feat / "ui-preview.json"
    frag_dir = pv_path.parent / "ui-preview"
    if not pv_path.exists():
        print(f"build_preview: {pv_path} not found (write it: references/ui-preview.md)", file=sys.stderr)
        return 1
    pv = json.loads(pv_path.read_text(encoding="utf-8"))
    plan = extract(plan_path)
    current = plan_hash(plan_path)

    if args.mark_published:
        pv["published_plan_hash"] = current
        pv["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        pv["published_fingerprints"] = fingerprints(plan, pv)
        pv_path.write_text(json.dumps(pv, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"build_preview: {pv_path} marked as published (plan.md {current})")
        return 0

    published = pv.get("published_plan_hash")
    if published and published != current:
        print(f"  STALE the published preview ({pv.get('artifact_url') or 'no link'}) is from plan.md {published}; "
              f"the current plan.md is {current}: build and publish again", file=sys.stderr)
    errors, warns, frags = validate(plan, pv, frag_dir)
    old = pv.get("published_fingerprints") or {}
    stale = {}
    for key, val in fingerprints(plan, pv).items():
        if key in old and old[key] != val:
            stale[key] = True
            print(f"  RECHECK {key}: the slice or criteria this mark was drawn from changed; redraw it", file=sys.stderr)
    for w in warns:
        print(f"  WARN  {w}", file=sys.stderr)
    for e in errors:
        print(f"  ERROR {e}", file=sys.stderr)
    if errors:
        print(f"build_preview: {len(errors)} error(s); preview not built", file=sys.stderr)
        return 1

    # Slice and criterion links go to the review page, when it is published.
    review_url = pv.get("review_url")
    rp_path = feat / "review-page.json"
    if review_url is None and rp_path.exists():
        review_url = json.loads(rp_path.read_text(encoding="utf-8")).get("artifact_url") or ""
    data = {
        "title": pv.get("title") or f"{plan['title']} UI preview",
        "plan_title": plan["title"],
        "plan_path": str(plan_path.relative_to(args.root)) if plan_path.is_relative_to(args.root) else str(plan_path),
        "hash": current,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "code_ref": pv.get("code_ref") or "",
        "review_url": review_url or "",
        "slices": {k: s["title"] for k, s in slice_map(plan).items()},
        "stale": stale,
        # Fragments by file name: a state that reuses the screen's fragment does not repeat it in the page.
        "frags": frags,
        "screens": pv["screens"],
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__TITLE__", data["title"].replace("<", "&lt;")).replace("__PREVIEW_JSON__", as_script_json(data))
    Path(args.out).write_text(html, encoding="utf-8")
    n_marks = sum(len(sc.get("marks") or []) for sc in pv["screens"])
    print(f"build_preview: {args.out} ({len(pv['screens'])} screen(s), {n_marks} mark(s), "
          f"{sum(len(t.encode()) for t in frags.values()) // 1000} KB of mockup, plan.md {current}, {len(warns)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
