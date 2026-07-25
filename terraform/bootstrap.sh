#!/usr/bin/env bash
# =============================================================================
# ONE-TIME bootstrap — run in Google Cloud Shell (https://shell.cloud.google.com),
# NOT on your laptop. Nothing to install; Cloud Shell has gcloud + auth already.
#
# It establishes the keyless trust so that AFTER this, every deploy — including
# `terraform apply` — runs in GitHub Actions. It creates:
#   • a GCS bucket for Terraform state
#   • a Workload Identity pool + GitHub OIDC provider
#   • one CI service account (Owner, POC) that both workflows impersonate
#   • the binding that lets ONLY this repo's Actions use that SA
#
# Safe to re-run — "already exists" messages are fine.
# =============================================================================
set -euo pipefail

# ---- SET THESE (edit here, or pass as env vars when running) ----
#   PROJECT_ID=my-project REPO=owner/name bash bootstrap.sh
PROJECT_ID="${PROJECT_ID:-your-gcp-project}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-hubbridge-developer/ai-driven-development}"   # owner/name
# -----------------------------------------------------------------

if [ "$PROJECT_ID" = "your-gcp-project" ]; then
  echo "ERROR: set your real GCP project id first, e.g.:" >&2
  echo "  PROJECT_ID=my-project REPO=hubbridge-developer/ai-driven-development bash bootstrap.sh" >&2
  echo "Find it with: gcloud projects list" >&2
  exit 1
fi

SA="add-ci"
POOL="github-pool"
PROVIDER="github-provider"
BUCKET="${PROJECT_ID}-tf-state"
OWNER="${REPO%%/*}"
SA_EMAIL="${SA}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"

echo "==> Enabling identity APIs..."
gcloud services enable iam.googleapis.com iamcredentials.googleapis.com \
  sts.googleapis.com cloudresourcemanager.googleapis.com storage.googleapis.com

echo "==> Creating GCS state bucket gs://$BUCKET ..."
gsutil mb -l "$REGION" "gs://$BUCKET" 2>/dev/null || echo "    (bucket already exists)"
gsutil versioning set on "gs://$BUCKET"

echo "==> Creating CI service account $SA ..."
gcloud iam service-accounts create "$SA" \
  --display-name="ADD CI (Terraform + deploy)" 2>/dev/null || echo "    (SA already exists)"

echo "==> Granting roles/owner to $SA_EMAIL (POC — tighten for production)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${SA_EMAIL}" --role="roles/owner" --condition=None -q >/dev/null

echo "==> Creating Workload Identity pool + GitHub provider..."
gcloud iam workload-identity-pools create "$POOL" --location=global \
  --display-name="GitHub Actions" 2>/dev/null || echo "    (pool already exists)"
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
  --location=global --workload-identity-pool="$POOL" \
  --display-name="GitHub OIDC" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner=='${OWNER}'" 2>/dev/null || echo "    (provider already exists)"

echo "==> Binding ${REPO} -> impersonate ${SA_EMAIL}..."
POOL_NAME=$(gcloud iam workload-identity-pools describe "$POOL" --location=global --format='value(name)')
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository/${REPO}" >/dev/null

PROVIDER_NAME=$(gcloud iam workload-identity-pools providers describe "$PROVIDER" \
  --location=global --workload-identity-pool="$POOL" --format='value(name)')

cat <<EOF

=============================================================================
 Bootstrap complete. Put these in GitHub ▸ Settings ▸ Secrets and variables ▸ Actions
=============================================================================
 Variables (Repository variables):
   GCP_PROJECT_ID   = ${PROJECT_ID}
   GCP_REGION       = ${REGION}
   AR_REPO          = add
   GKE_CLUSTER      = add-cluster
   GKE_LOCATION     = ${REGION}
   TF_STATE_BUCKET  = ${BUCKET}

 Secrets (infra):
   WIF_PROVIDER         = ${PROVIDER_NAME}
   WIF_SERVICE_ACCOUNT  = ${SA_EMAIL}

 Secrets (app — you provide the values):
   DJANGO_SECRET_KEY, DATABASE_URL, POSTGRES_PASSWORD, DJANGO_SUPERUSER_PASSWORD,
   ANTHROPIC_API_KEY, ENCRYPTION_KEY, APP_GITHUB_PAT
=============================================================================
Next: run the "Terraform (GCP infra)" workflow (Actions tab) to build the
cluster, then the "Deploy to GKE" workflow deploys the app.
EOF
