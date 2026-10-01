# --- Container registry -----------------------------------------------------

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
      description  = "Keep the 30 most recent images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 30
      }
      action = { type = "expire" }
    }]
  })
}

# --- Application secrets ----------------------------------------------------
# Terraform creates the containers only. Values are set out-of-band so they
# never touch state:
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

# --- Database ---------------------------------------------------------------

resource "random_password" "db" {
  length  = 32
  special = false # URL-safe; embedded in DATABASE_URL
}

resource "aws_db_subnet_group" "main" {
  name       = local.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_db_parameter_group" "main" {
  name   = "${local.name}-pg17"
  family = "postgres17"

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }
}

resource "aws_db_instance" "main" {
  identifier     = local.name
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.project
  username = var.project
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.main.name
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  # Windows in UTC: backups ~2-3am AEST, maintenance Monday ~3:30am AEST.
  backup_retention_period    = 7
  backup_window              = "16:00-17:00"
  maintenance_window         = "sun:17:30-sun:18:30"
  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true

  enabled_cloudwatch_logs_exports = ["postgresql"]

  deletion_protection       = var.db_deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = "${local.name}-final"
}

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${local.name}/database-url"
  description             = "SQLAlchemy URL for the app (Postgres on RDS)"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id = aws_secretsmanager_secret.database_url.id
  secret_string = format(
    "postgresql+psycopg://%s:%s@%s:%d/%s?sslmode=require",
    aws_db_instance.main.username,
    random_password.db.result,
    aws_db_instance.main.address,
    aws_db_instance.main.port,
    aws_db_instance.main.db_name,
  )
}
