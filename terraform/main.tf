# The identity/trust plumbing (Workload Identity pool/provider, CI service
# account, state bucket) is created once by bootstrap.sh in Cloud Shell — it
# cannot be managed by the same Terraform that authenticates through it.
# This config manages the actual infrastructure, applied by GitHub Actions.

# ---------------------------------------------------------------------------
# Enable the resource APIs
# ---------------------------------------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",        # GKE
    "artifactregistry.googleapis.com", # image registry
    "compute.googleapis.com",          # LB / networking for the Ingress
  ])
  service            = each.key
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Artifact Registry — where CI pushes the backend/frontend images
# ---------------------------------------------------------------------------
resource "google_artifact_registry_repository" "add" {
  location      = var.region
  repository_id = var.ar_repo_name
  format        = "DOCKER"
  description   = "AI-Driven Development (ADD) container images"
  depends_on    = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# GKE — Autopilot cluster (VPC-native by default, so container-native LB / NEG
# works with the Ingress). No node pools to manage.
# ---------------------------------------------------------------------------
resource "google_container_cluster" "add" {
  name     = var.cluster_name
  location = var.region

  enable_autopilot    = true
  deletion_protection = false # POC — allow `terraform destroy`

  depends_on = [google_project_service.apis]
}
