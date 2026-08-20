#!/usr/bin/env bash
# Provision transcript screening: two DLP templates and the Model Armor
# template that points at them.
#
# Deliberately narrow. Model Armor's basic SDP config enables Google's whole
# default info-type set, which on an eighty-year-old's life story means names,
# dates, addresses and health details -- it would redact the archive itself.
#
# What actually detects what, measured rather than assumed:
#   FINANCIAL_ACCOUNT_NUMBER  finds nothing here, despite the name
#   CREDIT_CARD_NUMBER        works, Luhn-checkable
#   MALAYSIA_*                does not exist; there is no IC detector either
#   custom regex below        one finding across her whole archive, no false
#                             positives on years or dates
set -euo pipefail

PROJECT="${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
LOCATION="${SAMPAN_ARMOR_LOCATION:-asia-southeast1}"
TOKEN="$(gcloud auth print-access-token)"
API="https://dlp.googleapis.com/v2/projects/$PROJECT/locations/$LOCATION"

post() { curl -sS -X "$1" -H "Authorization: Bearer $TOKEN" \
  -H "x-goog-user-project: $PROJECT" -H "Content-Type: application/json" \
  "$2" -d "$3"; }

echo "==> inspect template"
post POST "$API/inspectTemplates" '{
  "templateId": "sampan-bank-only",
  "inspectTemplate": {
    "displayName": "Sampan — account and card numbers only",
    "inspectConfig": {
      "infoTypes": [{"name": "CREDIT_CARD_NUMBER"}],
      "customInfoTypes": [{
        "infoType": {"name": "BANK_ACCOUNT_NUMBER"},
        "likelihood": "VERY_LIKELY",
        "regex": {"pattern": "[0-9]{4}[ -]?[0-9]{4}[ -]?[0-9]{2,8}"}
      }],
      "minLikelihood": "LIKELY", "includeQuote": false
    }
  }
}' | head -c 200; echo

echo "==> de-identify template"
post POST "$API/deidentifyTemplates" '{
  "templateId": "sampan-bank-redact",
  "deidentifyTemplate": {
    "displayName": "Sampan — replace account and card numbers",
    "deidentifyConfig": {
      "infoTypeTransformations": {
        "transformations": [{
          "infoTypes": [{"name": "CREDIT_CARD_NUMBER"}, {"name": "BANK_ACCOUNT_NUMBER"}],
          "primitiveTransformation": {"replaceWithInfoTypeConfig": {}}
        }]
      }
    }
  }
}' | head -c 200; echo

echo "==> model armor template"
post POST \
  "https://modelarmor.$LOCATION.rep.googleapis.com/v1/projects/$PROJECT/locations/$LOCATION/templates?template_id=sampan-transcripts" \
  "{\"filterConfig\":{\"sdpSettings\":{\"advancedConfig\":{
      \"inspectTemplate\":\"projects/$PROJECT/locations/$LOCATION/inspectTemplates/sampan-bank-only\",
      \"deidentifyTemplate\":\"projects/$PROJECT/locations/$LOCATION/deidentifyTemplates/sampan-bank-redact\"}}}}" \
  | head -c 200; echo

echo "==> service agent access to the DLP templates"
# Without this the filter is SKIPPED and Model Armor still answers 200: a
# screen that reports success and protects nothing.
NUM="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:service-${NUM}@gcp-sa-modelarmor.iam.gserviceaccount.com" \
  --role=roles/dlp.user --condition=None --quiet >/dev/null

echo
echo "Done. Redeploy with SAMPAN_ARMOR_TEMPLATE=sampan-transcripts"
