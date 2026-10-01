# Always-on, near-zero-cost resources. These survive runtime spin-down so
# images, keys and the deploy role persist between demos.

resource "aws_ecr_repository" "app" {
  name                 = var.project
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the 10 most recent images (~$0.10/GB-month)"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# Values are set out-of-band so they never touch state:
#   aws secretsmanager put-secret-value --secret-id <name> --secret-string '<key>'
resource "aws_secretsmanager_secret" "openrouter_api_key" {
  name                    = "${local.name}/openrouter-api-key"
  description             = "OpenRouter API key for LLM chat"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "massive_api_key" {
  count                   = var.enable_massive ? 1 : 0
  name                    = "${local.name}/massive-api-key"
  description             = "Massive (Polygon.io) market data API key"
  recovery_window_in_days = 7
}

# --- Alerts and cost guardrail (free) ---------------------------------------

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alarm_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alarm_email]
  }
}
