"""Acceptance criteria that changed since the reviewer last saw them (tlc-spec-lean and tlc-spec-driven).

The review state keeps `ac_baseline`: per group (a tlc-spec-lean slice, a tlc-spec-driven section),
the text of each criterion as the reviewer last saw it. A build pairs the current criteria with it
by content, not by position, so a criterion inserted at the top does not make every one below look
changed. Each current criterion comes out `same`, `changed` (with the text it had and a word diff)
or `new`; a baseline criterion with no current partner comes out `removed`.

The baseline only moves forward for what the reviewer acknowledged: a criterion confirmed or
rejected again on its current text, or its slice / section validated on its current text. The
rest keeps the old text, so the flag stays on the page across any number of republishes until the
reviewer looks at it. With no baseline yet (the first publish), nothing is flagged.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re

# Below this similarity, a replaced criterion is "removed" + "new" rather than "changed".
PAIR_RATIO = 0.4


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def align(old: list[str], new: list[str]) -> list[tuple[str, int | None, int | None]]:
    """Pair two lists of criteria in order: `[(op, i_old, i_new)]`, op in same / changed / new / removed."""
    a, b = [_norm(x) for x in old], [_norm(x) for x in new]
    out: list[tuple[str, int | None, int | None]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            out += [("same", i1 + k, j1 + k) for k in range(i2 - i1)]
            continue
        # A replaced run: pair each new criterion with the most similar old one left after the last
        # pairing (order kept); what has no partner close enough is new or removed.
        i = i1
        for j in range(j1, j2):
            best, best_r = None, PAIR_RATIO
            for k in range(i, i2):
                r = difflib.SequenceMatcher(None, a[k], b[j], autojunk=False).ratio()
                if r > best_r:
                    best, best_r = k, r
            if best is None:
                out.append(("new", None, j))
                continue
            out += [("removed", k, None) for k in range(i, best)]
            out.append(("changed", best, j))
            i = best + 1
        out += [("removed", k, None) for k in range(i, i2)]
    return out


def word_diff(old: str, new: str) -> list[list[str]]:
    """`[[op, text]]` with op `=` (kept), `-` (only in the old text) or `+` (only in the new one)."""
    a, b = re.findall(r"\S+|\s+", _norm(old)), re.findall(r"\S+|\s+", _norm(new))
    out: list[list[str]] = []

    def put(op: str, text: str) -> None:
        if not text:
            return
        if out and out[-1][0] == op:
            out[-1][1] += text
        else:
            out.append([op, text])

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            put("=", "".join(a[i1:i2]))
        else:
            put("-", "".join(a[i1:i2]))
            put("+", "".join(b[j1:j2]))
    return out


def gone_fp(texts: list[str]) -> str:
    """Fingerprint of a group's removed criteria: the page's "Seen" button stores it at `review/gone:<group>`."""
    return hashlib.sha256(json.dumps([_norm(t) for t in texts], ensure_ascii=False).encode()).hexdigest()[:16]


def changes(baseline: dict[str, list[str]] | None, current: dict[str, list[tuple[str, str]]],
            acked: set[str], acked_groups: set[str], gone_seen: dict[str, str] | None = None) -> tuple[dict, dict[str, list[str]]]:
    """Compare the current criteria with the baseline.

    `current` is `{group: [(key, text)]}` in document order; `acked` the criterion keys and
    `acked_groups` the groups the reviewer marked on their current text; `gone_seen` maps a group to
    the `gone_fp` of the removed criteria the reviewer pressed "Seen" on (the only way to clear the
    removals of a slice or section that no longer exists). Returns the page data
    `{"items": {key: {"st", "group", "was"?, "diff"?}}, "removed": {group: {"fp", "texts"}}}` (only
    what is not acknowledged yet) and the next baseline.
    """
    items: dict[str, dict] = {}
    removed: dict[str, dict] = {}
    gone_seen = gone_seen or {}
    nxt: dict[str, list[str]] = {}
    if baseline is None:
        return {"items": {}, "removed": {}}, {g: [t for _, t in xs] for g, xs in current.items()}
    for g in list(current) + [g for g in baseline if g not in current]:
        cur, old = current.get(g, []), baseline.get(g, [])
        g_ok = g in acked_groups
        keep: list[str] = []
        ops = align(old, [t for _, t in cur])
        gone = [old[i] for op, i, _ in ops if op == "removed"]
        gone_ok = g_ok or (bool(gone) and gone_seen.get(g) == gone_fp(gone))
        for op, i, j in ops:
            key, text = cur[j] if j is not None else (None, None)
            ok = g_ok or (key in acked)
            if op == "same":
                keep.append(text)
            elif op == "changed":
                if ok:
                    keep.append(text)
                else:
                    keep.append(old[i])
                    items[key] = {"st": "changed", "group": g, "was": _norm(old[i]), "diff": word_diff(old[i], text)}
            elif op == "new":
                if ok:
                    keep.append(text)
                else:
                    items[key] = {"st": "new", "group": g}
            elif not gone_ok:  # removed: shown until the group is validated again or marked "Seen"
                keep.append(old[i])
        if gone and not gone_ok:
            removed[g] = {"fp": gone_fp(gone), "texts": [_norm(t) for t in gone]}
        if keep:
            nxt[g] = keep
    return {"items": items, "removed": removed}, nxt
