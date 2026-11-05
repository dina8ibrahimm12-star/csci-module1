# Retention policy
| Log | Location | Retention | Why |
|---|---|---|---|
| CloudTrail | s3://csci-logs-<acct>/AWSLogs/<acct>/CloudTrail/ | 365 days (variable `log_retention_days`) | covers project, demo, report |
| AWS Config | .../Config/ | 365 days | configuration history for before/after |
| VPC Flow Logs | .../vpcflowlogs/ | 365 days | network evidence |
| Athena results | .../athena-results/ | 365 days | query output |
| SQS change events | queue (lab stack) | 4 days; DLQ 14 days | ingestion retry only |

The log bucket is versioned, encrypted (SSE-S3), blocks all public access, denies non-TLS access,
and is protected from `terraform destroy` (`prevent_destroy`). CloudTrail log-file validation is on
(supports chain of custody). Production would add Object Lock and cross-account log archiving.
