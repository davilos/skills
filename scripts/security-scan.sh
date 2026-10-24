#!/usr/bin/env bash
# Runs the same Snyk checks as .github/workflows/snyk.yml, locally.
#   Agent Scan: prompt injection, malicious code and secrets in skills/
#   Snyk Code:  static analysis of the skill scripts
set -uo pipefail

AGENT_SCAN_VERSION="0.6.9"

cd "$(dirname "$0")/.." || exit 1

if [[ -z "${SNYK_TOKEN:-}" ]]; then
  echo "SNYK_TOKEN is not set. Get one at https://app.snyk.io/account (API Token)." >&2
  exit 2
fi

status=0

echo "==> Snyk Agent Scan (skills/)"
uvx "snyk-agent-scan@${AGENT_SCAN_VERSION}" --ci skills || status=1

echo "==> Snyk Code"
snyk code test || status=1

exit "$status"
