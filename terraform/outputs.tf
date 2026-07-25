# These map 1:1 onto the GitHub Actions config in .github/workflows/deploy-gke.yml.
# After `terraform apply`, run `terraform output` and paste them into
# GitHub ▸ Settings ▸ Secrets and variables ▸ Actions.

# --- Repository VARIABLES ---
output "GCP_PROJECT_ID" {
  value = var.project_id
}

output "GCP_REGION" {
  value = var.region
}

output "AR_REPO" {
  value = google_artifact_registry_repository.add.repository_id
}

output "GKE_CLUSTER" {
  value = google_container_cluster.add.name
}

output "GKE_LOCATION" {
  value = google_container_cluster.add.location
}

# --- Repository SECRETS (infra ones; app secrets you set yourself) ---
output "WIF_PROVIDER" {
  description = "Full resource name of the Workload Identity provider."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "WIF_SERVICE_ACCOUNT" {
  description = "Deployer service account email."
  value       = google_service_account.deployer.email
}

# Handy for `gcloud container clusters get-credentials`
output "artifact_registry_host" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.add.repository_id}"
}
