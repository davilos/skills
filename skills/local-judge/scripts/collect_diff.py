#!/usr/bin/env python3
# invariant: stdlib only, read-only on the repo (no fetch, no checkout, no index writes); everything it writes lives under the git-dir.
"""Resolve what local-judge reviews and write it under <git-dir>/local-judge/.

Usage: collect_diff.py [--repo PATH] [--base REF] [--fresh]

--fresh moves the ledger and round reports into archive-<timestamp>/ and starts again at round 1.

Writes <workdir>/branch.patch (merge-base vs working tree, untracked files as new),
<workdir>/since.patch on round 2+ (last reviewed snapshot vs working tree), and
<workdir>/meta.json. Prints meta.json to stdout. Exit 2 on unresolvable input.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

DEFAULT_BASES = ("origin/main", "main", "origin/master", "master")
MECHANICAL = [
    re.compile(r"(^|/)(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|poetry\.lock|uv\.lock|Pipfile\.lock|Cargo\.lock|go\.sum)$"),
    re.compile(r"\.snap$"),
    re.compile(r"(^|/)(dist|build|\.next|coverage|node_modules)/"),
    re.compile(r"(^|/)schema\.(yml|yaml|json)$"),
    re.compile(r"(^|/)migrations/\d{4}_.*\.py$"),
    re.compile(r"\.min\.(js|css)$"),
]


def git(repo, *args, check=True):
    # quotePath off keeps non-ASCII paths literal; errors=replace survives files that are not UTF-8
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotePath=false", *args],
                       capture_output=True, text=True, errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def ref_exists(repo, ref):
    return subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
                          capture_output=True).returncode == 0


def slug(branch):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("-") or "detached"


def file_hash(repo, path):
    try:
        with open(os.path.join(repo, path), "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()
    except OSError:
        return None


def untracked(repo):
    out = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    return [p for p in out.split("\0") if p]


def new_file_patch(repo, path):
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotePath=false", "diff", "--no-index", "--", "/dev/null", path],
                       capture_output=True, text=True, errors="replace")
    return r.stdout  # exit 1 means "differs", which is the normal case here


def diff_against(repo, rev, extra_untracked):
    patch = git(repo, "diff", "--no-color", "--no-ext-diff", rev)
    for p in extra_untracked:
        patch += new_file_patch(repo, p)
    return patch


def changed_files(repo, rev, extra_untracked):
    files = []
    for line in git(repo, "diff", "--numstat", "--no-renames", rev).splitlines():
        a, d, path = line.split("\t", 2)
        files.append({"path": path, "added": a, "deleted": d})
    for p in extra_untracked:
        try:
            with open(os.path.join(repo, p), "rb") as fh:
                n = fh.read().count(b"\n")
        except OSError:
            n = 0
        files.append({"path": p, "added": str(n), "deleted": "0", "untracked": True})
    for f in files:
        f["mechanical_hint"] = any(rx.search(f["path"]) for rx in MECHANICAL)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base")
    ap.add_argument("--fresh", action="store_true")
    a = ap.parse_args()

    try:
        repo = git(a.repo, "rev-parse", "--show-toplevel").strip()
    except RuntimeError as e:
        print(f"not a git repository: {e}", file=sys.stderr)
        return 2
    git_dir = git(repo, "rev-parse", "--absolute-git-dir").strip()
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    head = git(repo, "rev-parse", "HEAD").strip()

    base = a.base or next((b for b in DEFAULT_BASES if ref_exists(repo, b)), None)
    if not base or not ref_exists(repo, base):
        print(f"base ref not found ({a.base or ', '.join(DEFAULT_BASES)}); pass --base <ref>", file=sys.stderr)
        return 2
    merge_base = git(repo, "merge-base", base, "HEAD").strip()

    workdir = os.path.join(git_dir, "local-judge", slug(branch if branch != "HEAD" else "detached"))
    os.makedirs(workdir, exist_ok=True)
    ledger_path = os.path.join(workdir, "ledger.json")
    if a.fresh and os.path.exists(ledger_path):
        archive = os.path.join(workdir, "archive-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        os.makedirs(archive)
        for name in os.listdir(workdir):
            if name == "ledger.json" or re.match(r"round-\d+\.md$", name):
                os.replace(os.path.join(workdir, name), os.path.join(archive, name))

    extra = untracked(repo)
    with open(os.path.join(workdir, "branch.patch"), "w", encoding="utf-8") as fh:
        fh.write(diff_against(repo, merge_base, extra))

    prev = None
    if os.path.exists(ledger_path):
        with open(ledger_path, encoding="utf-8") as fh:
            prev = json.load(fh)
    rounds = (prev or {}).get("rounds", [])
    since = None
    if rounds:
        last = rounds[-1]
        snap = last.get("snapshot") or last["head"]
        if not ref_exists(repo, snap):
            snap = last["head"]
        since = {"snapshot": snap, "reviewed_head": last["head"], "round": last["round"]}
        # stash create skips untracked files, so the ledger keeps their hashes; unchanged ones stay out of since.patch
        seen = last.get("untracked", {})
        changed_untracked = [p for p in extra if seen.get(p) != file_hash(repo, p)]
        with open(os.path.join(workdir, "since.patch"), "w", encoding="utf-8") as fh:
            fh.write(diff_against(repo, snap, changed_untracked))

    findings = (prev or {}).get("findings", {})
    open_ids = sorted((k for k, v in findings.items() if v.get("status") in ("open", "fixed-locally")),
                      key=lambda k: int(k[1:]))
    next_id = 1 + max((int(k[1:]) for k in findings), default=0)

    meta = {
        "repo": repo,
        "branch": branch,
        "head": head,
        "dirty": bool(git(repo, "status", "--porcelain")),
        "base": base,
        "merge_base": merge_base,
        "commits": git(repo, "log", "--format=%h %s", f"{merge_base}..HEAD").splitlines(),
        "files": changed_files(repo, merge_base, extra),
        "workdir": workdir,
        "branch_patch": os.path.join(workdir, "branch.patch"),
        "since_patch": os.path.join(workdir, "since.patch") if since else None,
        "ledger": ledger_path,
        "round": (rounds[-1]["round"] + 1) if rounds else 1,
        "since": since,
        "previous_open": {k: findings[k] for k in open_ids},
        "next_finding_id": f"F{next_id}",
    }
    with open(os.path.join(workdir, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
