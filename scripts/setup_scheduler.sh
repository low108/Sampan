#!/usr/bin/env bash
# Schedule the community refresh.
#
# Chapters are the one part of the graph not maintained by the call that
# changed it. Every other derived record -- stories, facts, retirements,
# entities -- is written by `finish_call` while the transcript is still in
# hand. Communities need full label propagation over the whole graph plus a
# model call per chapter, which is seconds of work and wrong to do while an
# eighty-year-old is holding a phone. So it runs on a clock instead.
#
# Zep is explicit that this is required rather than optional: communities are
# extended cheaply as conversations land, and "periodic community refreshes
# remain necessary" because that cheap extension drifts.
#
# Weekly, not nightly. One narrator produces a handful of new entities a week;
# re-clustering every night would spend a model call per chapter to rediscover
# the same chapters. If the archive grows, raise the frequency -- the job is
# idempotent, so running it more often is safe and only costs money.
#
# Idempotent: re-run after a redeploy changes the service URL.
set -euo pipefail

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
REGION="${GOOGLE_CLOUD_LOCATION:-asia-southeast1}"
SERVICE="${SAMPAN_SERVICE:-sampan}"
API_KEY="${SAMPAN_API_KEY:?set SAMPAN_API_KEY}"
JOB="${SAMPAN_COMMUNITY_JOB:-sampan-communities}"
NARRATORS="${SAMPAN_COMMUNITY_NARRATORS:-ah_khim,wei_lun}"
# 04:00 Monday, Malaysian time: after the week's calls, before anyone looks.
SCHEDULE="${SAMPAN_COMMUNITY_SCHEDULE:-0 4 * * 1}"
TIMEZONE="${SAMPAN_TIMEZONE:-Asia/Kuala_Lumpur}"

gcloud services enable cloudscheduler.googleapis.com --project="$PROJECT_ID"

URL="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"
TARGET="${URL}/internal/communities?narrators=${NARRATORS}"

# The key rides in a header, not the query string. Cloud Scheduler can set
# custom headers -- Pub/Sub push cannot, which is why /internal/memories has
# no choice and this one does. A key in a URL is a key in access logs, in the
# Cloud Scheduler console, and in any screen recording of either.
COMMON=(
  --project="$PROJECT_ID"
  --location="$REGION"
  --schedule="$SCHEDULE"
  --time-zone="$TIMEZONE"
  --uri="$TARGET"
  --http-method=POST
  # Clustering plus one model call per chapter. The 180s default is generous
  # for one narrator and would not be for fifty.
  --attempt-deadline=600s
  # The endpoint answers 200 with per-narrator errors in the body rather than
  # failing, so a retry here means the request never arrived at all.
  --max-retry-attempts=3
  --min-backoff=60s
  --description="Recompute narrator chapters (label propagation + naming)"
)

# `^@^` sets @ as the KEY=VALUE delimiter, so a rotated key containing a comma
# cannot silently split into a second, bogus header. Same guard deploy.sh uses
# for env vars.
HEADER="^@^X-Sampan-Key=${API_KEY}"

# create and update do not take the same flag: `--headers` on one,
# `--update-headers` on the other. Passing the update form to create fails with
# an unrecognised-argument error, which is a thing to find out now rather than
# the first time the service URL changes.
if gcloud scheduler jobs describe "$JOB" \
     --project="$PROJECT_ID" --location="$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$JOB" "${COMMON[@]}" \
    --update-headers="$HEADER"
  echo "updated existing job"
else
  gcloud scheduler jobs create http "$JOB" "${COMMON[@]}" \
    --headers="$HEADER"
fi

echo
echo "Job     : $JOB"
echo "Schedule: $SCHEDULE ($TIMEZONE)"
echo "Target  : ${URL}/internal/communities?narrators=${NARRATORS}"
echo
echo "Run it now, without waiting for the schedule:"
echo "  gcloud scheduler jobs run $JOB --project=$PROJECT_ID --location=$REGION"
echo
echo "Check what it did:"
echo "  gcloud scheduler jobs describe $JOB --project=$PROJECT_ID --location=$REGION \\"
echo "    --format='value(status, lastAttemptTime)'"
