# Terraform — GCP foundation for ADD

Provisions the GCP infrastructure the app runs on. Designed so **every deploy
runs in GitHub Actions** — the only manual step is a one-time bootstrap in the
browser (Google Cloud Shell), never your laptop.

```
bootstrap.sh (Cloud Shell, once)  → trust + state bucket + CI service account
        │  outputs GitHub config ↓
terraform/  (GitHub Actions)      → GKE cluster + Artifact Registry
k8s/        (GitHub Actions)      → the app on the cluster
```

Why a bootstrap at all? Keyless auth (Workload Identity Federation) needs an
initial trust relationship, and Terraform can't create the very identity it
authenticates through. So `bootstrap.sh` creates that once; Terraform manages
everything else from CI.

## Step 1 — Bootstrap (once, in Google Cloud Shell)

Open **https://shell.cloud.google.com** (nothing to install), then:

```bash
# clone your repo (or upload just terraform/bootstrap.sh)
git clone https://github.com/hubbridge-developer/ai-driven-development
cd ai-driven-development/terraform
# edit the 3 vars at the top of bootstrap.sh (PROJECT_ID, REGION, REPO)
bash bootstrap.sh
```

It creates the state bucket, the Workload Identity pool + GitHub provider, and a
single **CI service account** (Owner, for the POC) that both workflows use. It
prints the exact GitHub Variables/Secrets to set.

## Step 2 — Configure GitHub (Settings ▸ Secrets and variables ▸ Actions)

**Variables** (from the bootstrap output):
`GCP_PROJECT_ID`, `GCP_REGION`, `AR_REPO`, `GKE_CLUSTER`, `GKE_LOCATION`, `TF_STATE_BUCKET`

**Secrets — infra** (from the bootstrap output):
`WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`

**Secrets — app** (you choose these values):
`DJANGO_SECRET_KEY`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `DJANGO_SUPERUSER_PASSWORD`,
`ANTHROPIC_API_KEY`, `ENCRYPTION_KEY`, `APP_GITHUB_PAT`

> `DATABASE_URL` and `POSTGRES_PASSWORD` must agree, e.g.
> `postgresql://add:<pw>@add-postgres:5432/add` with `POSTGRES_PASSWORD=<pw>`.

## Step 3 — Build the infra (GitHub Actions)

**Actions ▸ Terraform (GCP infra) ▸ Run workflow** (or push a change under
`terraform/**`). It runs `plan` on PRs and `apply` on `main` — creating the GKE
Autopilot cluster + Artifact Registry. State is stored in your GCS bucket, so
runs are stateful and repeatable.

## Step 4 — Deploy the app (GitHub Actions)

Once the cluster exists, **Actions ▸ Deploy to GKE ▸ Run workflow** (or push app
code). It builds both images → Artifact Registry, applies `k8s/`, and prints the
Ingress IP. Open `http://<INGRESS_IP>/`.

> First-time ordering: run **Terraform** first (Step 3), then **Deploy** — the
> deploy needs the cluster to already exist. Afterwards, normal pushes to `main`
> just work.

## Notes

- **No local tooling required** — bootstrap runs in Cloud Shell; all applies run
  in Actions.
- **Autopilot** cluster: no node pools, always VPC-native so the Ingress NEG
  annotations work.
- **Cost:** the cluster + LB + registry bill while they exist. To tear down, run
  `terraform destroy` (locally or via a manual Actions job), then delete the
  bootstrap resources if you're fully done.
- **Least privilege:** the CI SA uses `roles/owner` for simplicity. For
  production, replace it (in `bootstrap.sh`) with `roles/container.admin`,
  `roles/artifactregistry.admin`, `roles/compute.networkAdmin`, and
  `roles/serviceusage.serviceUsageAdmin`.
- **Cloud SQL:** the in-cluster Postgres is POC-grade; for production add a
  `google_sql_database_instance` here and point `DATABASE_URL` at it.
