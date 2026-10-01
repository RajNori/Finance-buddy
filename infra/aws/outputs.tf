output "runtime_enabled" {
  value = var.runtime_enabled
}

output "aws_region" {
  value = var.region
}

output "ecr_repository" {
  description = "GitHub variable ECR_REPOSITORY"
  value       = aws_ecr_repository.app.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "github_deploy_role_arn" {
  description = "GitHub variable AWS_DEPLOY_ROLE_ARN"
  value       = aws_iam_role.github_deploy.arn
}

output "openrouter_secret_id" {
  description = "Set with: aws secretsmanager put-secret-value --secret-id <this> --secret-string '<key>'"
  value       = aws_secretsmanager_secret.openrouter_api_key.name
}

output "massive_secret_id" {
  value = one(aws_secretsmanager_secret.massive_api_key[*].name)
}

# --- Runtime (null while dormant) -------------------------------------------

output "app_url" {
  value = try(local.runtime.app_url, null)
}

output "ecs_cluster" {
  description = "GitHub variable ECS_CLUSTER"
  value       = try(local.runtime.ecs_cluster, null)
}

output "ecs_service" {
  description = "GitHub variable ECS_SERVICE"
  value       = try(local.runtime.ecs_service, null)
}

output "ecs_task_family" {
  description = "GitHub variable ECS_TASK_FAMILY"
  value       = try(local.runtime.ecs_task_family, null)
}

output "db_endpoint" {
  value = try(local.runtime.db_endpoint, null)
}
