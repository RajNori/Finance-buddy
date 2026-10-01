# The billable runtime: VPC, NAT, ALB, WAF, ECS, RDS (~$0.18/hour).
# Off by default. Spin up for a demo, then turn off:
#   terraform apply -var runtime_enabled=true
#   terraform apply -var runtime_enabled=false

module "runtime" {
  source = "./modules/runtime"
  count  = var.runtime_enabled ? 1 : 0

  name                  = local.name
  db_name               = var.project
  ecr_repository_url    = aws_ecr_repository.app.repository_url
  image_tag             = var.image_tag
  openrouter_secret_arn = aws_secretsmanager_secret.openrouter_api_key.arn
  massive_secret_arn    = one(aws_secretsmanager_secret.massive_api_key[*].arn)
  alarm_topic_arn       = aws_sns_topic.alerts.arn

  vpc_cidr           = var.vpc_cidr
  single_nat_gateway = var.single_nat_gateway
  domain_name        = var.domain_name
  route53_zone_name  = var.route53_zone_name

  task_cpu           = var.task_cpu
  task_memory        = var.task_memory
  desired_count      = var.desired_count
  log_retention_days = var.log_retention_days

  db_instance_class      = var.db_instance_class
  db_allocated_storage   = var.db_allocated_storage
  db_multi_az            = var.db_multi_az
  db_deletion_protection = var.db_deletion_protection
  db_skip_final_snapshot = var.db_skip_final_snapshot

  enable_waf          = var.enable_waf
  waf_rate_limit      = var.waf_rate_limit
  waf_chat_rate_limit = var.waf_chat_rate_limit
}

locals {
  runtime = one(module.runtime[*])
}
