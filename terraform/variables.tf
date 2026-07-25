variable "project_id" {
  type        = string
  description = "GCP project ID to deploy into."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Region for the GKE cluster and Artifact Registry."
}

variable "cluster_name" {
  type        = string
  default     = "add-cluster"
  description = "GKE cluster name (must match the GKE_CLUSTER GitHub variable)."
}

variable "ar_repo_name" {
  type        = string
  default     = "add"
  description = "Artifact Registry (Docker) repository name (must match AR_REPO)."
}
