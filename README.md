# Cloud Security Change Intelligence & Attack Path Platform
## Module 1: Cloud Lab & Data Collection

Everything owned by **Role 1**: the AWS lab (IaC), the logging foundation (CloudTrail, AWS Config,
VPC Flow Logs), the EventBridge -> SQS change feed, Athena queries, the discovery script and
the data contract for the rest of the team.

> **Nothing in this repository creates, changes or deletes AWS resources by itself.**
> No script runs `terraform apply` or `terraform destroy` for you, and no `-auto-approve` is used anywhere.
> Resources are created only when a person runs the commands in `docs/RUNBOOK.md`
> **after the team has reviewed the Terraform plan and the expected cost.**

## The AWS account
The team creates its own AWS account in the **new AWS experience** (AWS Builder ID + project): there is no
root user and no IAM console user, and AWS assigns the project's Region (here **eu-north-1**, which cannot
be changed). `docs/RUNBOOK.md` (Arabic, step by step, Ubuntu commands) covers: creating the account,
securing it with MFA in AWS Settings, inviting teammates, logging in from the CLI with `aws login`
(temporary credentials, **no long-term access keys**), cost protection, and the read-only checks to run
before building anything.
**Never put AWS keys, passwords or MFA codes in files, in GitHub or in chat.**

## Order of work (same numbering as the RUNBOOK)
0. Local checks, no AWS needed (`static_check.py`, offline test, `terraform validate`)
1. Create the AWS account (team decision: owner, Free vs Paid plan, Region eu-north-1 accepted by the instructor)
2. Secure it: MFA in AWS Settings, invite teammates (each uses their own login)
3. Log in: `aws login --profile csci`
4. Cost protection: budget before the first resource
5. Read-only pre-checks (existing CloudTrail, Config recorder, Config delivery channel)
6. `infra/evidence`: `plan` -> **team review** -> `apply` (log bucket, CloudTrail, Athena)
7. `infra/lab`: `plan` -> **team review of plan and cost** -> `apply` (lab, Config, Flow Logs, EventBridge -> SQS)
8. Verify: Config status, change event arrives in SQS, real S3 event names
9. Extract the snapshot file for Roles 3 and 4
10. Athena queries (optional)
11. Cleanup: `docs/CLEANUP.md` (export evidence first; destroy the lab only, with team approval)

## Layout
```
infra/evidence/   PERSISTENT: log bucket, CloudTrail, Athena. Never destroyed with the lab.
infra/lab/        DESTROYABLE lab: VPC, security group, IAM roles, fake-data S3 buckets,
                  Config recorder + delivery channel, Flow Logs, EventBridge -> SQS,
                  read-only discovery role. EC2 is OFF by default (create_web_server = false).
src/discovery/discover.py     read-only boto3 snapshot -> snapshots/*.json
src/tools/verify_pipeline.py  prints events arriving in the SQS queue
athena/           03_queries.sql (9 forensic queries); table DDL is generated into athena/generated/
scripts/          simulate_changes.sh (Bash) + simulate_changes.ps1 (Windows PowerShell),
                  static_check.py (offline sanity checks, needs no AWS)
tests/            test_discover_offline.py (fake AWS clients, needs no AWS)
samples/          sample snapshots with FAKE ids so other roles can start now
docs/             RUNBOOK, CLEANUP, log architecture, retention policy, audit-log inventory,
                  snapshot schema (the contract for Roles 3 and 4)
```

## Safe defaults
- Web server security group has **no inbound rules**. SSH to 0.0.0.0/0 only appears if someone runs scenario S1.
- Every S3 bucket has all four Block Public Access settings **on**. Scenario S3 turns it off on purpose.
- **No EC2** is created unless `create_web_server = true` in `infra/lab/terraform.tfvars`.
- CloudTrail, the Config recorder + delivery channel, Flow Logs and the budget each have an on/off
  variable, because AWS allows only one recorder and one delivery channel per region and the account
  may already have them.
- The log bucket lives in its own Terraform stack with `prevent_destroy`, so cleaning up the lab
  cannot delete report evidence.
- No credentials in any file. Terraform and Python read your AWS profile / environment only.
- CloudTrail is single-Region by default (`cloudtrail_multi_region = false`) because the new AWS experience does not support multi-Region features.

## Quick map for teammates
- Everyone: `docs/HANDOVER.md` (Arabic hand-over notes) and `docs/data-model.md` (the shared data contract).
- Roles 3 and 4: `docs/snapshot-schema.md` + `samples/`.
- Role 4/5 (Collector): queue URL = `terraform output queue_url` (stack `infra/lab`); messages are raw
  EventBridge events (`AWS API Call via CloudTrail` or `Config Configuration Item Change`).
- Role 2: GuardDuty, Security Hub and Config rules are not part of this module. **Note:** GuardDuty and Security Hub are not supported by default in the new AWS experience; the team must decide how to enable them.

## Before you push to GitHub
Run `git status` and make sure no `*.tfstate`, `terraform.tfvars`, `.terraform/`, `*.tfplan`,
`snapshots/*.json`, `athena/generated/*.sql`, `.env` or `.aws/` files are listed (`.gitignore` blocks them).
**Do** commit `.terraform.lock.hcl` (created by `terraform init`).
