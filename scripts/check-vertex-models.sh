#!/usr/bin/env bash
# Check whether Vertex AI Gemini models are usable in your project/region BEFORE
# deploying. Run in Google Cloud Shell (uses your gcloud auth). A model is only
# truly usable if this returns OK (200) — it verifies existence + region + access.
#
#   bash scripts/check-vertex-models.sh                 # checks the common ids
#   bash scripts/check-vertex-models.sh gemini-2.5-pro  # check specific id(s)
set -uo pipefail

PROJECT="${PROJECT_ID:-ai-driven-development-503519}"
REGION="${REGION:-us-central1}"

if [ "$#" -gt 0 ]; then
  MODELS=("$@")
else
  MODELS=(gemini-2.0-flash-001 gemini-2.5-flash gemini-2.5-pro gemini-1.5-pro-002)
fi

TOKEN=$(gcloud auth print-access-token)
echo "Project: $PROJECT   Region: $REGION"
echo "-------------------------------------------"
for M in "${MODELS[@]}"; do
  CODE=$(curl -s -o /tmp/vresp -w "%{http_code}" -X POST \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    "https://${REGION}-aiplatform.googleapis.com/v1/projects/${PROJECT}/locations/${REGION}/publishers/google/models/${M}:generateContent" \
    -d '{"contents":[{"role":"user","parts":[{"text":"ping"}]}],"generationConfig":{"maxOutputTokens":1}}')
  if [ "$CODE" = "200" ]; then
    printf "  OK          %s\n" "$M"
  else
    REASON=$(python3 -c "import json;print(json.load(open('/tmp/vresp')).get('error',{}).get('status',''))" 2>/dev/null || true)
    printf "  FAIL(%s)  %s   %s\n" "$CODE" "$M" "${REASON:+-> $REASON}"
  fi
done
echo "-------------------------------------------"
echo "Use the OK ids in config/llm_routing_vertex.yaml (prefix them 'vertex_ai/')."
echo "For CLAUDE models, enable them in Vertex Model Garden (console) — they live"
echo "under publishers/anthropic and are region-limited (often us-east5)."
