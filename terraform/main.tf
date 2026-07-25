# ---------------------------------------------------------------------------
# Enable the APIs this stack needs
# ---------------------------------------------------------------------------
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",       # GKE
    "artifactregistry.googleapis.com",# image registry
    "compute.googleapis.com",         # LB / networking for Ingress
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",  # Workload Identity Federation
    "sts.googleapis.com",             # token exchange for WIF
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
# GKE — Autopilot cluster (VPC-native by default, so container-native LB /
# NEG works with the Ingress). No node pools to manage.
# ---------------------------------------------------------------------------
resource "google_container_cluster" "add" {
  name     = var.cluster_name
  location = var.region

  enable_autopilot    = true
  deletion_protection = false # POC — allow `terraform destroy`

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Deployer service account used by GitHub Actions (impersonated via WIF —
# no JSON keys are ever created)
# ---------------------------------------------------------------------------
resource "google_service_account" "deployer" {
  account_id   = var.deployer_sa_id
  display_name = "ADD GitHub Actions deployer"
}

resource "google_project_iam_member" "ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "gke_developer" {
  project = var.project_id
  role    = "roles/container.developer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# ---------------------------------------------------------------------------
# Workload Identity Federation — lets GitHub Actions from THIS repo mint
# short-lived GCP credentials for the deployer SA, keylessly.
# ---------------------------------------------------------------------------
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Actions"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }
  # Only tokens from your GitHub org are accepted by this provider.
  attribute_condition = "assertion.repository_owner == '${var.github_owner}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow only Actions runs from <owner>/<repo> to impersonate the deployer SA.
resource "google_service_account_iam_member" "wif_impersonation" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.github_repo}"
}
