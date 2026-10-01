output "app_url" {
  value = local.use_https ? "https://${var.domain_name}" : "http://${aws_lb.main.dns_name}"
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service" {
  value = aws_ecs_service.app.name
}

output "ecs_service_arn" {
  value = aws_ecs_service.app.id
}

output "ecs_task_family" {
  value = aws_ecs_task_definition.app.family
}

output "execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "db_endpoint" {
  value = aws_db_instance.main.address
}
