#!/usr/bin/env python3
# invariant: stdlib only, no network. A gate that can fail open via a missing import is not a gate.
import json
import os
import re
import sys
import unicodedata

SEVERITIES = ("blocker", "should-fix", "nit", "pre-existing")
EMOJI = {"blocker": "\U0001F534", "should-fix": "\U0001F7E0", "nit": "\U0001F7E1", "pre-existing": "\U0001F7E3"}
VERDICTS = ("READY", "NEEDS_WORK", "BLOCKED")
RESOLUTION_STATUSES = ("resolved", "open", "declined-accepted")
ID_RE = re.compile(r"^F[1-9]\d*$")
MAX_NITS = 5
CAPS = {"blocker": (900, 10), "should-fix": (900, 10), "nit": (400, 10), "pre-existing": (900, 10)}

BANNED_WORDS = [
    "obviously", "simply", "delve", "seamless", "streamline", "leverage", "crucial",
    "pivotal", "tapestry", "foster", "landscape", "furthermore", "moreover", "kudos",
    "awesome", "sorry", "apologies", "obviamente", "simplesmente", "ademais",
    "parabens", "desculpe", "desculpa",
]
BANNED_PHRASES = [
    "you forgot", "you missed", "great job", "nice work", "good catch",
    "hope this helps", "let me know", "feel free", "happy to", "it's worth noting",
    "its worth noting", "worth noting", "note that", "just a heads up",
    "as you can see", "thanks for", "thank you for", "i think maybe",
    "perhaps consider", "you might want to", "it would be beneficial", "testament to",
    "otimo trabalho", "bom trabalho", "espero que ajude", "fique a vontade",
    "sinta-se a vontade", "vale ressaltar", "vale a pena notar", "vale notar",
    "note que", "alem disso", "voce esqueceu", "com toda certeza",
]
NOT_BUT = [
    re.compile(r"\b(not|isn'?t|doesn'?t|don'?t|aren'?t|wasn'?t)\s+(just|only|merely)\b.{0,80}\bbut\b", re.S),
    re.compile(r"\bnao (apenas|so|somente)\b.{0,80}\bmas\b", re.S),
]
BANNED_OPENERS = [
    "let me", "i'll", "i will", "looking at", "first,", "so,", "sure", "ok,",
    "okay", "great", "vou ", "deixa eu", "primeiramente", "olhando", "bom,",
]
INTERNAL_REF = re.compile(r"^.+:\d+$")
COVERAGE_STATUSES = ("implemented", "partial", "missing", "contradicted", "not-applicable")
GAP_STATUSES = ("partial", "missing", "contradicted")
GAP_SEVERITIES = ("blocker", "should-fix")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def strip_code(s: str) -> str:
    s = re.sub(r"```.*?```", " ", s, flags=re.S)
    s = re.sub(r"`[^`\n]*`", " ", s)
    return s


def text_violations(raw: str, label: str) -> list:
    out = []
    stripped = strip_code(raw)
    if "\u2014" in stripped or "\u2013" in stripped:
        out.append(f"{label}: em/en dash found")
    if "!" in stripped:
        out.append(f"{label}: exclamation mark found")
    n = norm(stripped)
    for w in BANNED_WORDS:
        if re.search(r"\b" + re.escape(w) + r"\b", n):
            out.append(f"{label}: banned word '{w}'")
    for p in BANNED_PHRASES:
        if p in n:
            out.append(f"{label}: banned phrase '{p}'")
    for rx in NOT_BUT:
        if rx.search(n):
            out.append(f"{label}: 'not just X but Y' construction")
    return out


def opener_violation(body: str, label: str) -> list:
    first = body.strip()
    for e in EMOJI.values():
        first = first.replace(e, "", 1)
    first = norm(first.strip().split("\n", 1)[0])
    for op in BANNED_OPENERS:
        if first.startswith(op):
            return [f"{label}: first line opens with '{op.strip()}' (state the problem instead)"]
    return []


def line_count(repo: str, path: str):
    try:
        with open(os.path.join(repo, path), "rb") as fh:
            data = fh.read()
    except OSError:
        return None
    return data.count(b"\n") + (0 if not data or data.endswith(b"\n") else 1)


def check_location(repo: str, path: str, line, label: str, what: str) -> list:
    n = line_count(repo, path)
    if n is None:
        return [f"{label}: {what} '{path}' does not exist in the working tree"]
    if line is not None and line > n:
        return [f"{label}: {what} line {line} is past the end of '{path}' ({n} lines)"]
    return []


def check_finding(f: dict, meta: dict, seen: set) -> list:
    v = []
    sev = f.get("severity")
    fid = f.get("id", "")
    label = f"{fid or '?'} ({f.get('path', '?')}:{f.get('line', '-')})"
    if not ID_RE.match(fid):
        v.append(f"{label}: id must look like F7")
    elif fid in seen:
        v.append(f"{label}: duplicate id")
    elif int(fid[1:]) < int(meta["next_finding_id"][1:]):
        v.append(f"{label}: id already used in a previous round; new ids start at {meta['next_finding_id']}")
    seen.add(fid)
    if sev not in SEVERITIES:
        return v + [f"{label}: invalid severity '{sev}'"]
    title = f.get("title", "")
    if not title.strip() or len(title) > 100:
        v.append(f"{label}: 'title' required, one line up to 100 chars (it goes to the ledger table)")
    v += text_violations(title, f"{label} title")
    body = f.get("body", "")
    if not body.strip():
        return v + [f"{label}: empty body"]
    if not body.strip().startswith(EMOJI[sev]):
        v.append(f"{label}: body must start with {EMOJI[sev]} for severity '{sev}'")
    path, line = f.get("path"), f.get("line")
    if line is not None and (not isinstance(line, int) or line < 1):
        v.append(f"{label}: 'line' must be an integer >= 1")
        line = None
    if sev != "pre-existing":
        changed = {x["path"] for x in meta["files"]}
        if not path or line is None:
            v.append(f"{label}: '{sev}' requires 'path' and 'line'")
        elif path not in changed:
            v.append(f"{label}: '{path}' is not changed on this branch; anchor on the changed caller or make it pre-existing")
    if path:
        v += check_location(meta["repo"], path, line, label, "path")
    ev = f.get("evidence") or []
    if sev in ("blocker", "should-fix") and not ev:
        v.append(f"{label}: '{sev}' requires at least one evidence entry")
    for e in ev:
        t, ref = e.get("type"), e.get("ref", "")
        if t == "internal":
            if not INTERNAL_REF.match(ref):
                v.append(f"{label}: internal evidence '{ref}' must match path:line")
            else:
                p, ln = ref.rsplit(":", 1)
                v += check_location(meta["repo"], p, int(ln), label, "internal evidence")
        elif t == "external" and not ref.startswith("https://"):
            v.append(f"{label}: external evidence must be an https URL, got '{ref}'")
        elif t == "repro" and not ref.strip():
            v.append(f"{label}: repro evidence must carry the command that reproduces the claim")
        elif t not in ("internal", "external", "repro"):
            v.append(f"{label}: evidence type must be internal, external or repro, got '{t}'")
    max_chars, max_lines = CAPS[sev]
    if len(body) > max_chars:
        v.append(f"{label}: body {len(body)} chars exceeds {max_chars} cap")
    if body.count("\n") + 1 > max_lines:
        v.append(f"{label}: body exceeds {max_lines} lines")
    v += text_violations(body, label)
    v += opener_violation(body, label)
    return v


def check_summary(summary: str, round_n: int) -> list:
    v = []
    if "tl;dr" not in summary.lower():
        v.append("SUMMARY: missing TL;DR section")
    if not re.search(r"lint[ -]?rule", summary, re.I):
        v.append("SUMMARY: missing 'Promote to lint rule' section (write 'none' if empty)")
    if round_n >= 2 and not re.search(r"resolu", summary, re.I):
        v.append("SUMMARY: round >= 2 requires a Resolution section mapping every previous finding")
    v += text_violations(summary, "SUMMARY")
    return v


def check_resolution(data: dict, meta: dict, findings: list):
    """Round >= 2: only new blockers, and every previously open finding resolved, open or declined-accepted."""
    v, carry = [], {"blocker": 0, "should-fix": 0}
    if meta["round"] < 2:
        if data.get("resolution"):
            v.append("RESOLUTION: round 1 has no previous findings; remove 'resolution'")
        return v, carry
    for f in findings:
        if f.get("severity") != "blocker":
            v.append(f"ROUND: round {meta['round']} may only add NEW blockers; '{f.get('severity')}' {f.get('id', '?')} belongs in the Resolution table or nowhere")
    prev = meta.get("previous_open") or {}
    res = {r.get("id"): r for r in data.get("resolution") or []}
    for fid in prev:
        if fid not in res:
            v.append(f"RESOLUTION: previous finding {fid} has no resolution entry")
    for fid, r in res.items():
        if fid not in prev:
            v.append(f"RESOLUTION: {fid} was not open after the previous round")
            continue
        st = r.get("status")
        if st not in RESOLUTION_STATUSES:
            v.append(f"RESOLUTION: {fid} status '{st}' not in {RESOLUTION_STATUSES}")
        elif st == "open" and prev[fid].get("severity") in carry:
            carry[prev[fid]["severity"]] += 1
        if st == "declined-accepted" and not (r.get("note") or "").strip():
            v.append(f"RESOLUTION: {fid} declined-accepted needs the reason in 'note'")
    return v, carry


def check_spec(data: dict, meta: dict, summary: str):
    """With a spec: one spec_coverage row per requirement, evidence on every claim, gaps weigh on the verdict."""
    v, gaps = [], {"blocker": 0, "should-fix": 0}
    spec, rows = meta.get("spec"), data.get("spec_coverage")
    if not spec:
        if rows:
            v.append("SPEC: 'spec_coverage' present but collect_diff ran without --spec")
        return v, gaps
    try:
        with open(spec["requirements"], encoding="utf-8") as fh:
            reqs = json.load(fh).get("requirements") or []
    except (OSError, json.JSONDecodeError) as e:
        return [f"SPEC: cannot read {spec['requirements']}: {e}"], gaps
    if not reqs:
        return [f"SPEC: {spec['requirements']} lists no requirements; write them by hand from the spec"], gaps
    spec_lines = line_count("/", spec["path"])
    known = {}
    for r in reqs:
        rid, ln = r.get("id"), r.get("line")
        if not rid or rid in known:
            v.append(f"SPEC: requirement id '{rid}' missing or repeated in requirements.json")
        if not isinstance(ln, int) or spec_lines is None or not 1 <= ln <= spec_lines:
            v.append(f"SPEC: requirement {rid} line {ln!r} is not a line of {spec['path']}")
        known[rid] = r
    if not isinstance(rows, list):
        return v + ["SPEC: 'spec_coverage' must be a list with one row per requirement"], gaps
    seen = set()
    for row in rows:
        rid, st = row.get("id"), row.get("status")
        label = f"SPEC {rid}"
        if rid not in known:
            v.append(f"{label}: not a requirement id from requirements.json")
            continue
        if rid in seen:
            v.append(f"{label}: duplicate row")
        seen.add(rid)
        if st not in COVERAGE_STATUSES:
            v.append(f"{label}: status '{st}' not in {COVERAGE_STATUSES}")
            continue
        ev = row.get("evidence") or []
        if st in ("implemented", "partial", "contradicted") and not any(e.get("type") == "internal" for e in ev):
            v.append(f"{label}: '{st}' requires internal evidence path:line in the code")
        for e in ev:
            t, ref = e.get("type"), e.get("ref", "")
            if t == "internal":
                if not INTERNAL_REF.match(ref):
                    v.append(f"{label}: internal evidence '{ref}' must match path:line")
                else:
                    p, ln = ref.rsplit(":", 1)
                    v += check_location(meta["repo"], p, int(ln), label, "internal evidence")
            elif t not in ("external", "repro"):
                v.append(f"{label}: evidence type must be internal, external or repro, got '{t}'")
        note = row.get("note") or ""
        if st != "implemented" and not note.strip():
            v.append(f"{label}: '{st}' needs a 'note' saying what is missing, wrong or out of scope")
        v += text_violations(note, label)
        sev = row.get("severity")
        if st in GAP_STATUSES:
            if sev not in GAP_SEVERITIES:
                v.append(f"{label}: '{st}' needs 'severity' blocker or should-fix")
            else:
                gaps[sev] += 1
        elif sev:
            v.append(f"{label}: 'severity' only applies to {GAP_STATUSES}")
    for rid in known:
        if rid not in seen:
            v.append(f"SPEC {rid}: no spec_coverage row")
    if not re.search(r"spec coverage", summary, re.I):
        v.append("SUMMARY: a review with --spec requires a 'Spec coverage' section")
    return v, gaps


def expected_verdict(findings: list, carry: dict, gaps: dict) -> str:
    sevs = {f.get("severity") for f in findings}
    if "blocker" in sevs or carry["blocker"] or gaps["blocker"]:
        return "BLOCKED"
    if "should-fix" in sevs or carry["should-fix"] or gaps["should-fix"]:
        return "NEEDS_WORK"
    return "READY"


def main() -> int:
    args = sys.argv[1:]
    if len(args) != 3 or args[1] != "--meta":
        print("usage: review_gate.py findings.json --meta meta.json", file=sys.stderr)
        return 2
    try:
        data = json.loads(open(args[0], encoding="utf-8").read())
        meta = json.loads(open(args[2], encoding="utf-8").read())
    except (OSError, json.JSONDecodeError) as e:
        print(f"malformed input: {e}", file=sys.stderr)
        return 2

    violations = []
    if data.get("round") != meta["round"]:
        violations.append(f"ROUND: findings.json says round {data.get('round')!r}, meta.json says {meta['round']}")
    verdict = data.get("verdict")
    if verdict not in VERDICTS:
        violations.append(f"VERDICT: '{verdict}' not in {VERDICTS}")
    findings = data.get("findings")
    if not isinstance(findings, list):
        violations.append("SCHEMA: 'findings' must be a list")
        findings = []
    summary = data.get("summary", "")
    if not summary.strip():
        violations.append("SCHEMA: 'summary' is required")

    nits = sum(1 for f in findings if f.get("severity") == "nit")
    if nits > MAX_NITS:
        violations.append(f"NITS: {nits} nit findings exceed cap of {MAX_NITS}; fold overflow into the summary count")

    seen = set()
    for f in findings:
        violations += check_finding(f, meta, seen)
    violations += check_summary(summary, meta["round"])
    res_v, carry = check_resolution(data, meta, findings)
    violations += res_v
    spec_v, gaps = check_spec(data, meta, summary)
    violations += spec_v
    if verdict in VERDICTS:
        expected = expected_verdict(findings, carry, gaps)
        if verdict != expected:
            violations.append(f"VERDICT: '{verdict}' inconsistent with findings, still-open previous findings and spec gaps, expected '{expected}'")
        if verdict not in summary:
            violations.append(f"SUMMARY: TL;DR must contain the verdict token '{verdict}' verbatim")

    if violations:
        for x in violations:
            print(x)
        print(f"\ngate: FAIL ({len(violations)} violations)")
        return 1
    print(f"gate: PASS ({len(findings)} findings, verdict {verdict})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
