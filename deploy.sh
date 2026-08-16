#!/usr/bin/env bash
# Deploy Sampan to Cloud Run.
#
# The flags here are part of the contract, not incidental (see PRD.md 9.3):
#   --timeout=3600      the 300s default kills calls mid-story
#   --max-instances=3   caps runaway spend on hackathon credits
#   --min-instances     0 while building; set to 1 only for recording, then back
set -euo pipefail

# ^@^ sets @ as the env-var delimiter, so a key containing a comma cannot
# silently split into a bogus extra variable.
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-southeast1}"
SERVICE="${SAMPAN_SERVICE:-sampan}"
MIN_INSTANCES="${SAMPAN_MIN_INSTANCES:-0}"
API_KEY="${SAMPAN_API_KEY:?set SAMPAN_API_KEY}"

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
  --set-env-vars="^@^GOOGLE_CLOUD_PROJECT=${PROJECT_ID}@GOOGLE_CLOUD_LOCATION=${REGION}@SAMPAN_API_KEY=${API_KEY}"

URL="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"

echo
echo "Deployed: $URL"
echo
echo "Ticket 1 acceptance — health:"
echo "  curl -s ${URL}/healthz"
echo
echo "Ticket 1 acceptance — Firestore round trip:"
echo "  curl -s -X POST ${URL}/debug/smoke \\"
echo "    -H 'X-Sampan-Key: \$SAMPAN_API_KEY' -H 'Content-Type: application/json' \\"
echo "    -d '{\"note\":\"板底街的咖啡店\"}'"
echo
echo "Ticket 1 acceptance — auth rejects:"
echo "  curl -s -o /dev/null -w '%{http_code}\\n' -X POST ${URL}/debug/smoke \\"
echo "    -H 'Content-Type: application/json' -d '{\"note\":\"nope\"}'   # expect 401"
