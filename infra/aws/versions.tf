terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Partial configuration: values come from backend.hcl (see backend.hcl.example).
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = var.github_repo
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name           = "${var.project}-${var.environment}"
  azs            = slice(data.aws_availability_zones.available.names, 0, 2)
  container_name = "app"
  container_port = 8000
  use_https      = var.domain_name != ""
  account_id     = data.aws_caller_identity.current.account_id
}
