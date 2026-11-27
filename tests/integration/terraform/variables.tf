variable "region" {
  description = "AWS region to deploy the jumphost in."
  type        = string
}

variable "role_arn" {
  description = "IAM role to create the resources with. Null uses the caller's credentials."
  type        = string
  default     = null
}

variable "subnet_private_ids" {
  description = "Subnets for the jumphost instance, from pytest-infrahouse's service_network."
  type        = list(string)
}

variable "subnet_public_ids" {
  description = "Subnets for the jumphost's NLB, from pytest-infrahouse's service_network."
  type        = list(string)
}

variable "test_zone_id" {
  description = "Route53 zone for the jumphost's DNS record, from pytest-infrahouse's subzone."
  type        = string
}

variable "testing_repo_codename" {
  description = "Codename of the testing apt repository, for example noble-testing."
  type        = string
}

variable "testing_repo_url" {
  description = "URL of the testing apt repository, with a trailing slash."
  type        = string

  validation {
    condition     = can(regex("^https://[a-z0-9.-]+/$", var.testing_repo_url))
    error_message = "testing_repo_url must be an https URL of a host with a trailing slash. Got: ${var.testing_repo_url}"
  }
}

variable "toolkit_version" {
  description = <<-EOT
    The infrahouse-toolkit version under test, as the testing repository lists it,
    for example 2.68.3+candidate.259.1-1. The instance installs exactly this version.
  EOT
  type        = string

  validation {
    condition     = can(regex("^[0-9][A-Za-z0-9.+~-]*-[A-Za-z0-9.+~]+$", var.toolkit_version))
    error_message = "toolkit_version must be a Debian version with a revision, like 2.68.3+candidate.259.1-1. Got: ${var.toolkit_version}"
  }
}
