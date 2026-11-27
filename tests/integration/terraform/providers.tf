provider "aws" {
  region = var.region
  dynamic "assume_role" {
    for_each = var.role_arn != null ? [1] : []
    content {
      role_arn = var.role_arn
    }
  }
  default_tags {
    tags = {
      created_by = "infrahouse/infrahouse-toolkit" # GitHub repository that created a resource
    }
  }
}
