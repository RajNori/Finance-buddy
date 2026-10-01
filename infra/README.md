# Financebuddy on AWS

Production deployment: ECS Fargate behind an ALB with WAF, RDS Postgres, Secrets Manager, and keyless GitHub Actions deploys. Everything is Terraform; nothing is click-ops.

## Architecture

```
                 Internet
                    │
          ┌─────────▼──────────┐
          │  WAF (rate limits, │   /api/chat capped per IP (LLM spend)
          │  AWS managed rules)│
          └─────────┬──────────┘
          ┌─────────▼──────────┐
 public   │  ALB  :443 (ACM)   │   :80 → 301 to HTTPS when a domain is set
 subnets  └─────────┬──────────┘   idle timeout 120s (SSE)
                    │ :8000
          ┌─────────▼──────────┐
 app      │ ECS Fargate task   │──► NAT ──► OpenRouter / Massive / ECR
 subnets  │ FastAPI + static UI│
          │ simulator in-proc  │   1 task, rolling deploy, circuit-breaker rollback
          └─────────┬──────────┘
                    │ :5432 (TLS enforced)
          ┌─────────▼──────────┐
 data     │ RDS Postgres 17    │   encrypted, 7-day backups, no internet route
 subnets  └────────────────────┘

 GitHub Actions ──OIDC──► IAM deploy role ──► ECR push ──► ECS update-service
```

Region `ap-southeast-2` (Sydney), two AZs.

## Key decisions

| Decision | Why |
|---|---|
| ECS Fargate over App Runner/EKS | Supports long-lived SSE and VPC-private networking; no cluster to run. EKS is overkill for one service. |
| RDS Postgres over SQLite | Fargate has no durable local disk. The app reads `DATABASE_URL`, so local dev keeps SQLite unchanged. |
| One task (`desired_count = 1`) | The simulator and snapshot job run in-process; two tasks would serve different prices. Availability comes from fast replacement (health checks + rolling deploy), not replicas. |
| WAF with a `/api/chat` rate limit | No auth + paid LLM calls = cost-abuse risk. Also set a credit limit on the OpenRouter key. |
| GitHub OIDC, environment-scoped | No long-lived AWS keys in GitHub. Only jobs in the `production` environment can assume the role. |
| Secrets set out-of-band | API keys never enter Terraform state. The DB password does (random, in encrypted S3 state); move to IAM DB auth in phase 2. |
| CI owns the image, Terraform owns everything else | Service ignores `task_definition` drift; deploys register new revisions from the latest one. |

## First-time setup (~45 min)

Prereqs: AWS CLI v2 logged in as an admin, Terraform ≥ 1.10.

```bash
# 1. State bucket (once per account)
cd infra/bootstrap
terraform init && terraform apply
terraform output -raw backend_hcl > ../aws/backend.hcl

# 2. Main stack
cd ../aws
cp terraform.tfvars.example terraform.tfvars   # set alarm_email (+ domain if you have one)
terraform init -backend-config=backend.hcl
terraform apply                                  # ~15 min, RDS is the slow part

# 3. Secrets (values never go in Terraform)
aws secretsmanager put-secret-value \
  --secret-id "$(terraform output -raw openrouter_secret_id)" \
  --secret-string '<openrouter-key>'

# 4. Confirm the SNS subscription email AWS sends you.
```

The ECS service will fail to start until step 5 pushes the first image. That's expected.

```bash
# 5. GitHub: create environment "production" (add yourself as required reviewer),
#    then set repository variables from Terraform outputs:
gh variable set AWS_REGION          --body "$(terraform output -raw aws_region)"
gh variable set AWS_DEPLOY_ROLE_ARN --body "$(terraform output -raw github_deploy_role_arn)"
gh variable set ECR_REPOSITORY      --body "$(terraform output -raw ecr_repository)"
gh variable set ECS_CLUSTER         --body "$(terraform output -raw ecs_cluster)"
gh variable set ECS_SERVICE         --body "$(terraform output -raw ecs_service)"
gh variable set ECS_TASK_FAMILY     --body "$(terraform output -raw ecs_task_family)"
gh variable set APP_URL             --body "$(terraform output -raw app_url)"

# 6. Deploy
gh workflow run Deploy
```

Commit `infra/aws/.terraform.lock.hcl` and `infra/bootstrap/.terraform.lock.hcl` after the first `init`.

## Day-2 operations

| Task | How |
|---|---|
| Deploy | Merge to `main` → CI passes → Deploy workflow (approval-gated) |
| Roll back | Re-run Deploy for an older commit, or `aws ecs update-service --task-definition <family>:<rev>` |
| Change env vars / CPU / memory | Edit Terraform, `apply`, then run Deploy so the service picks up the new revision |
| Rotate a secret | `put-secret-value`, then `aws ecs update-service --force-new-deployment` |
| Shell into the container | `aws ecs execute-command --cluster <c> --task <id> --container app --interactive --command sh` |
| Logs | CloudWatch `/ecs/financebuddy-prod`, or `aws logs tail /ecs/financebuddy-prod --follow` |
| Restore DB | RDS point-in-time restore (7 days) to a new instance, swap `DATABASE_URL` |

Alarms (email via SNS): no running tasks, unhealthy targets, 5xx spike, DB CPU, DB storage, and a monthly budget at 80% forecast / 100% actual.

## Cost (approx., ap-southeast-2, light traffic)

| Item | USD/month |
|---|---|
| NAT gateway (1) | ~35 |
| ALB | ~20 |
| RDS db.t4g.micro + 20GB | ~20 |
| Fargate 0.5 vCPU / 1GB, 24/7 | ~20 |
| WAF (ACL + 5 rules) | ~10 |
| CloudWatch, Secrets, ECR, Container Insights | ~10 |
| **Total** | **~115** |

`single_nat_gateway = false` and `db_multi_az = true` add roughly $55 for AZ-failure tolerance.

## Phase 2 (when there's a reason)

1. **Scale out:** move the price feed to a single producer publishing to ElastiCache (Redis pub/sub) and the snapshot job to EventBridge Scheduler, then lift `desired_count` and add target-tracking autoscaling.
2. **IAM database auth** instead of a password in state.
3. **Terraform in CI:** read-only OIDC role for `plan` on PRs, approval-gated `apply`.
4. **Edge:** CloudFront in front of the ALB for static assets; WAF logging to S3.
5. **Multi-env:** `staging` via a second backend key and tfvars, same modules.
