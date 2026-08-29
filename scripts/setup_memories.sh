#!/usr/bin/env bash
# Provision generated card imagery: a bucket, a topic, and the push
# subscription that joins them to /internal/memories.
#
# Optional. Without it `publish` is a quiet no-op and the endpoint declines, so
# the app runs exactly as before with one fewer feature (D21).
#
# Idempotent: every step tolerates already existing, so this is safe to re-run
# after a redeploy changes the service URL.
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
BUCKET="${SAMPAN_MEMORIES_BUCKET:-${PROJECT_ID}-memories}"
TOPIC="${SAMPAN_MEMORIES_TOPIC:-sampan-memories}"
DEAD="${TOPIC}-dead"

NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
# The Pub/Sub service agent, not the runtime account: dead-lettering is done by
# Pub/Sub on its own behalf and fails silently without these two bindings.
PUBSUB_SA="service-${NUMBER}@gcp-sa-pubsub.iam.gserviceaccount.com"
RUNTIME_SA="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" \
  --format='value(spec.template.spec.serviceAccountName)')"
URL="$(gcloud run services describe "$SERVICE" \
  --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"

ok() { "$@" 2>&1 | tail -1 || true; }

gcloud services enable pubsub.googleapis.com storage.googleapis.com \
  --project="$PROJECT_ID"

ok gcloud storage buckets create "gs://$BUCKET" \
  --location="$REGION" --project="$PROJECT_ID" --uniform-bucket-level-access
# Cards load the URL directly, so the objects are world-readable. Nothing
# identifying is in them by construction: the prompt forbids people and faces,
# and the object name is a story id rather than anything she said.
ok gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member=allUsers --role=roles/storage.objectViewer --project="$PROJECT_ID"
ok gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role=roles/storage.objectAdmin --project="$PROJECT_ID"

ok gcloud pubsub topics create "$DEAD" --project="$PROJECT_ID"
ok gcloud pubsub topics create "$TOPIC" --project="$PROJECT_ID"
# A topic with no subscription drops what it receives, so a dead-letter topic
# without one is a backstop that catches nothing and reports nothing. This is
# how four failed renders vanished with no trace to read afterwards. Nothing
# consumes it; it exists so the failures are still there to pull:
#   gcloud pubsub subscriptions pull "${DEAD}-hold" --auto-ack --limit=10
ok gcloud pubsub subscriptions create "${DEAD}-hold" --project="$PROJECT_ID" \
  --topic="$DEAD" --message-retention-duration=7d

# --ack-deadline=600 matters: Veo takes tens of seconds and the 10s default
# redelivers while the first attempt is still generating, billing for each.
#
# --max-delivery-attempts is 5 because 5 is the floor Pub/Sub allows; the README
# said 3 for a while, which is simply rejected. It rarely binds either way --
# the endpoint answers 200 even on failure, precisely so a wedged message
# cannot retry a paid model call forever.
ok gcloud pubsub subscriptions create "${TOPIC}-push" --project="$PROJECT_ID" \
  --topic="$TOPIC" \
  --push-endpoint="${URL}/internal/memories?key=${API_KEY}" \
  --ack-deadline=600 \
  --max-delivery-attempts=5 \
  --dead-letter-topic="$DEAD"
# Existing subscription, new service URL.
ok gcloud pubsub subscriptions update "${TOPIC}-push" --project="$PROJECT_ID" \
  --push-endpoint="${URL}/internal/memories?key=${API_KEY}"

ok gcloud pubsub topics add-iam-policy-binding "$DEAD" --project="$PROJECT_ID" \
  --member="serviceAccount:${PUBSUB_SA}" --role=roles/pubsub.publisher
ok gcloud pubsub subscriptions add-iam-policy-binding "${TOPIC}-push" \
  --project="$PROJECT_ID" \
  --member="serviceAccount:${PUBSUB_SA}" --role=roles/pubsub.subscriber

echo
echo "Done. Put these in .env, then ./deploy.sh:"
echo "  SAMPAN_MEMORIES_TOPIC=$TOPIC"
echo "  SAMPAN_MEMORIES_BUCKET=$BUCKET"
echo
echo "Backfill existing stories with: python scripts/backfill_memories.py"
