# Terraform — GCP foundation for ADD

This provisions the GCP infrastructure the app is deployed onto. It is the layer
*below* `k8s/`:

| Layer | Provisions | Tool |
|---|---|---|
| **terraform/** (this) | GKE cluster, Artifact Registry, Workload Identity Federation, deployer SA + IAM, enabled APIs | Terraform |
| **k8s/** | The app itself — pods, services, ingress — inside the cluster | kustomize / kubectl |
| **.github/workflows/** | Builds images + applies `k8s/` on every push | GitHub Actions |

State lives in a **GCS bucket** (shared by local + CI). Create it once, then init
with the bucket/prefix:

```bash
export PROJECT_ID=your-project REGION=us-central1
gsutil mb -l $REGION gs://$PROJECT_ID-tf-state
gsutil versioning set on gs://$PROJECT_ID-tf-state
```

## One-time apply (local)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in project_id (+ owner/repo)
terraform init \
  -backend-config="bucket=$PROJECT_ID-tf-state" \
  -backend-config="prefix=add/gke"
terraform plan
terraform apply
```

You need `gcloud auth application-default login` first (or a `GOOGLE_APPLICATION_CREDENTIALS`),
and your user must have Owner/Editor + IAM admin on the project to create the SA
and Workload Identity resources.

## Deploy via GitHub Actions (`.github/workflows/terraform.yml`)

PRs touching `terraform/**` run `plan`; pushes to `main` (and manual dispatch)
run `apply`. Auth is keyless via WIF, using a **privileged** Terraform service
account — distinct from the app-deploy SA, which lacks permission to manage
clusters/IAM.

**Bootstrap once (project Owner, locally)** — after the local apply above created
the `github-pool`:

```bash
export REPO=hubbridge-developer/ai-driven-development
gcloud iam service-accounts create add-terraform --display-name="ADD Terraform CI"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:add-terraform@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/owner"
POOL=$(gcloud iam workload-identity-pools describe github-pool --location=global --format='value(name)')
gcloud iam service-accounts add-iam-policy-binding \
  add-terraform@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/$POOL/attribute.repository/$REPO"
```

**GitHub config** (Settings ▸ Secrets and variables ▸ Actions):

- **Variables:** `TF_STATE_BUCKET` (= `$PROJECT_ID-tf-state`), plus the existing
  `GCP_PROJECT_ID`, `GCP_REGION` (reused; `github_owner`/`github_repo` come from
  the Actions context automatically).
- **Secrets:** `TF_SERVICE_ACCOUNT` (= `add-terraform@$PROJECT_ID.iam.gserviceaccount.com`),
  `TF_WIF_PROVIDER` (same value as the `WIF_PROVIDER` output).

## Wire the outputs into GitHub

```bash
terraform output      # prints values named exactly like the GitHub config
```

Put these under **GitHub ▸ Settings ▸ Secrets and variables ▸ Actions**:

- **Variables:** `GCP_PROJECT_ID`, `GCP_REGION`, `AR_REPO`, `GKE_CLUSTER`, `GKE_LOCATION`
- **Secrets:** `WIF_PROVIDER`, `WIF_SERVICE_ACCOUNT`
- **App secrets you set yourself** (not from Terraform): `DJANGO_SECRET_KEY`,
  `DATABASE_URL`, `POSTGRES_PASSWORD`, `DJANGO_SUPERUSER_PASSWORD`,
  `ANTHROPIC_API_KEY`, `ENCRYPTION_KEY`, `APP_GITHUB_PAT`

Then push to `main` (or run the workflow manually) and it deploys.

## Notes

- **Autopilot** cluster: no node pools to manage, always VPC-native so the
  Ingress NEG annotations work. Switch to a Standard cluster + node pool in
  `main.tf` if you want fixed nodes / lower idle cost.
- **Keyless CI:** Workload Identity Federation means no service-account JSON key
  is ever created or stored in GitHub. Only Actions runs from
  `github_owner/github_repo` can impersonate the deployer SA.
- **State:** stored locally by default. For a team, uncomment the `gcs` backend
  in `versions.tf`.
- **Cost:** an Autopilot cluster + LB + Artifact Registry bills while it exists.
  `terraform destroy` tears it all down when you're done.
- The in-cluster Postgres is fine for a POC; for production, provision Cloud SQL
  here and point `DATABASE_URL` at it instead of the StatefulSet.
