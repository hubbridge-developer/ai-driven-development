variable "project_id" {
  type        = string
  description = "GCP project ID to deploy into."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Region for the GKE cluster and Artifact Registry."
}

variable "github_owner" {
  type        = string
  default     = "hubbridge-developer"
  description = "GitHub account/org that owns the repo (used to scope Workload Identity)."
}

variable "github_repo" {
  type        = string
  default     = "ai-driven-development"
  description = "GitHub repo name (without owner). Only Actions from this repo can deploy."
}

variable "cluster_name" {
  type        = string
  default     = "add-cluster"
  description = "GKE cluster name."
}

variable "ar_repo_name" {
  type        = string
  default     = "add"
  description = "Artifact Registry (Docker) repository name."
}

variable "deployer_sa_id" {
  type        = string
  default     = "add-deployer"
  description = "Service account id used by GitHub Actions to build+deploy."
}
