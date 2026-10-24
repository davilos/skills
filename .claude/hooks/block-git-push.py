#!/usr/bin/env python3
"""PreToolUse hook: block any `git push` by the agent that would update `main`.

Pushing other branches is allowed. A push is blocked when a refspec targets
main, when it uses --all/--mirror, or when it relies on the current branch
(bare push or HEAD) while that branch is main.

Exit 2 blocks the Bash call and feeds stderr back to Claude.
Push main manually with `! git push` in the prompt when needed.
"""
import json
import re
import shlex
import subprocess
import sys

PROTECTED = "main"

# git, then any global options (-C dir, -c k=v, --flag), then the push subcommand
# and its arguments up to the end of the shell command
PUSH_RE = re.compile(
    r"(?:^|[\s;&|()`/])git"
    r"((?:\s+(?:-C\s+\S+|-c\s+\S+|--?\S+))*)"
    r"\s+push\b([^;&|()`\n]*)"
)

# push options that take a separate value argument
VALUE_OPTS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


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
    try:
        return subprocess.run(
            ["git", "-C", cwd or ".", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None  # unknown branch: treat as protected below


def targets_main(global_opts, args, cwd):
    tokens = split(args)
    positional = []
    skip = False
    for tok in tokens:
        if skip:
            skip = False
        elif tok in ("--all", "--mirror"):
            return True
        elif tok in VALUE_OPTS:
            skip = True
        elif not tok.startswith("-"):
            positional.append(tok)

    refspecs = positional[1:]  # first positional is the remote
    branch = None
    if not refspecs:
        branch = current_branch(global_opts, cwd)
        return branch in (None, PROTECTED)

    for ref in refspecs:
        dst = ref.lstrip("+").split(":")[-1]
        if dst == "HEAD":
            branch = branch or current_branch(global_opts, cwd)
            dst = branch or PROTECTED
        if dst.removeprefix("refs/heads/") == PROTECTED:
            return True
    return False


payload = json.load(sys.stdin)
command = payload.get("tool_input", {}).get("command", "")
cwd = payload.get("cwd")

for match in PUSH_RE.finditer(command):
    if targets_main(match.group(1), match.group(2), cwd):
        print(
            f"Blocked: git push to {PROTECTED} is disabled for the agent in "
            "this repo. Push a feature branch instead, or ask the user to "
            f"push {PROTECTED}.",
            file=sys.stderr,
        )
        sys.exit(2)
