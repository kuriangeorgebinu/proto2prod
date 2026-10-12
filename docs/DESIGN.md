# proto2prod – Design

proto2prod has two products that share one engine (analysis, Terraform generation, OIDC trust, merge requests, independent review):

- **Launch** (§1–11): turns a prototype's source code into a verified, production-ready AWS deployment. One-off, per app.
- **Cost Guardian** (§12): watches the AWS account after launch, catches cost spikes within minutes, and fixes waste through Terraform merge requests. Always on, recurring revenue.

Launch gets an app into AWS correctly; Guardian keeps it cost-efficient. A coding assistant run on demand can't do the second part: it has to be always on, remember each account's history, and act on live infrastructure.

## 1. Problem

AI app builders (Lovable, Bolt, Replit, Claude Code) produce working prototypes fast, but the step to production is where they fail:

- **Security:** disabled row-level security, hard-coded secrets, auth enforced only in the browser.
- **Scalability:** in-memory sessions, no connection pooling, no health checks, no migrations.
- **Infrastructure:** free-form AI-generated Terraform succeeds only ~20–30% of the time on the first try and often passes `terraform plan` while being insecure (wildcard IAM, public buckets, open SSH).

proto2prod's promise is **verified** production readiness: nothing ships until independent reviewers and a real test deploy say it works.

## 2. Goals and non-goals

**Goals (MVP)**
- Input: **any** containerizable web app in a GitHub repo. The first deep-refactor adapter is Next.js + Postgres; everything else uses the generic adapter (see §2a).
- Output: one pull request containing app refactors, Terraform, CI/CD, an architecture summary and a monthly cost estimate.
- Target architecture: ECS Fargate + RDS Postgres + ALB + CloudFront + Secrets Manager, in the user's own AWS account.
- Every change reviewed by agents that did not write it, then proven with a throwaway deploy.

**Non-goals (MVP)**
- Other clouds (GCP, Azure), Kubernetes, multi-region.
- Applying changes to production automatically.
- Operating the AWS console through a browser (see §7).

## 2a. Stack adapters

Most of the pipeline does not care what language the app is written in: once the app runs in a container, Terraform, CI/CD, cost, review and test deploy are the same. Only two things are stack-specific: **detecting** the stack and **refactoring** it. Those live in adapters.

| Part | Stack-specific? |
|---|---|
| Architecture, Terraform, CI/CD, reviewers, test deploy | No – works on the container |
| Detection, build commands, Dockerfile, refactor rules | Yes – one adapter per stack |

Each adapter implements: `detect(repo) -> confidence`, `profile(repo)`, `dockerfile(profile)`, `refactor_rules()`.

- **`nextjs`** (MVP): full detection, Dockerfile, and deep refactor.
- **`generic`** (MVP fallback): any app with a Dockerfile, or one the agent can write. Full infra, CI/CD and review; no deep refactor. The pull request states which refactor checks were skipped.
- Next adapters: FastAPI/Django, Express, Rails, Spring Boot.

## 3. Pipeline overview

```
Source repo
   │
   ▼
Analyzer agent ──► app-profile.yaml + contract.yaml
   │
   ├──► Refactor agent      (branch: p2p/refactor)
   ├──► Architecture agent  (branch: p2p/architecture)
   ├──► Terraform agent     (branch: p2p/terraform)   ← waits for architecture decision
   └──► CI/CD agent         (branch: p2p/cicd)
   │
   ▼
Integrator ──► merges branches, resolves conflicts against the contract
   │
   ▼
Reviewer agents (security, cost, code, policy) ──► rework loop (max 3 rounds)
   │
   ▼
Test deploy (throwaway AWS environment, smoke tests, teardown)
   │
   ▼
Pull request + evidence ──► user approval
```

Note: the Terraform agent depends on the architecture agent's decision record. In practice the architecture agent finishes first (it is fast: a sizing decision plus a cost estimate), then Terraform starts; refactor and CI/CD run fully in parallel throughout.

## 4. The shared contract

Parallel agents fail when they make conflicting assumptions (one names a secret `DB_URL`, another reads `DATABASE_URL`). The analyzer therefore writes two files before any worker starts. Workers may **read** them but never change them; a change request goes back through the orchestrator, which re-runs affected agents.

**`app-profile.yaml`** – facts about the app:
- framework and version, package manager, build and start commands
- services (web, workers, cron), ports
- database engine/version, ORM, migration tool
- environment variables found in code, which are secrets
- external services (Stripe, email, auth providers)
- traffic tier and monthly budget (chosen by the user)

**`contract.yaml`** – names every agent must use:
- container image name and tag scheme
- port, health-check path (`/api/health`), readiness path
- environment variable and secret names (mapping to Secrets Manager ARNs)
- AWS resource name prefix, tags, region
- environments (`staging`, `production`) and branch mapping

Schemas live in `schemas/` and are validated by every agent and reviewer.

## 5. Agents

| Agent | Input | Output | Key rules |
|---|---|---|---|
| **Analyzer** | repo | app profile, contract | Read-only. Flags anything it is unsure of instead of guessing. |
| **Refactor** | repo, contract | code changes | Secrets → env vars; health endpoint; stateless sessions; DB pooling; migrations; structured logs; server-side auth checks; enable row-level security. Must keep existing tests passing. |
| **Architecture** | profile | `architecture.md`, decision record, cost estimate | Picks the cheapest tier that meets the traffic tier. Explains every choice in plain English. |
| **Terraform** | decision record, contract | `infra/` | Composes **only** modules from `modules/` (tested library); no free-form resources except variables/wiring. Pinned provider versions. Remote state in S3 with locking. |
| **CI/CD** | profile, contract | `.github/workflows/` **or** `.gitlab-ci.yml` | Build → test → scan (deps, container, IaC) → `terraform plan` on PR/MR → deploy staging on merge → manual gate for production. Authenticates to AWS with OIDC (GitHub or GitLab); no long-lived keys. |
| **Integrator** | worker branches | merged branch | Resolves conflicts using the contract as the source of truth. |

### Architecture tiers (MVP)

| Tier | Traffic | Shape | Rough cost |
|---|---|---|---|
| Starter | < 10k req/day | App Runner + RDS `db.t4g.micro` | ~$30–50/mo |
| Standard | < 1M req/day | ECS Fargate (2 tasks, autoscale) + ALB + RDS `db.t4g.small` + CloudFront | ~$120–200/mo |
| Growth | > 1M req/day | Standard + RDS Multi-AZ + ElastiCache + autoscale 2–10 | ~$400+/mo |

Costs are computed at runtime with Infracost / the AWS Pricing API; the figures above are placeholders for planning.

## 6. Reviewers

Reviewers never see the worker's reasoning, only its output, so the work is not grading itself.

| Reviewer | Checks | Tools |
|---|---|---|
| **Security** | wildcard IAM, public buckets, open ports, unencrypted storage, secrets in code or state, missing RLS, client-only auth | Checkov, tfsec/Trivy, gitleaks, LLM review |
| **Cost** | estimate vs. user budget, oversized instances, missing autoscaling limits, NAT gateway surprises | Infracost, AWS Pricing API |
| **Code** | refactor kept behavior; tests, type-check and lint pass; no unrelated changes | project test suite, LLM diff review |
| **Policy** | every name matches `contract.yaml`; required tags present; provider versions pinned | schema validator, OPA/conftest |

**Rework loop:** each failure is returned to the worker that produced it as a structured finding (file, line, rule, why it matters, suggested fix). Max 3 rounds per worker; unresolved findings are listed in the pull request for the user to decide.

## 7. Security model

**No browser automation of the AWS console.** Customers will not hand an AI their console login, console clicks leave no reviewable record, and console layouts change often.

Instead:
1. **One-click bootstrap:** the user launches a small CloudFormation stack (`bootstrap/bootstrap.yaml`) in their account. GitHub/GitLab cannot create their own trust (they have no AWS access until it exists), so this one human click solves the chicken-and-egg problem. It creates:
   - an OIDC identity provider for `token.actions.githubusercontent.com` **or** the GitLab host (`https://gitlab.com` or a self-managed URL),
   - a `p2p-deploy` role trusted only by that project and its deploy branches, with scoped permissions,
   - an S3 bucket + DynamoDB table for Terraform state.

   Trust conditions (the security reviewer rejects wildcards that widen these):

   | Provider | `aud` | `sub` (StringLike) |
   |---|---|---|
   | GitHub | `sts.amazonaws.com` | `repo:<owner>/<repo>:ref:refs/heads/main` (+ `environment:production` for prod) |
   | GitLab | `https://gitlab.com` (or self-managed URL) | `project_path:<group>/<project>:ref_type:branch:ref:main` |

   Self-managed GitLab must be reachable from the internet so AWS can fetch its signing keys; a private-only instance is flagged by the analyzer.
2. **All further IAM is Terraform**, reviewed by the security reviewer and versioned in git.
3. **No long-lived AWS keys** are ever stored by proto2prod or in GitHub/GitLab CI variables.
4. **Agents never apply to production.** They open a pull/merge request; production deploys require a human approval (GitHub environment protection or a GitLab manual job on a protected environment).

## 8. Test deploy

1. Create an ephemeral environment named `p2p-test-<run-id>` from the merged Terraform, in the user's account (or our sandbox account for the free tier).
2. Build and push the container image; run database migrations.
3. Smoke tests: health endpoint, home page, one authenticated route, one database write/read.
4. Attach results (logs, timings, screenshots) to the pull request.
5. `terraform destroy` the environment, always, even on failure (enforced by a TTL tag and a cleanup job).

## 9. Repository layout

```
proto2prod/
├── docs/                 design and decision records
├── schemas/              app-profile and contract JSON schemas
├── src/proto2prod/
│   ├── orchestrator.py   plans the run, launches agents, enforces the contract
│   ├── contract.py       load/validate profile + contract
│   ├── agents/           analyzer, refactor, architecture, terraform, cicd, integrator
│   ├── reviewers/        security, cost, code, policy
│   └── deploy/           test-deploy runner
├── modules/              tested Terraform module library (network, ecs-service, rds, cdn, secrets)
├── bootstrap/            one-click CloudFormation bootstrap stack
└── examples/             sample prototype apps used for end-to-end tests
```

## 10. Tech choices

- **Language:** Python 3.12.
- **Agents:** Claude Agent SDK; each agent runs in its own sandboxed container on its own git branch.
- **Source/CI providers:** GitHub (GitHub App, pull request, Actions) and GitLab (GitLab app/token, merge request, GitLab CI). Chosen per project in `contract.yaml` → `ci`.
- **Infra tooling:** Terraform ≥ 1.8, AWS provider pinned, Checkov, Infracost, gitleaks.

## 11. Roadmap

1. **M1 – Skeleton:** contract schemas, orchestrator, analyzer agent producing a valid profile for the example app.
2. **M2 – Infra:** module library + Terraform agent + CI/CD agent for the Standard tier.
3. **M3 – Verification:** security/cost/policy reviewers, rework loop, test deploy.
4. **M4 – Refactor agent** and code reviewer.
5. **M5 – Product:** GitHub App, web dashboard, bootstrap stack, pricing.
6. **G1 – Guardian daily loop:** waste rules, savings estimates, fix merge requests (see §12).
7. **G2 – Guardian fast loop:** change and spike alerts within minutes.
8. **G3 – Guardian product:** savings verification, billing, dashboard.

## 12. Cost Guardian

### 12.1 Problem and buyer

Small teams spending roughly $2k–$50k/month on AWS rarely have someone watching the bill. Waste accumulates quietly (idle instances, oversized databases, forgotten snapshots, NAT gateway data charges) and mistakes are discovered at month end. Existing cost tools mostly *report* waste or manage savings commitments for larger companies; Guardian *fixes* it in the customer's own Terraform.

### 12.2 Why two loops

AWS billing data is not real time: Cost Explorer refreshes at least once a day and a day's costs can take about two days to finalise; billing exports (CUR 2.0) refresh at least daily. A bill-only watcher learns about a mistake a day or two late. Guardian therefore runs two loops:

| Loop | Cadence | Inputs | Purpose |
|---|---|---|---|
| **Fast** | Minutes | CloudTrail management events via EventBridge; CloudWatch metrics (NAT bytes, ASG size, Lambda/API request rates, data transfer) | Catch risky changes and spikes; estimate cost from list prices; alert and propose a fix |
| **Daily** | Once a day | Cost Explorer API; Data Exports (CUR 2.0) in the customer's S3 | Exact spend, slow waste, trends and forecasts; verify savings of past fixes |

The fast loop is approximate but quick ("a `p4d.24xlarge` started in us-east-1, ≈$32/h, not in Terraform"). The daily loop is exact and is the source of truth for verified savings and billing.

### 12.3 Access

Same bootstrap stack as Launch (§7), with an extra Guardian option:
- **Read role** for the Guardian service: Cost Explorer, CloudWatch, resource describe/list, read on the billing export bucket. No write permissions.
- **EventBridge rule** in the customer account forwarding selected CloudTrail events (resource create/modify, scaling changes) to Guardian's event bus.
- **No direct write access.** Every fix is a Terraform merge request that the customer's own pipeline applies through its OIDC deploy role.

### 12.4 Fix flow

1. A rule finds waste or a spike → a **finding** with evidence and estimated monthly saving.
2. The fix agent edits the customer's Terraform (resize, schedule non-prod, lifecycle policy, remove unused resource) and opens a merge request.
3. The reviewer agents check it (security, policy, blast radius) before the customer sees it.
4. Customers can enable **auto-merge per rule type** for low-risk fixes (e.g. S3 lifecycle rules, scheduling non-prod). Deletions and production resizing always need a human.
5. Resources created outside Terraform ("ClickOps") cannot be fixed by merge request; Guardian alerts and offers a Terraform import instead.
6. The daily loop measures actual spend before/after and records **verified savings** per fix.

### 12.5 Initial rule set (daily loop)

Idle EC2/RDS (low CPU and connections for 14 days) · oversized instances · unattached EBS volumes and old snapshots · idle load balancers and unused Elastic IPs · NAT gateway traffic that a VPC endpoint would avoid · S3 buckets without lifecycle rules · CloudWatch log groups with no retention · previous-generation instance types · savings plan / reserved-capacity coverage gaps.

### 12.6 Pricing

A share of **verified** savings (≈20–30%), with a small monthly minimum. Customers only pay for savings the daily loop has measured.

### 12.7 Code layout

```
src/proto2prod/guardian/
├── rules/          waste and spike rules (same Finding model as scanners.py)
├── daily.py        Cost Explorer + Data Exports ingestion, rule run, savings verification
├── fast.py         EventBridge event handler, list-price estimator, alerts
├── pricing.py      AWS Price List API lookups with caching
└── fixes.py        Terraform edits + merge request via the shared delivery layer
```
