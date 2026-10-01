# Financebuddy on AWS

Production deployment: ECS Fargate behind an ALB with WAF, RDS Postgres, Secrets Manager, and keyless GitHub Actions deploys. Everything is Terraform; nothing is click-ops.

## Two modes

| Mode | What exists | Cost |
|---|---|---|
| **Dormant** (default, `runtime_enabled = false`) | ECR, OpenRouter secret, GitHub deploy role, SNS topic, budget, state bucket | ~US$0.70/month |
| **Running** (`runtime_enabled = true`) | Everything below: VPC, NAT, ALB, WAF, ECS, RDS, alarms | ~US$0.18/hour (~$134/month if left on) |

Pre-launch, keep it dormant and spin up for demos: `scripts/aws_up.sh`, then `scripts/aws_down.sh`. A 2-hour demo costs about $0.40. Spin-up takes ~20 minutes (RDS is the slow part); spin-down ~10. The database is deleted without a snapshot on spin-down and re-seeded on the next spin-up.

At launch, set `runtime_enabled = true`, `db_deletion_protection = true`, `db_skip_final_snapshot = false` and raise `monthly_budget_usd` in `terraform.tfvars`.

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

## First-time setup (~15 min, dormant)

Prereqs: AWS CLI v2 logged in as an admin, Terraform ≥ 1.10, `gh` CLI.

```bash
# 1. State bucket (once per account)
cd infra/bootstrap
terraform init && terraform apply
terraform output -raw backend_hcl > ../aws/backend.hcl

# 2. Dormant stack (~10 resources, ~$0.70/month)
cd ../aws
cp terraform.tfvars.example terraform.tfvars   # set alarm_email
terraform init -backend-config=backend.hcl
terraform plan -out=tfplan && terraform apply tfplan

# 3. OpenRouter key (never goes in Terraform)
aws secretsmanager put-secret-value \
  --secret-id "$(terraform output -raw openrouter_secret_id)" \
  --secret-string '<openrouter-key>'

# 4. Confirm the SNS subscription email AWS sends you.

# 5. GitHub: create environment "production" (add yourself as required reviewer), then:
gh variable set AWS_REGION          --body "$(terraform output -raw aws_region)"
gh variable set AWS_DEPLOY_ROLE_ARN --body "$(terraform output -raw github_deploy_role_arn)"
gh variable set ECR_REPOSITORY      --body "$(terraform output -raw ecr_repository)"
gh variable set RUNTIME_ENABLED     --body false
```

Commit `infra/aws/.terraform.lock.hcl` and `infra/bootstrap/.terraform.lock.hcl` after the first `init`.

## Spin up / down

```bash
scripts/aws_up.sh     # apply runtime (review the plan), set ECS_* + APP_URL vars, run Deploy
scripts/aws_down.sh   # RUNTIME_ENABLED=false, destroy runtime (review the plan)
```

While dormant, merges to `main` skip the Deploy workflow; a manual Deploy run only pushes the image to ECR. The deploy role loses its ECS permissions while dormant.

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

## Cost (approx., ap-southeast-2, excl. 10% GST)

**Dormant:** ECR (~2 GB, 10 images kept) $0.20 · OpenRouter secret $0.40 · S3 state $0.05 · SNS, budget, IAM free → **~$0.70/month**. Each running hour adds ~$0.18.

**Running, per month if left on:**

| Item | USD/month |
|---|---|
| NAT gateway (1) + data | ~44 |
| ALB + LCU | ~20 |
| Public IPv4 (3 addresses) | ~11 |
| Fargate 0.5 vCPU / 1GB | ~22 |
| RDS db.t4g.micro + 20GB gp3 | ~21 |
| WAF (ACL + 5 rules) | ~11 |
| CloudWatch, Container Insights, flow logs, DB URL secret | ~5 |
| **Total** | **~134** |

`single_nat_gateway = false` and `db_multi_az = true` add roughly $68 for AZ-failure tolerance.

## Phase 2 (when there's a reason)

1. **Scale out:** move the price feed to a single producer publishing to ElastiCache (Redis pub/sub) and the snapshot job to EventBridge Scheduler, then lift `desired_count` and add target-tracking autoscaling.
2. **IAM database auth** instead of a password in state.
3. **Terraform in CI:** read-only OIDC role for `plan` on PRs, approval-gated `apply`.
4. **Edge:** CloudFront in front of the ALB for static assets; WAF logging to S3.
5. **Multi-env:** `staging` via a second backend key and tfvars, same modules.
