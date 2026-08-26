#!/bin/sh
# Start both Next.js development servers in one UI container.
# Website: 3000. Backoffice: 3001. --webpack comes from each package.json.
set -eu

# Named volumes for node_modules start empty on some Docker Desktop setups.
# Reinstall from the lockfile when the volume does not yet contain Next.js.
if [ ! -d /uis/website/node_modules/next ]; then
  npm ci --prefix /uis/website
fi
if [ ! -d /uis/backoffice/node_modules/next ]; then
  npm ci --prefix /uis/backoffice
fi

npm run dev --prefix /uis/website -- --hostname 0.0.0.0 --port 3000 &
npm run dev --prefix /uis/backoffice -- --hostname 0.0.0.0 --port 3001 &

wait
