#!/usr/bin/env python3
"""Read `.specs/features/<feature>/plan.md` and print the plan as JSON.

This is the mechanical part of the page: the text of each section, tables, lists,
mermaid blocks, the `## Criteria` slices with their numbered criteria, and the
`**Status**:` line. Nothing here interprets the plan; whatever requires reading the
code (Where / Why / Proof, Flow paths, Impact cards) comes from the
`review-page.json` the agent writes.

Usage:
    python3 extract_plan.py --root <project> <feature> [--out plan.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KNOWN_IDS = {
    "problem": "problem",
    "flow": "flow",
    "impact": "impact",
    "relations": "relations",
    "surface": "surface",
    "landing": "landing",
    "criteria": "criteria",
    "out of scope": "out",
    "assumptions": "assumptions",
    "open questions": "questions",
    "observable": "observable",
    "sources": "sources",
}

SLICE_RE = re.compile(r"^###\s+(S\d+[a-z]?)\s*[:\-–—]?\s*(.*?)\s*(?:\((P\d)\))?\s*$")
OL_RE = re.compile(r"^(\d+)\.\s+(.*)$")
UL_RE = re.compile(r"^[-*]\s+(.*)$")
OPEN_Q_RE = re.compile(r"^\*\*Open questions:?\*\*:?\s*(.*)$", re.IGNORECASE)


def section_id(name: str) -> str:
    key = name.strip().lower()
    if key in KNOWN_IDS:
        return KNOWN_IDS[key]
    return re.sub(r"[^a-z0-9]+", "-", key).strip("-") or "section"


def split_row(line: str) -> list[str]:
    """Split a markdown table row without cutting a `|` inside backticks."""
    cells, buf, in_code, i = [], [], False, 0
    s = line.strip()
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code:
            cells.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    cells.append("".join(buf))
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [c.strip() for c in cells]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells)


def parse_blocks(lines: list[str]) -> list[dict]:
    """Blocks of a section: p, ul, ol, table, code (mermaid included)."""
    blocks: list[dict] = []
    para: list[str] = []
    i = 0

    def flush_para():
        nonlocal para
        if para:
            blocks.append({"type": "p", "text": " ".join(x.strip() for x in para)})
            para = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            flush_para()
            i += 1
            continue
        if stripped.startswith("```"):
            flush_para()
            lang = stripped[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            blocks.append({"type": "code", "lang": lang, "text": "\n".join(body)})
            i += 1
            continue
        if stripped.startswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            header = rows[0] if rows else []
            body_rows = [r for r in rows[1:] if not is_separator(r)]
            blocks.append({"type": "table", "header": header, "rows": body_rows})
            continue
        m_ol = OL_RE.match(stripped)
        m_ul = UL_RE.match(stripped)
        if (m_ol or m_ul) and not line.startswith(("  ", "\t")):
            flush_para()
            kind = "ol" if m_ol else "ul"
            items = []
            while i < len(lines):
                cur = lines[i]
                cs = cur.strip()
                mo, mu = OL_RE.match(cs), UL_RE.match(cs)
                if kind == "ol" and mo and not cur.startswith(("  ", "\t")):
                    items.append({"n": int(mo.group(1)), "text": mo.group(2)})
                elif kind == "ul" and mu and not cur.startswith(("  ", "\t")):
                    items.append({"text": mu.group(1)})
                elif cs and cur.startswith(("  ", "\t")) and items:
                    items[-1]["text"] += " " + cs
                else:
                    break
                i += 1
            blocks.append({"type": kind, "items": items})
            continue
        para.append(line)
        i += 1
    flush_para()
    return blocks


def parse_criteria(lines: list[str]) -> dict:
    intro: list[str] = []
    slices: list[dict] = []
    cur = None
    for line in lines:
        m = SLICE_RE.match(line.strip()) if line.startswith("### ") else None
        if m:
            cur = {"id": m.group(1), "title": m.group(2).strip(), "prio": m.group(3) or "", "lines": []}
            slices.append(cur)
            continue
        (cur["lines"] if cur else intro).append(line)

    out = []
    for s in slices:
        desc, acs, indep, extra = [], [], "", []
        stage = "desc"
        blocks = parse_blocks(s.pop("lines"))
        for b in blocks:
            if b["type"] == "p" and b["text"].strip().lower().startswith("**acceptance criteria**"):
                stage = "acs"
                continue
            if b["type"] == "p" and b["text"].startswith("**Independent test:**"):
                indep = b["text"][len("**Independent test:**"):].strip()
                stage = "after"
                continue
            if stage == "acs" and b["type"] == "ol":
                acs.extend(b["items"])
                continue
            (desc if stage == "desc" else extra).append(b)
        s.update({"desc": desc, "acs": acs, "indep": indep, "extra": extra})
        out.append(s)
    return {"intro": parse_blocks(intro), "slices": out}


def extract(plan_path: Path) -> dict:
    text = plan_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title, status = "", ""
    sections: list[dict] = []
    cur = None
    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("**Status**:") and not sections:
            status = line[len("**Status**:"):].strip()
            continue
        if line.startswith("## "):
            name = line[3:].strip()
            cur = {"name": name, "id": section_id(name), "lines": []}
            sections.append(cur)
            continue
        if cur is not None:
            cur["lines"].append(line)

    result = []
    for s in sections:
        raw = s.pop("lines")
        if s["id"] == "criteria":
            s["criteria"] = parse_criteria(raw)
            result.append(s)
            continue
        if s["id"] == "assumptions":
            # `**Open questions:**` lives inside Assumptions in the tlc-spec-lean
            # template; the page shows it as its own section in the index.
            cut = next((k for k, ln in enumerate(raw) if OPEN_Q_RE.match(ln.strip())), None)
            if cut is not None:
                s["blocks"] = parse_blocks(raw[:cut])
                result.append(s)
                rest = OPEN_Q_RE.match(raw[cut].strip()).group(1)
                q_lines = ([rest] if rest else []) + raw[cut + 1:]
                result.append({"name": "Open questions", "id": "questions", "blocks": parse_blocks(q_lines)})
                continue
        s["blocks"] = parse_blocks(raw)
        result.append(s)

    return {"path": str(plan_path), "title": title, "status": status, "sections": result}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="project root (where .specs/ lives)")
    ap.add_argument("--out", help="write the JSON to this file instead of printing it")
    ap.add_argument("feature")
    args = ap.parse_args()
    plan = Path(args.root) / ".specs" / "features" / args.feature / "plan.md"
    if not plan.exists():
        print(f"extract_plan: {plan} not found", file=sys.stderr)
        return 1
    data = extract(plan)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
