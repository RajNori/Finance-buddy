resource "random_password" "db" {
  length  = 32
  special = false # URL-safe; embedded in DATABASE_URL
}

resource "aws_db_subnet_group" "main" {
  name       = var.name
  subnet_ids = aws_subnet.data[*].id
}

resource "aws_db_parameter_group" "main" {
  name   = "${var.name}-pg17"
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
  identifier     = var.name
  engine         = "postgres"
  engine_version = "17"
  instance_class = var.db_instance_class

  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = 100
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_name
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
  skip_final_snapshot       = var.db_skip_final_snapshot
  final_snapshot_identifier = var.db_skip_final_snapshot ? null : "${var.name}-final-${formatdate("YYYYMMDDhhmm", timestamp())}"

  lifecycle {
    ignore_changes = [final_snapshot_identifier]
  }
}

# Lives and dies with the database, so no recovery window: a later spin-up
# must be able to recreate the same name immediately.
resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.name}/database-url"
  description             = "SQLAlchemy URL for the app (Postgres on RDS)"
  recovery_window_in_days = 0
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
