variable "region" {
  description = "AWS region. Sydney keeps latency low for AU users."
  type        = string
  default     = "ap-southeast-2"
}

variable "project" {
  type    = string
  default = "financebuddy"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "github_repo" {
  description = "owner/repo allowed to deploy via OIDC. Case-sensitive; must match GitHub's canonical name."
  type        = string
  default     = "RajNori/Finance-buddy"
}

variable "github_environment" {
  description = "GitHub Actions environment that gates deploys (add required reviewers there)."
  type        = string
  default     = "production"
}

variable "create_github_oidc_provider" {
  description = "Set false if the account already has the token.actions.githubusercontent.com provider."
  type        = bool
  default     = true
}

variable "alarm_email" {
  description = "Receives CloudWatch alarm and budget notifications."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Account-level monthly budget; alerts at 80% forecast and 100% actual."
  type        = number
  default     = 200
}

# --- Networking -------------------------------------------------------------

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "single_nat_gateway" {
  description = "One NAT gateway (cheaper) vs one per AZ (survives an AZ outage)."
  type        = bool
  default     = true
}

# --- DNS / TLS (optional) ---------------------------------------------------

variable "domain_name" {
  description = "e.g. financebuddy.rajnori.net. Empty = HTTP on the ALB DNS name only."
  type        = string
  default     = ""
}

variable "route53_zone_name" {
  description = "Public Route 53 hosted zone that contains domain_name, e.g. rajnori.net."
  type        = string
  default     = ""
}

# --- Compute ----------------------------------------------------------------

variable "task_cpu" {
  type    = number
  default = 512
}

variable "task_memory" {
  type    = number
  default = 1024
}

variable "desired_count" {
  description = <<-EOT
    Keep at 1. The price simulator and snapshot task run in-process, so
    multiple tasks would serve divergent prices. Scale out only after moving
    market data to a shared store (see infra/README.md, phase 2).
  EOT
  type        = number
  default     = 1

  validation {
    condition     = var.desired_count >= 0 && var.desired_count <= 1
    error_message = "desired_count must be 0 or 1 until market data is externalised."
  }
}

variable "image_tag" {
  description = "Initial image tag for the Terraform-managed task definition. CI deploys replace it."
  type        = string
  default     = "bootstrap"
}

variable "enable_massive" {
  description = "Wire MASSIVE_API_KEY from Secrets Manager. False = built-in simulator."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  type    = number
  default = 30
}

# --- Database ---------------------------------------------------------------

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_multi_az" {
  description = "Standby replica in a second AZ. Roughly doubles DB cost."
  type        = bool
  default     = false
}

variable "db_deletion_protection" {
  type    = bool
  default = true
}

# --- Edge protection --------------------------------------------------------

variable "enable_waf" {
  type    = bool
  default = true
}

variable "waf_rate_limit" {
  description = "Max requests per IP per 5 minutes across the whole site."
  type        = number
  default     = 2000
}

variable "waf_chat_rate_limit" {
  description = "Max /api/chat requests per IP per 5 minutes. Caps LLM spend from abuse."
  type        = number
  default     = 60
}
