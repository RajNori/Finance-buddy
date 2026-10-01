output "app_url" {
  value = local.use_https ? "https://${var.domain_name}" : "http://${aws_lb.main.dns_name}"
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

output "ecs_cluster" {
  description = "GitHub variable ECS_CLUSTER"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service" {
  description = "GitHub variable ECS_SERVICE"
  value       = aws_ecs_service.app.name
}

output "ecs_task_family" {
  description = "GitHub variable ECS_TASK_FAMILY"
  value       = aws_ecs_task_definition.app.family
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

output "db_endpoint" {
  value = aws_db_instance.main.address
}
