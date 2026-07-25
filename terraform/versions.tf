terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # Remote state in GCS. Bucket/prefix are supplied at init via -backend-config
  # (see terraform/README.md) so CI and local runs share the same state.
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}
