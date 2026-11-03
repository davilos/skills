"""Document coverage: proves the page carries all the text of the document, in place and in order.

Splits the document into content pieces (each paragraph line, list item, table cell, heading,
front matter key and value, code line), each tagged with the section it belongs to, and checks at
both ends:

- `missing_in_data`: the piece is in the extracted data (catches extract_doc bugs);
- `rendered_pieces`: the form the piece takes in the page text after the template's md(), with
  its section and kind; check_page.cjs looks for each one inside the right section and in
  document order (catches template bugs).

`rendered_form` mirrors the template's md() exactly: if one changes, the other must too.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from doc_extract import COMMENT_RE, FENCE, HEADING, HR_RE, TASK_RE, code_mask, is_separator, list_item, outline, split_row

IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SEPARATOR = re.compile(r"\|?[\s:\-|]+\|?")

# Markdown the template's md() does not render: the page shows the raw text.
UNSUPPORTED = [
    (re.compile(r"<(?!br\s*/?>)(?!https?://)[a-zA-Z/][^>]*>"), "HTML"),
    (re.compile(r"\[\^[^\]]+\]"), "footnote [^n]"),
    (re.compile(r"(?<!\])\[[^\]]+\]\[[^\]]*\]"), "reference link [text][ref]"),
    (re.compile(r"^\s{0,3}\[[^\]^]+\]:\s+\S"), "link definition [ref]: url"),
    (re.compile(r"^\s{0,3}(?:=+|-+)\s*$"), None),  # setext underline, checked against the previous line below
]


def clean_text(doc_path: Path) -> str:
    text = doc_path.read_text(encoding="utf-8")
    return COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def doc_pieces(doc_path: Path) -> list[dict]:
    """All content of the document: {line, sec, kind, text}, 1-based lines.

    kind: `th` (a heading or table header: presence in its section is enough), `code` (a code line:
    shown as written, md() does not touch it) or `text`.
    """
    text = clean_text(doc_path)
    lines = text.splitlines()
    ol = outline(text)
    mask = code_mask(lines)
    starts = {s["line"]: s for s in ol["sections"]}
    out: list[dict] = []
    sec = "header"

    def add(i, t, kind="text", where=None):
        if t and t.strip():
            out.append({"line": i + 1, "sec": where or sec, "kind": kind, "text": t.strip()})

    # The page header shows the title first, then the front matter.
    if ol["title_line"] is not None:
        add(ol["title_line"], ol["title"], "text", "header")
    for k, v in ol["front"]:
        add(0, k, "th")
        add(0, v)
    first = ol["sections"][0] if ol["sections"] else None
    if first and first.get("intro") and first["line"] < ol["body_start"]:
        sec = "intro"
    prev_table = False
    prev_para = -2  # the last line that was plain paragraph text
    for i in range(ol["body_start"], len(lines)):
        ln = lines[i]
        if i == ol["title_line"]:
            if i in starts:
                sec = starts[i]["id"]
            continue
        if i in starts:
            sec = starts[i]["id"]
            add(i, starts[i]["name"], "th")
            prev_table = False
            continue
        if mask[i]:
            if not FENCE.match(ln):
                add(i, ln, "code")
            prev_table = False
            continue
        s = ln.strip()
        while s.startswith(">"):
            s = s[1:].strip()
        if not s or HR_RE.match(s):
            prev_table = False
            continue
        if s.startswith("|"):
            cells = split_row(s)
            if is_separator(cells):
                continue
            for c in cells:
                add(i, c, "text" if prev_table else "th")
            prev_table = True
            continue
        prev_table = False
        hm = HEADING.match(s)
        if hm:
            add(i, hm[2])
            continue
        li = list_item(s)
        if li:
            t = li[3]
            tm = TASK_RE.match(t) if li[1] == "ul" else None
            add(i, tm[2] if tm else t)
            continue
        # A paragraph that goes on from the line above is one piece with it: md() renders the joined
        # paragraph, so code or bold that opens on one line and closes on the next pairs across them.
        if prev_para == i - 1 and out and out[-1]["kind"] == "text":
            out[-1]["text"] += " " + s
        else:
            add(i, s)
        prev_para = i
    return out


def missing_in_data(doc_path: Path, data: dict) -> list[tuple[int, str]]:
    flat = norm(json.dumps(data, ensure_ascii=False).replace('\\"', '"').replace("\\\\", "\\"))
    return [(p["line"], p["text"]) for p in doc_pieces(doc_path) if norm(p["text"]) not in flat]


ESCAPABLE = r"\\`*_{}\[\]()#+\-.!|~<>"


def _inline(s: str) -> str:
    """Emphasis as md() strips it: bold, strikethrough, italics (never inside a word)."""
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"__([^_]+)__", r"\1", s)
    s = re.sub(r"~~([^~]+)~~", r"\1", s)
    s = re.sub(r"(^|[^\w*])\*(?=\S)([^*]*?\S)\*(?![\w*])", r"\1\2", s)
    s = re.sub(r"(^|[^\w_])_(?=\S)([^_]*?\S)_(?![\w_])", r"\1\2", s)
    return s


def rendered_form(piece: str) -> str:
    """The text a piece becomes on the page, as md() renders it (see the template)."""
    ph: list[str] = []

    def hold(text: str) -> str:
        ph.append(text)
        return f"\x00{len(ph) - 1}\x00"

    s = re.sub(r"`([^`]+)`", lambda m: hold(m[1]), piece)
    s = re.sub(rf"\\([{ESCAPABLE}])", lambda m: hold(m[1]), s)
    s = IMAGE.sub(lambda m: hold(m[1]), s)
    s = LINK.sub(lambda m: hold(_inline(m[1])), s)
    s = re.sub(r"<(https?://[^\s>]+)>", lambda m: hold(m[1]), s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = _inline(s)
    for _ in range(3):  # placeholders nested inside link text
        s = re.sub(r"\x00(\d+)\x00", lambda m: ph[int(m[1])], s)
    return norm(s)


def rendered_pieces(doc_path: Path) -> list[list]:
    """[line, section, kind, rendered text] in document order."""
    out = []
    for p in doc_pieces(doc_path):
        shown = norm(p["text"]) if p["kind"] == "code" else rendered_form(p["text"])
        if shown:
            out.append([p["line"], p["sec"], p["kind"], shown])
    return out


def unsupported_markdown(doc_path: Path) -> list[tuple[int, str]]:
    found = []
    lines = clean_text(doc_path).splitlines()
    mask = code_mask(lines)
    for i, line in enumerate(lines):
        if mask[i]:
            continue
        code_free = re.sub(r"`[^`]*`", "", line)
        for rx, name in UNSUPPORTED:
            if not rx.search(code_free):
                continue
            if name is None:
                prev = lines[i - 1].strip() if i else ""
                if prev and not prev.startswith(("|", "-", "*", "#", ">")) and not mask[i - 1] and not HR_RE.match(line):
                    found.append((i + 1, "setext heading (underlined with === or ---)"))
                continue
            found.append((i + 1, name))
    return found
