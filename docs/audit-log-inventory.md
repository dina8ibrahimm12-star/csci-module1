# Audit log inventory
| Source | Defined in | Content | Consumed by |
|---|---|---|---|
| CloudTrail (management events, all regions) | infra/evidence/main.tf (optional) | who called which API, when, from where | Athena, EventBridge, Role 4 |
| AWS Config (EC2 instance/SG/VPC/subnet, IAM role/policy, S3 bucket) | infra/lab/logging.tf (optional) | resource configuration + history | before/after diff |
| VPC Flow Logs (ALL) | infra/lab/logging.tf (optional) | accepted/rejected traffic | forensics |
| EventBridge rules (2) | infra/lab/events.tf | filtered change feed | SQS queue |
| GuardDuty / Security Hub | Role 2 | findings | correlation |
Known limits: S3 data events and CloudTrail Lake are not enabled (cost). IAM is a global service whose
API events are logged in us-east-1; with the project Region eu-north-1 the EventBridge rule and Config did
NOT see them (measured; see docs/data-model.md section 8). The default Region is eu-north-1 because AWS assigns it to the project. Event names for S3 Block Public Access are listed in several
spellings in `infra/lab/events.tf` and must be confirmed on the real account (RUNBOOK step 8).
