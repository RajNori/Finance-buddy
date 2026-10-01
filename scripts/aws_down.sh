#!/usr/bin/env bash
# Tear down the billable AWS runtime. Keeps ECR, secrets, deploy role and budget (~US$0.70/month).
# Pre-launch, the database is deleted without a snapshot; it is re-seeded on the next spin-up.
set -euo pipefail
cd "$(dirname "$0")/../infra/aws"

gh variable set RUNTIME_ENABLED --body false
terraform apply -var runtime_enabled=false
