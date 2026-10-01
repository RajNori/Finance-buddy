variable "name" {
  description = "Resource name prefix, e.g. financebuddy-prod"
  type        = string
}

variable "db_name" {
  type = string
}

variable "ecr_repository_url" {
  type = string
}

variable "image_tag" {
  type = string
}

variable "openrouter_secret_arn" {
  type = string
}

variable "massive_secret_arn" {
  description = "Null = use the built-in simulator"
  type        = string
  default     = null
}

variable "alarm_topic_arn" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "single_nat_gateway" {
  type = bool
}

variable "domain_name" {
  type = string
}

variable "route53_zone_name" {
  type = string
}

variable "task_cpu" {
  type = number
}

variable "task_memory" {
  type = number
}

variable "desired_count" {
  type = number
}

variable "log_retention_days" {
  type = number
}

variable "db_instance_class" {
  type = string
}

variable "db_allocated_storage" {
  type = number
}

variable "db_multi_az" {
  type = bool
}

variable "db_deletion_protection" {
  type = bool
}

variable "db_skip_final_snapshot" {
  type = bool
}

variable "enable_waf" {
  type = bool
}

variable "waf_rate_limit" {
  type = number
}

variable "waf_chat_rate_limit" {
  type = number
}
