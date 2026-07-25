terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  # For a team, store state in a GCS bucket instead of locally:
  # backend "gcs" {
  #   bucket = "my-tf-state-bucket"
  #   prefix = "add/gke"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
