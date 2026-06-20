#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -x node_modules/.bin/vercel ]; then
  npm install
fi

VERCEL_BIN="./node_modules/.bin/vercel"

if [ -n "${VERCEL_TOKEN:-}" ]; then
  "$VERCEL_BIN" deploy --prod --yes \
    --scope "${VERCEL_SCOPE:-danielcruz-glitchs-projects}" \
    --token "$VERCEL_TOKEN"
  exit 0
fi

if ! "$VERCEL_BIN" whoami >/dev/null 2>&1; then
  echo "Log in to Vercel first:"
  echo "  npm run vercel:login"
  echo
  echo "Or set VERCEL_TOKEN for non-interactive deploy:"
  echo "  export VERCEL_TOKEN=your_token_here"
  echo "  ./scripts/deploy-vercel.sh"
  exit 1
fi

if [ ! -d .vercel ]; then
  "$VERCEL_BIN" link --yes --scope danielcruz-glitchs-projects
fi

"$VERCEL_BIN" deploy --prod --yes --scope danielcruz-glitchs-projects
