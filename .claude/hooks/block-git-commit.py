#!/usr/bin/env python3
"""PreToolUse hook: block the agent from creating commits on `main`.

Any git subcommand that writes commits to the current branch (commit, merge,
cherry-pick, revert, am, rebase) is blocked while that branch is main.
On any other branch these commands are allowed.

Exit 2 blocks the Bash call and feeds stderr back to Claude.
Commit to main manually with `! git commit` in the prompt when needed.
"""
import json
import re
import shlex
import subprocess
import sys

PROTECTED = "main"

# git, then any global options (-C dir, -c k=v, --flag), then a subcommand
# that writes commits to the current branch
COMMIT_RE = re.compile(
    r"(?:^|[\s;&|()`/])git"
    r"((?:\s+(?:-C\s+\S+|-c\s+\S+|--?\S+))*)"
    r"\s+(commit|merge|cherry-pick|revert|am|rebase)\b"
)


def split(text):
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def current_branch(global_opts, cwd):
    opts = split(global_opts)
    for i, opt in enumerate(opts[:-1]):
        if opt == "-C":
            cwd = opts[i + 1]
    # symbolic-ref also resolves an unborn branch (repo with no commits yet)
    try:
        return subprocess.run(
            ["git", "-C", cwd or ".", "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None  # not a repo, detached HEAD or git missing: not main


payload = json.load(sys.stdin)
command = payload.get("tool_input", {}).get("command", "")
cwd = payload.get("cwd")

for match in COMMIT_RE.finditer(command):
    if current_branch(match.group(1), cwd) == PROTECTED:
        print(
            f"Blocked: git {match.group(2)} on {PROTECTED} is disabled for "
            "the agent in this repo. Create a feature branch first "
            f"(git switch -c <branch>), or ask the user to commit on {PROTECTED}.",
            file=sys.stderr,
        )
        sys.exit(2)
