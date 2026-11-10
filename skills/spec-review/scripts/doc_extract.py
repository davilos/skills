#!/usr/bin/env python3
"""Read a local Markdown document and print it as JSON, section by section.

This is the mechanical part of the page: the title, the front matter, and for each section its
blocks (paragraphs, subheadings, lists with their nesting, tables, code and mermaid blocks,
quotes). Nothing here interprets the document.

Sections are the headings one level below the title: with a single `#` title they are the `##`
headings; without one (or with several `#`) they are the shallowest headings in the file. Deeper
headings stay inside their section as subheadings. Text between the title and the first section
becomes the `intro` section. A section with no content, or whose only content is `None - <why>`
(`N/A`, `-`, `Nenhum`, `Não se aplica`...), comes out with `empty: true`: nothing to validate.

Usage:
    python3 extract_doc.py <doc.md> [--out doc.json] [--lang en|pt]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```+|~~~+)(.*)$")
OL_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
UL_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
TASK_RE = re.compile(r"^\[([ xX])\]\s+(.*)$")
HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
EMPTY_RE = re.compile(r"^(?:none|nothing|n/?a|nenhuma?|nada|não se aplica|nao se aplica)\b|^[-–—]?$", re.IGNORECASE)

PT_WORDS = re.compile(r"\b(que|não|nao|para|com|uma|são|como|está|também|quando|depois|pelo|pela)\b|ção\b|ções\b", re.I)
EN_WORDS = re.compile(r"\b(the|and|with|that|this|which|when|should|will|from|into|after)\b", re.I)


def detect_lang(text: str) -> str:
    return "pt" if len(PT_WORDS.findall(text)) > len(EN_WORDS.findall(text)) else "en"


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[`*_~\[\]()]", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "section"


def gh_slug(name: str) -> str:
    """GitHub's heading anchor: lowercase, accents kept, punctuation out, spaces to hyphens."""
    s = re.sub(r"[`*_~\[\]()]", "", name).strip().lower()
    s = re.sub(r"[^\w\- ]", "", s, flags=re.UNICODE)
    return s.replace(" ", "-")


def strip_front_matter(lines: list[str]) -> tuple[list[list[str]], int]:
    """YAML front matter (`---` ... `---` at the top): its `key: value` pairs and how many lines it takes."""
    if not lines or lines[0].strip() != "---":
        return [], 0
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            pairs = []
            for ln in lines[1:i]:
                if not ln.strip() or ln.lstrip().startswith("#"):
                    continue
                m = re.match(r"^([^:]+):\s*(.*)$", ln.strip())
                if m and not ln.startswith((" ", "\t")):
                    pairs.append([m[1].strip(), m[2].strip().strip("'\"")])
                elif pairs:
                    pairs[-1][1] = (pairs[-1][1] + " " + ln.strip().lstrip("- ").strip()).strip()
            return pairs, i + 1
    return [], 0


def code_mask(lines: list[str]) -> list[bool]:
    """True for every line inside (or opening/closing) a fenced code block."""
    mask, fence = [], None
    for ln in lines:
        m = FENCE.match(ln)
        if fence is None and m:
            fence = m[1][0] * 3
            mask.append(True)
        elif fence is not None:
            mask.append(True)
            if ln.strip().startswith(fence) and not ln.strip()[len(fence):].strip("`~"):
                fence = None
        else:
            mask.append(False)
    return mask


def outline(text: str) -> dict:
    """Where the title and each section start. Shared with coverage.py so both cut the file the same way.

    Returns {front, body_start, title, title_line, level, sections: [{line, id, name}]} with 0-based lines.
    """
    lines = text.splitlines()
    front, start = strip_front_matter(lines)
    mask = code_mask(lines)
    heads = []
    for i in range(start, len(lines)):
        if mask[i]:
            continue
        m = HEADING.match(lines[i])
        if m:
            heads.append((i, len(m[1]), m[2].strip()))
    h1 = [h for h in heads if h[1] == 1]
    fm_title = next((v for k, v in front if k.lower() == "title"), "")
    title, title_line = "", None
    rest = heads
    if len(h1) == 1 and heads and heads[0][1] == 1:
        title, title_line = heads[0][2], heads[0][0]
        rest = heads[1:]
    elif fm_title:
        title = fm_title
    level = min((h[1] for h in rest), default=2)
    sections, used = [], set()
    # Text before the first section (after the title, or from the top when there is none) is the intro.
    first = next((h[0] for h in rest if h[1] == level), len(lines))
    body_from = (title_line + 1) if title_line is not None else start
    if any(ln.strip() for ln in lines[body_from:first]):
        sections.append({"line": body_from - 1, "id": "intro", "name": "", "intro": True})
        used.add("intro")
    for i, lvl, name in rest:
        if lvl != level:
            continue
        sid, k = slugify(name), 2
        base = sid
        while sid in used:
            sid, k = f"{base}-{k}", k + 1
        used.add(sid)
        sections.append({"line": i, "id": sid, "name": name})
    return {"front": front, "body_start": start, "title": title, "title_line": title_line, "level": level, "sections": sections}


def split_row(line: str) -> list[str]:
    """Split a markdown table row without cutting a `|` inside backticks or an escaped `\\|`."""
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
    if cells and cells[-1].strip() == "" and s.endswith("|"):
        cells = cells[:-1]
    return [c.strip() for c in cells]


def is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{1,}:?", c.replace(" ", "")) for c in cells)


def indent_of(line: str) -> int:
    return len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip())


def list_item(line: str):
    """(indent, kind, n, text) when the line opens a list item, else None."""
    mo, mu = OL_RE.match(line), UL_RE.match(line)
    if mo:
        return indent_of(line), "ol", int(mo[2]), mo[3]
    if mu and not HR_RE.match(line):
        return indent_of(line), "ul", None, mu[2]
    return None


def make_item(kind: str, n, text: str) -> dict:
    it = {"text": text}
    if kind == "ol":
        it["n"] = n
    else:
        t = TASK_RE.match(text)
        if t:
            it["task"] = t[1].lower() == "x"
            it["text"] = t[2]
    return it


def parse_list(lines: list[str], i: int) -> tuple[dict, int]:
    """A list starting at line i, with nested lists and wrapped lines; returns (block, next line)."""
    base, kind, _, _ = list_item(lines[i])
    items: list[dict] = []
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            # A blank line ends the list unless the list goes on after it (same level or deeper).
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            nxt = list_item(lines[j]) if j < len(lines) else None
            if j < len(lines) and ((nxt and nxt[0] >= base and (nxt[0] > base or nxt[1] == kind)) or (indent_of(lines[j]) > base and items)):
                i = j
                continue
            break
        li = list_item(ln)
        if li and li[0] == base:
            if li[1] != kind:
                break
            items.append(make_item(kind, li[2], li[3]))
            i += 1
            continue
        if li and li[0] > base and items:
            sub, i = parse_list(lines, i)
            items[-1].setdefault("sub", []).append(sub)
            continue
        fm = FENCE.match(ln) if items and indent_of(ln) > base else None
        if fm:
            # A fenced code block inside an item is the item's own block: folded into its text, the fences
            # would pair the item's backticks differently from the document.
            fence, ind, body = fm[1][0] * 3, indent_of(ln), []
            i += 1
            while i < len(lines) and not (lines[i].strip().startswith(fence) and not lines[i].strip()[len(fence):].strip("`~")):
                body.append(lines[i][ind:] if not lines[i][:ind].strip() else lines[i].strip())
                i += 1
            i += 1  # the closing fence
            items[-1].setdefault("sub", []).append({"type": "code", "lang": fm[2].strip(), "text": "\n".join(body)})
            continue
        if indent_of(ln) > base and items:
            # A wrapped line continues the last item (or the last item of its sublist). After a code block
            # inside the item, it is a paragraph of the item, under the code.
            target = items[-1]
            while target.get("sub") and target["sub"][-1]["type"] in ("ul", "ol"):
                target = target["sub"][-1]["items"][-1]
            last = (target.get("sub") or [None])[-1]
            if last and last["type"] == "code":
                target["sub"].append({"type": "p", "text": ln.strip()})
            elif last and last["type"] == "p":
                last["text"] += " " + ln.strip()
            else:
                target["text"] += " " + ln.strip()
            i += 1
            continue
        if li and li[0] < base:
            break
        if items and not li and not ln.startswith(("|", ">", "#")) and not FENCE.match(ln):
            # Lazy continuation: an unindented line right after an item still belongs to it.
            items[-1]["text"] += " " + ln.strip()
            i += 1
            continue
        break
    return {"type": kind, "items": items}, i


def parse_blocks(lines: list[str]) -> list[dict]:
    """Blocks: p, h, ul, ol, table, code (mermaid included), quote, hr."""
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
        fm = FENCE.match(line)
        if fm:
            flush_para()
            fence = fm[1][0] * 3
            lang = fm[2].strip().split()[0] if fm[2].strip() else ""
            body = []
            i += 1
            while i < len(lines) and not (lines[i].strip().startswith(fence) and not lines[i].strip()[len(fence):].strip("`~")):
                body.append(lines[i])
                i += 1
            blocks.append({"type": "code", "lang": lang, "text": "\n".join(body)})
            i += 1
            continue
        hm = HEADING.match(line)
        if hm:
            flush_para()
            blocks.append({"type": "h", "level": len(hm[1]), "text": hm[2].strip()})
            i += 1
            continue
        if HR_RE.match(line) and not para:
            flush_para()
            blocks.append({"type": "hr"})
            i += 1
            continue
        if stripped.startswith(">"):
            flush_para()
            inner = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                inner.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            blocks.append({"type": "quote", "blocks": parse_blocks(inner)})
            continue
        if stripped.startswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            header = rows[0] if rows else []
            body_rows = [r for r in rows[1:] if not is_separator(r)]
            width = len(header)
            body_rows = [(r + [""] * width)[:max(width, len(r))] for r in body_rows]
            blocks.append({"type": "table", "header": header, "rows": body_rows})
            continue
        if list_item(line) and not para:
            flush_para()
            block, i = parse_list(lines, i)
            blocks.append(block)
            continue
        para.append(line)
        i += 1
    flush_para()
    return blocks


def is_empty(blocks: list[dict]) -> bool:
    if not blocks:
        return True
    if len(blocks) > 1 or blocks[0]["type"] != "p":
        return False
    return bool(EMPTY_RE.match(re.sub(r"[`*_]", "", blocks[0]["text"]).strip()))


def extract(doc_path: Path, lang: str | None = None) -> dict:
    text = doc_path.read_text(encoding="utf-8")
    # HTML comments are notes to the editor, not content: out of the page and out of coverage.
    clean = COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    lines = clean.splitlines()
    ol = outline(clean)
    starts = ol["sections"]
    out = []
    for k, s in enumerate(starts):
        end = starts[k + 1]["line"] if k + 1 < len(starts) else len(lines)
        body = lines[s["line"] + 1:end]
        blocks = parse_blocks(body)
        sec = {"id": s["id"], "name": s["name"], "blocks": blocks, "empty": is_empty(blocks)}
        if s.get("intro"):
            sec["intro"] = True
        out.append(sec)
    lang = lang or detect_lang(clean)
    title = ol["title"] or doc_path.stem
    for s in out:
        if s.get("intro"):
            s["name"] = "Introdução" if lang == "pt" else "Introduction"
    return {"path": str(doc_path), "title": title, "lang": lang, "front": ol["front"], "level": ol["level"], "sections": out}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("doc", help="the Markdown document")
    ap.add_argument("--out", help="write the JSON to this file instead of printing it")
    ap.add_argument("--lang", choices=["en", "pt"], help="page language (default: detected from the document)")
    args = ap.parse_args()
    doc = Path(args.doc)
    if not doc.is_file():
        print(f"extract_doc: {doc} not found", file=sys.stderr)
        return 1
    payload = json.dumps(extract(doc, args.lang), ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
