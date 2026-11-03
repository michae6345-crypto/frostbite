#!/bin/sh
# Mirror the latest GitHub Actions run of the current repo on slot 3.
# Usage: examples/gh-actions-slot.sh [slot] [name]
SLOT=${1:-3}
NAME=${2:-CI build}
while :; do
  RUN=$(gh run list --limit 1 --json databaseId,status --jq '.[0] | select(.status != "completed") | .databaseId')
  if [ -n "$RUN" ]; then
    frostbite-ctl set "$SLOT" run "$NAME" --detail "run $RUN"
    if gh run watch "$RUN" --exit-status >/dev/null 2>&1; then
      frostbite-ctl set "$SLOT" done "$NAME" --detail "run $RUN passed"
    else
      frostbite-ctl set "$SLOT" error "$NAME" --detail "run $RUN failed"
    fi
  fi
  sleep 30
done
