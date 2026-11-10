#!/usr/bin/env bash
# Rebuild the live Watchd (docker-compose.watchd.yaml) from the code here.
#
#   scripts/deploy.sh            check the site builds, then rebuild the app
#   scripts/deploy.sh --no-site  skip the local site build check
#
# The app mounts the downloads folder on the USB drive (D:). When that drive
# drops out and comes back, Docker Desktop loses the mount until it restarts,
# and a rebuild then fails, leaving Watchd down. So before rebuilding, this
# checks Docker can still mount D:, and restarts Docker Desktop first if not.
set -euo pipefail

cd "$(dirname "$0")/.."
COMPOSE=(docker compose -f docker-compose.watchd.yaml)
DOWNLOADS="D:/Downloads"
# Any image that's already here will do for the mount check.
PROBE_IMAGE="postgres:16-alpine"

say() { printf '\n== %s\n' "$*"; }

wait_for_docker() {
  for _ in $(seq 1 60); do
    docker info >/dev/null 2>&1 && return 0
    sleep 5
  done
  echo "Docker didn't come back within 5 minutes." >&2
  return 1
}

wait_healthy() {
  local state=""
  for _ in $(seq 1 40); do
    state=$(docker inspect -f '{{.State.Health.Status}}' scrob-app-1 2>/dev/null || true)
    [ "$state" = healthy ] && { echo "Watchd is healthy."; return 0; }
    sleep 5
  done
  echo "Watchd isn't healthy after 200 seconds (state: ${state:-not running})." >&2
  echo "Look at: docker logs scrob-app-1" >&2
  return 1
}

can_mount_downloads() {
  MSYS_NO_PATHCONV=1 docker run --rm --entrypoint true \
    -v "$DOWNLOADS:/probe:ro" "$PROBE_IMAGE" >/dev/null 2>&1
}

if [ "${1:-}" != "--no-site" ]; then
  say "Building the site to check it compiles"
  (cd frontend && npx astro build >/dev/null && rm -rf dist)
fi

say "Checking Docker can still reach $DOWNLOADS"
if can_mount_downloads; then
  echo "It can."
else
  if [ ! -d "/d/Downloads" ]; then
    echo "$DOWNLOADS isn't there in Windows either: is the USB drive plugged in and on?" >&2
    exit 1
  fi
  echo "Docker has lost the drive (it dropped out and came back). Restarting Docker Desktop."
  docker desktop restart
  wait_for_docker
  "${COMPOSE[@]}" up -d
  if ! can_mount_downloads; then
    echo "Docker still can't mount $DOWNLOADS after a restart; not rebuilding." >&2
    exit 1
  fi
  echo "Reconnected."
fi

say "Rebuilding the app"
"${COMPOSE[@]}" up -d --build app
wait_healthy
