# WIF_PROVIDER and WIF_SERVICE_ACCOUNT come from bootstrap.sh, not Terraform.
# These outputs confirm what Terraform created; the GitHub Variables of the same
# names are printed by bootstrap.sh.

output "GKE_CLUSTER" {
  value = google_container_cluster.add.name
}

output "GKE_LOCATION" {
  value = google_container_cluster.add.location
}

output "AR_REPO" {
  value = google_artifact_registry_repository.add.repository_id
}

output "artifact_registry_host" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.add.repository_id}"
}
