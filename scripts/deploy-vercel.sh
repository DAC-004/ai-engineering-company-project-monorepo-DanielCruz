#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -n "${VERCEL_TOKEN:-}" ]; then
  npx --yes vercel deploy --prod --yes \
    --scope "${VERCEL_SCOPE:-danielcruz-glitchs-projects}" \
    --token "$VERCEL_TOKEN"
  exit 0
fi

if ! npx --yes vercel whoami >/dev/null 2>&1; then
  echo "Log in to Vercel first:"
  echo "  npx vercel login"
  echo
  echo "Or set VERCEL_TOKEN for non-interactive deploy:"
  echo "  export VERCEL_TOKEN=your_token_here"
  echo "  ./scripts/deploy-vercel.sh"
  exit 1
fi

if [ ! -d .vercel ]; then
  npx --yes vercel link
fi

npx --yes vercel deploy --prod --yes
