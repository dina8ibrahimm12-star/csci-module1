terraform {
  required_version = ">= 1.5"
  required_providers {
    aws   = { source = "hashicorp/aws", version = "~> 5.0" }
    local = { source = "hashicorp/local", version = "~> 2.4" }
  }
}

# No credentials here, ever. Terraform reads them from your AWS profile
# (AWS_PROFILE) or environment, as set up in docs/RUNBOOK.md (step 3).
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = "lab"
      ManagedBy   = "terraform"
    }
  }
}
