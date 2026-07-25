#!/usr/bin/env bash
# POC helper: point kubectl at the cluster, expose Qdrant on a LoadBalancer,
# and print the public dashboard URL. Run in Google Cloud Shell.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-ai-driven-development-503519}"
REGION="${REGION:-us-central1}"
CLUSTER="${CLUSTER:-add-cluster}"

echo "==> Fetching cluster credentials..."
gcloud container clusters get-credentials "$CLUSTER" --region "$REGION" --project "$PROJECT_ID"

echo "==> Ensuring the Qdrant LoadBalancer service exists..."
kubectl apply -f - <<'EOF'
apiVersion: v1
kind: Service
metadata:
  name: add-qdrant-lb
  namespace: add
spec:
  type: LoadBalancer
  selector: { app: add-qdrant }
  ports:
    - name: http
      port: 6333
      targetPort: 6333
EOF

echo "==> Waiting for the external IP (up to ~5 min)..."
IP=""
for _ in $(seq 1 60); do
  IP=$(kubectl -n add get svc add-qdrant-lb \
        -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  [ -n "$IP" ] && break
  sleep 5
done

echo ""
if [ -n "$IP" ]; then
  echo "======================================================"
  echo "  Qdrant dashboard:  http://${IP}:6333/dashboard"
  echo "======================================================"
else
  echo "IP still pending. Re-run this script, or check:"
  echo "  kubectl -n add get svc add-qdrant-lb"
fi
