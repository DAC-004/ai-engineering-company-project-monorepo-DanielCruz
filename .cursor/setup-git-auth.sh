#!/usr/bin/env bash
set -euo pipefail

if [ -z "${GITHUB_PAT:-}" ] && [ -n "${DAC004_GITHUB_PAT:-}" ]; then
  export GITHUB_PAT="$DAC004_GITHUB_PAT"
fi

if [ -z "${GITHUB_PAT:-}" ]; then
  echo "GITHUB_PAT is not set and DAC004_GITHUB_PAT is unavailable." >&2
  exit 1
fi

export GIT_TERMINAL_PROMPT=0

git config --global --replace-all credential.helper ""
git config --global --add credential.helper '!f() { echo "username=x-access-token"; echo "password=${GITHUB_PAT}"; }; f'

if [ -n "${GH_TOKEN:-}" ]; then
  unset GH_TOKEN
fi

echo "$GITHUB_PAT" | gh auth login --hostname github.com --with-token
gh auth setup-git

git config --global url."https://x-access-token:${GITHUB_PAT}@github.com/DAC-004/".insteadOf "https://github.com/DAC-004/"

echo "Git auth configured for $(gh api user --jq .login)"
