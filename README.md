# proto2prod

**Turn a prototype web app into a production-ready AWS deployment, then keep its AWS bill in check.**

Two products on one engine:

- **Launch** – source code in, verified production-ready pull/merge request out (described below).
- **Cost Guardian** – always-on: alerts on cost spikes within minutes, finds waste daily, and fixes it through Terraform pull/merge requests. Priced on measured savings. See [DESIGN.md §12](docs/DESIGN.md#12-cost-guardian).

## Launch

proto2prod is a team of AI agents that reads your app's source code and delivers, as a pull request:

- a security and scalability **refactor** of the application,
- a **cost-efficient AWS architecture** sized to your traffic and budget,
- **Terraform** for all of it, built from tested modules,
- a full **CI/CD pipeline** (build, test, scan, plan, deploy),
- a plain-English **architecture summary** and **monthly cost estimate**.

Every piece of work is checked by independent reviewer agents and proven with a real deploy to a throwaway environment before you see it. Nothing reaches production without your approval.

## How it works

1. **Analyze** – an analyzer agent reads the repo and writes an *app profile* and a *shared contract* (names, ports, secrets) that every other agent must follow.
2. **Build in parallel** – four worker agents (refactor, architecture, Terraform, CI/CD) work at the same time, each on its own branch.
3. **Review** – security, cost, code and policy reviewers check the work. Failures go back to the worker that produced them.
4. **Prove** – the result is deployed to a throwaway AWS environment, smoke-tested, then torn down.
5. **Approve** – you get one pull request with the plan, the cost estimate and the evidence.

Works with **GitHub or GitLab**; the CI/CD pipeline reaches your AWS account through **OIDC**, so no AWS keys are ever stored.

- [How it works](docs/how-it-works.html) – the end-to-end journey in one page
- [Development plan](docs/development-plan.html) – milestones to the MVP
- [Full design](docs/DESIGN.md)

## Status

Early development. Works with any containerizable web app; the first deep-refactor adapter is Next.js + Postgres. Target platform: ECS Fargate + RDS on AWS. A sample prototype app for end-to-end testing lives in [examples/notes-app](examples/notes-app).
