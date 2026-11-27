terraform {
  # terraform-aws-jumphost 6.1.1 needs 1.7, for `removed` blocks with lifecycle.destroy.
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0, < 7.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
  }
}
