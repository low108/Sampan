#!/usr/bin/env bash
# Deploy Sampan to Cloud Run.
#
# The flags here are part of the contract, not incidental (see PRD.md 9.3):
#   --timeout=3600      the 300s default kills calls mid-story
#   --max-instances=3   caps runaway spend on hackathon credits
#   --min-instances     0 while building; set to 1 only for recording, then back
set -euo pipefail

# Local config lives in .env, which is gitignored.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# ^@^ sets @ as the env-var delimiter, so a key containing a comma cannot
# silently split into a bogus extra variable.
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-southeast1}"
SERVICE="${SAMPAN_SERVICE:-sampan}"
MIN_INSTANCES="${SAMPAN_MIN_INSTANCES:-0}"
API_KEY="${SAMPAN_API_KEY:?set SAMPAN_API_KEY}"

# Transcript screening. Forwarded rather than hardcoded, and empty by default:
# `build_screen` returns None without templates, so a deploy that omits these
# silently stores unscreened transcripts. That was true of every revision up to
# 00014 -- the templates existed in the project and nothing referenced them.
#
# Provision with scripts/setup_armor.sh. `dlp` calls Sensitive Data Protection
# directly; `armor` goes through Model Armor to the same templates and adds the
# prompt-injection filters. Default dlp: one hop fewer, one silent failure mode
# fewer (R18).
SCREEN_BACKEND="${SAMPAN_SCREEN_BACKEND:-dlp}"
DLP_INSPECT="${SAMPAN_DLP_INSPECT_TEMPLATE:-}"
DLP_DEIDENTIFY="${SAMPAN_DLP_DEIDENTIFY_TEMPLATE:-}"
ARMOR_TEMPLATE="${SAMPAN_ARMOR_TEMPLATE:-}"

# Generated card imagery. Empty by default and the app is complete without it:
# `publish` is a no-op with no topic, and /internal/memories declines with no
# bucket. Provision with scripts/setup_memories.sh.
MEMORIES_TOPIC="${SAMPAN_MEMORIES_TOPIC:-}"
MEMORIES_BUCKET="${SAMPAN_MEMORIES_BUCKET:-}"

if [[ -z "$DLP_INSPECT$ARMOR_TEMPLATE" ]]; then
  echo "WARNING: no screening templates configured — transcripts will be stored" >&2
  echo "         unscreened. Run scripts/setup_armor.sh, or accept this."       >&2
fi

gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --source=. \
  --allow-unauthenticated \
  --timeout=3600 \
  --min-instances="$MIN_INSTANCES" \
  --max-instances=3 \
  --cpu=1 \
  --memory=1Gi \
  --concurrency=20 \
  --set-env-vars="^@^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}@GOOGLE_CLOUD_LOCATION=${REGION}@SAMPAN_API_KEY=${API_KEY}@SAMPAN_SCREEN_BACKEND=${SCREEN_BACKEND}@SAMPAN_DLP_INSPECT_TEMPLATE=${DLP_INSPECT}@SAMPAN_DLP_DEIDENTIFY_TEMPLATE=${DLP_DEIDENTIFY}@SAMPAN_ARMOR_TEMPLATE=${ARMOR_TEMPLATE}@SAMPAN_MEMORIES_TOPIC=${MEMORIES_TOPIC}@SAMPAN_MEMORIES_BUCKET=${MEMORIES_BUCKET}"

URL="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"

echo
echo "Deployed: $URL"
echo
echo "Ticket 1 acceptance — health:"
echo "  curl -s ${URL}/health"
echo
echo "Ticket 1 acceptance — Firestore round trip:"
echo "  curl -s -X POST ${URL}/debug/smoke \\"
echo "    -H 'X-Sampan-Key: \$SAMPAN_API_KEY' -H 'Content-Type: application/json' \\"
echo "    -d '{\"note\":\"the coffee shop on Jalan Bandar\"}'"
echo
echo "Ticket 1 acceptance — auth rejects:"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' -X POST ${URL}/debug/smoke \\"
echo "    -H 'Content-Type: application/json' -d '{\"note\":\"nope\"}'   # expect 401"
