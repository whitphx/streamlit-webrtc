#!/usr/bin/env bash
# Usage: bash scripts/setup-issue-labels.sh
#
# Idempotently creates / updates the labels used by the Claude issue
# automation workflows (.github/workflows/claude-issue-*.yml).
#
# Requirements:
# - `gh` CLI authenticated against the `whitphx/streamlit-webrtc` repo

set -euo pipefail

create_or_update_label() {
  local name="$1"
  local color="$2"
  local description="$3"

  echo "Creating/updating label: ${name}"
  gh label create "${name}" \
    --color "${color}" \
    --description "${description}" \
    --force
}

# Labels managed by the automation. We use --force so re-running the script
# updates color/description if they drift.
create_or_update_label "needs-info"   "FBCA04" "Waiting for additional info from the reporter (auto-applied by Claude)"
create_or_update_label "triaged"      "0E8A16" "Triaged and awaiting maintainer action (auto-applied by Claude)"
create_or_update_label "out-of-scope" "CCCCCC" "Out of scope for this project"
create_or_update_label "ai-implement" "1D76DB" "Request Claude to implement this issue"

# `wontfix` is a conventional GitHub default label. Avoid clobbering its
# existing color/description if it's already there.
existing_labels="$(gh label list --limit 200 --json name --jq '.[].name')"
if echo "${existing_labels}" | grep -qx "wontfix"; then
  echo "Label 'wontfix' already exists; leaving it untouched."
else
  create_or_update_label "wontfix" "FFFFFF" "This will not be worked on"
fi

echo "Done."
