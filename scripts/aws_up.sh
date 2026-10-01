#!/usr/bin/env bash
# Spin up the billable AWS runtime (~US$0.18/hour) and deploy main.
# Requires: terraform, gh (authenticated), AWS credentials. Review the plan before approving.
set -euo pipefail
cd "$(dirname "$0")/../infra/aws"

terraform apply -var runtime_enabled=true

for pair in ecs_cluster:ECS_CLUSTER ecs_service:ECS_SERVICE ecs_task_family:ECS_TASK_FAMILY app_url:APP_URL; do
  gh variable set "${pair#*:}" --body "$(terraform output -raw "${pair%%:*}")"
done
gh variable set RUNTIME_ENABLED --body true
gh workflow run Deploy

echo "Deploy started (approve it in GitHub if the environment requires review)."
echo "App: $(terraform output -raw app_url)"
echo "Billing ~US\$0.18/hour until you run scripts/aws_down.sh"
