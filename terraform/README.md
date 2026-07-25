# Terraform — GCP foundation for ADD

This provisions the GCP infrastructure the app is deployed onto. It is the layer
*below* `k8s/`:

| Layer | Provisions | Tool |
|---|---|---|
| **terraform/** (this) | GKE cluster, Artifact Registry, Workload Identity Federation, deployer SA + IAM, enabled APIs | Terraform |
| **k8s/** | The app itself — pods, services, ingress — inside the cluster | kustomize / kubectl |
| **.github/workflows/** | Builds images + applies `k8s/` on every push | GitHub Actions |

## One-time apply

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill in project_id (+ owner/repo)
terraform init
terraform plan
terraform apply
```

You need `gcloud auth application-default login` first (or a `GOOGLE_APPLICATION_CREDENTIALS`),
and your user must have Owner/Editor + IAM admin on the project to create the SA
and Workload Identity resources.

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
