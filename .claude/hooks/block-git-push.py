#!/usr/bin/env python3
"""PreToolUse hook: block any `git push` issued by the agent.

Exit 2 blocks the Bash call and feeds stderr back to Claude.
Push manually with `! git push` in the prompt when needed.
"""
import json
import re
import sys

# git, then any global options (-C dir, -c k=v, --flag), then the push subcommand
PUSH_RE = re.compile(
    r"(?:^|[\s;&|()`/])git"
    r"(?:\s+(?:-C\s+\S+|-c\s+\S+|--?\S+))*"
    r"\s+push\b"
)

payload = json.load(sys.stdin)
command = payload.get("tool_input", {}).get("command", "")

if PUSH_RE.search(command):
    print(
        "Blocked: git push is disabled for the agent in this repo. "
        "Commit locally and ask the user to push.",
        file=sys.stderr,
    )
    sys.exit(2)
