#!/usr/bin/env python3
# invariant: stdlib only; writes only under the git-dir workdir from meta.json; never touches refs, index or working tree.
"""Findings ledger for local-judge.

Usage:
  ledger.py record findings.json --meta meta.json   gate, then store the round and write round-N.md
  ledger.py mark --meta meta.json --status fixed-locally F1 F3
"""
import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMOJI = {"blocker": "\U0001F534", "should-fix": "\U0001F7E0", "nit": "\U0001F7E1", "pre-existing": "\U0001F7E3"}
MARKABLE = ("fixed-locally", "open")


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def snapshot(repo, head):
    # stash create builds a commit of the tracked working tree without touching refs or files
    r = subprocess.run(["git", "-C", repo, "stash", "create"], capture_output=True, text=True)
    return r.stdout.strip() or head


def untracked_hashes(repo):
    out = subprocess.run(["git", "-C", repo, "ls-files", "--others", "--exclude-standard", "-z"],
                         capture_output=True, text=True).stdout
    hashes = {}
    for p in filter(None, out.split("\0")):
        try:
            with open(os.path.join(repo, p), "rb") as fh:
                hashes[p] = hashlib.sha1(fh.read()).hexdigest()
        except OSError:
            pass
    return hashes


def render(meta, data, round_n):
    lines = [
        f"# local-judge round {round_n}: {data['verdict']}",
        "",
        f"- repo: `{meta['repo']}`",
        f"- branch: `{meta['branch']}` at `{meta['head'][:10]}`{' + uncommitted changes' if meta['dirty'] else ''}",
        f"- base: `{meta['base']}` (merge-base `{meta['merge_base'][:10]}`)",
        "",
        data["summary"].strip(),
        "",
    ]
    if data["findings"]:
        lines += ["## Details", ""]
        for f in data["findings"]:
            loc = f"{f['path']}:{f['line']}" if f.get("line") else f.get("path", "")
            lines += [f"### {f['id']} {EMOJI[f['severity']]} {f['title']}", "", f"`{loc}`", "", f["body"].strip(), ""]
            for e in f.get("evidence") or []:
                lines.append(f"- {e['type']}: {e['ref']}")
            lines.append("")
    return "\n".join(lines)


def record(a):
    meta = load(a.meta)
    gate = subprocess.run([sys.executable, os.path.join(HERE, "review_gate.py"), a.findings, "--meta", a.meta],
                          capture_output=True, text=True)
    if gate.returncode != 0:
        sys.stdout.write(gate.stdout)
        print("ledger: refused, the gate must pass before a round is recorded", file=sys.stderr)
        return 1
    data = load(a.findings)
    ledger = load(meta["ledger"], {"repo": meta["repo"], "branch": meta["branch"], "rounds": [], "findings": {}})
    if ledger["rounds"] and ledger["rounds"][-1]["round"] >= meta["round"]:
        print(f"ledger: round {meta['round']} already recorded; re-run collect_diff.py", file=sys.stderr)
        return 1
    round_n = meta["round"]
    for r in data.get("resolution") or []:
        entry = ledger["findings"][r["id"]]
        entry["status"] = r["status"]
        entry["history"] = entry.get("history", []) + [{"round": round_n, "status": r["status"], "note": r.get("note", "")}]
    for f in data["findings"]:
        ledger["findings"][f["id"]] = {
            "severity": f["severity"],
            "title": f["title"],
            "path": f.get("path"),
            "line": f.get("line"),
            "status": "noted" if f["severity"] == "pre-existing" else "open",
            "round": round_n,
        }
    report = os.path.join(meta["workdir"], f"round-{round_n}.md")
    with open(report, "w", encoding="utf-8") as fh:
        fh.write(render(meta, data, round_n))
    ledger["rounds"].append({
        "round": round_n,
        "at": datetime.datetime.now().isoformat(timespec="seconds"),
        "head": meta["head"],
        "snapshot": snapshot(meta["repo"], meta["head"]),
        "untracked": untracked_hashes(meta["repo"]),
        "base": meta["base"],
        "merge_base": meta["merge_base"],
        "verdict": data["verdict"],
        "report": report,
    })
    save(meta["ledger"], ledger)
    print(gate.stdout.strip())
    print(f"ledger: round {round_n} recorded")
    print(f"report: {report}")
    return 0


def mark(a):
    meta = load(a.meta)
    ledger = load(meta["ledger"])
    if not ledger:
        print("ledger: nothing recorded yet", file=sys.stderr)
        return 1
    bad = [i for i in a.ids if ledger["findings"].get(i, {}).get("status") not in ("open", "fixed-locally")]
    if bad:
        print(f"ledger: not open: {', '.join(bad)}", file=sys.stderr)
        return 1
    for i in a.ids:
        ledger["findings"][i]["status"] = a.status
    save(meta["ledger"], ledger)
    print(f"ledger: {', '.join(a.ids)} -> {a.status}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("findings")
    r.add_argument("--meta", required=True)
    m = sub.add_parser("mark")
    m.add_argument("--meta", required=True)
    m.add_argument("--status", choices=MARKABLE, required=True)
    m.add_argument("ids", nargs="+")
    a = ap.parse_args()
    return record(a) if a.cmd == "record" else mark(a)


if __name__ == "__main__":
    sys.exit(main())
