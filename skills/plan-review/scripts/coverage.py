"""Plan coverage: proves the page carries all the text of plan.md, in place and in order.

Splits plan.md into content pieces (each paragraph, list item, table cell, slice
title), each tagged with the section it belongs to, and checks at both ends:

- `missing_in_data`: the piece is in the extracted data (catches extract_plan bugs);
- `rendered_pieces`: the form the piece takes in the page text after the template's
  md(), with its section and kind; check_page.cjs looks for each one inside the right
  section and in plan order (catches template bugs).

Labels the page renders differently are left out as labels, but their content is
kept: `**Status**:`, `**Acceptance Criteria**`, `**Independent test:**`,
`**Open questions:**` and the `#`/`##`/`###` of headings.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from extract_plan import OPEN_Q_RE, SLICE_RE, section_id, split_row

LABELS = ("**Status**:", "**Independent test:**", "**Open questions:**")
SEPARATOR = re.compile(r"\|?[\s:\-|]+\|?")

# Markdown the template's md() does not render: the page shows the raw text.
UNSUPPORTED = [
    (re.compile(r"\[[^\]]+\]\([^)]+\)"), "link [text](url)"),
    (re.compile(r"~~"), "strikethrough ~~"),
    (re.compile(r"<[a-zA-Z/][^>]*>"), "HTML"),
    (re.compile(r"^\s{2,}(?:[-*]|\d+\.)\s"), "nested list"),
    (re.compile(r"^#{4,}\s"), "#### heading"),
    (re.compile(r"^>\s"), "blockquote >"),
    (re.compile(r"(?<![*\w])[*_](?=\S)[^*_`]+(?<=\S)[*_](?![*\w])"), "italics"),
]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def plan_pieces(plan_path: Path) -> list[dict]:
    """All content of plan.md: {line, sec, kind, text} (kind: text | th)."""
    out: list[dict] = []
    in_code = False
    sec = "header"
    table_row = 0
    for i, line in enumerate(plan_path.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not s.startswith("|"):
            table_row = 0
        if s.startswith("```"):
            in_code = not in_code
            continue
        if not s or SEPARATOR.fullmatch(s) or s == "**Acceptance Criteria**":
            continue

        def add(text, kind="text"):
            if text:
                out.append({"line": i, "sec": sec, "kind": kind, "text": text})

        if in_code:
            add(s)
            continue
        if s.startswith("## "):
            sec = section_id(s[3:])
            add(s[3:].strip(), "th")
            continue
        if s.startswith("# "):
            add(s[2:].strip())
            continue
        if sec == "assumptions" and OPEN_Q_RE.match(s):
            sec = "questions"
        for label in LABELS:
            if s.startswith(label):
                s = s[len(label):].strip()
        m = SLICE_RE.match(s) if s.startswith("### ") else None
        if m:
            for x in m.groups():
                add(x)
        elif s.startswith("|"):
            table_row += 1
            for c in split_row(s):
                add(c, "th" if table_row == 1 else "text")
        else:
            add(re.sub(r"^(\d+\.|[-*])\s+", "", s))
    return out


def missing_in_data(plan_path: Path, data: dict) -> list[tuple[int, str]]:
    flat = norm(json.dumps(data, ensure_ascii=False).replace('\\"', '"').replace("\\\\", "\\"))
    return [(p["line"], p["text"]) for p in plan_pieces(plan_path) if norm(p["text"]) not in flat]


def rendered_form(piece: str) -> str:
    """The text a piece becomes on the page: md() only strips backticks and bold."""
    s = piece.replace("**", "").replace("`", "")
    s = re.sub(r"^\d+\.\s+", "", s)  # a door's "1. name" becomes "One-way door 1" + "name"
    return norm(s)


def rendered_pieces(plan_path: Path) -> list[list]:
    """[line, section, kind, rendered text] in plan order."""
    return [[p["line"], p["sec"], p["kind"], rendered_form(p["text"])]
            for p in plan_pieces(plan_path) if rendered_form(p["text"])]


def unsupported_markdown(plan_path: Path) -> list[tuple[int, str]]:
    found = []
    for i, line in enumerate(plan_path.read_text(encoding="utf-8").splitlines(), 1):
        code_free = re.sub(r"`[^`]*`", "", line)
        for rx, name in UNSUPPORTED:
            if rx.search(code_free):
                found.append((i, name))
    return found
