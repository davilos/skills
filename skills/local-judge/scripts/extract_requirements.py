#!/usr/bin/env python3
# invariant: stdlib only, read-only on the spec; same requirement list on every run for the same file.
"""List the requirements a spec states, with the line each one sits on.

Usage: extract_requirements.py SPEC [--section REGEX] [--out FILE]

A requirement is:
  - a numbered, bulleted or checkbox item inside a criteria block (a heading or bold label
    named Acceptance Criteria, Criteria, Requirements, Critérios, Critérios de aceite, Requisitos);
  - anywhere else, a list item that states an obligation in capitals (SHALL, MUST, DEVE).
Indented bullets under an item are its examples and are not requirements of their own.
--section keeps only requirements whose heading chain ("# A > ## B > ### C") matches REGEX.

Ids are AC<n> when every item carries a list number and no number repeats, else R1..Rn in
order. Prints the JSON (also written to --out). Exit 2 when the spec cannot be read.
"""
import argparse
import json
import os
import re
import sys

BLOCK_LABEL = re.compile(
    r"^(#{1,6}\s+|\*\*|__)?\s*(acceptance criteria|criteria|requirements|crit[eé]rios( de aceite)?|requisitos)\s*(\*\*|__)?\s*:?\s*$",
    re.I,
)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
NUMBERED = re.compile(r"^ ?(\d+)[.)]\s+(.*)$")
CHECKBOX = re.compile(r"^ ?[-*+]\s+\[[ xX]\]\s+(.*)$")
BULLET = re.compile(r"^ ?[-*+]\s+(.*)$")
OBLIGATION = re.compile(r"\b(SHALL|MUST|DEVE|DEVEM)\b")
FENCE = re.compile(r"^\s*(```|~~~)")
MAX_TEXT = 300


def extract(lines, section=None):
    section_rx = re.compile(section) if section else None
    chain, items = [], []
    in_block, blanks, fenced = False, 0, False
    for i, raw in enumerate(lines, start=1):
        ln = raw.rstrip("\n")
        if FENCE.match(ln):
            fenced = not fenced
            continue
        if fenced:
            continue
        stripped = ln.strip()
        h = HEADING.match(ln)
        if h:
            level = len(h.group(1))
            chain = [c for c in chain if c[0] < level] + [(level, h.group(2))]
            in_block = bool(BLOCK_LABEL.match(stripped))
            blanks = 0
            continue
        if BLOCK_LABEL.match(stripped):
            in_block, blanks = True, 0
            continue
        if not stripped:
            blanks += 1
            if blanks >= 2:
                in_block = False
            continue
        blanks = 0
        if in_block and (stripped.startswith("**") or stripped.startswith("__")):
            in_block = False
        num, text = None, None
        m = NUMBERED.match(ln)
        if m:
            num, text = int(m.group(1)), m.group(2)
        else:
            m = CHECKBOX.match(ln) or BULLET.match(ln)
            if m:
                text = m.group(1)
        if text is None:
            continue
        if not (in_block or OBLIGATION.search(text)):
            continue
        heading = " > ".join("#" * lvl + " " + t for lvl, t in chain)
        if section_rx and not section_rx.search(heading):
            continue
        items.append({"number": num, "line": i, "text": text.strip()[:MAX_TEXT], "heading": heading})

    numbers = [it["number"] for it in items]
    use_numbers = bool(items) and None not in numbers and len(set(numbers)) == len(numbers)
    out = []
    for seq, it in enumerate(items, start=1):
        rid = f"AC{it['number']}" if use_numbers else f"R{seq}"
        out.append({"id": rid, "line": it["line"], "text": it["text"], "heading": it["heading"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--section")
    ap.add_argument("--out")
    a = ap.parse_args()
    try:
        with open(a.spec, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as e:
        print(f"spec not readable: {e}", file=sys.stderr)
        return 2
    try:
        reqs = extract(lines, a.section)
    except re.error as e:
        print(f"--section is not a valid regex: {e}", file=sys.stderr)
        return 2
    data = {"spec": os.path.abspath(a.spec), "section": a.section, "requirements": reqs}
    text = json.dumps(data, indent=2, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
