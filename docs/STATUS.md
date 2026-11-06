# Status (Role 1) - updated Nov 5
- Account: AWS new experience, Free plan, Region eu-north-1 (fixed). Login: `aws login --remote --profile csci`; Terraform/Python use profile `csci-tf` (credential_process). Session lasts ~12h.
- infra/evidence APPLIED (11 resources). Never destroy. infra/lab APPLIED (34 resources incl. EC2 t3.micro web-server; currently STOPPED).
- S1, S2, S3 applied AND reverted; all verified closed (SG ingress [], AppRole only ReadCustomerData, bucket block 4x True, no bucket policy).
- Snapshots (local, git-ignored): baseline.json, after-s1.json (22 open), after-s2.json (TooBroad), after-s3.json (customer-data public).
- SQS change feed verified for S1 and S3 (CloudTrail + Config events). DLQ=0. IAM events (S2) do NOT arrive: not in eu-north-1 CloudTrail, not in Config, not in queue; they exist in us-east-1 CloudTrail (lookup-events --region us-east-1 works).
- Athena works: table csci_logs.cloudtrail_logs (partition column needs backticks in CREATE, double quotes in SELECT). Workgroup csci-wg.
- Real event shapes captured -> docs/data-model.md written. Hand-over notes -> docs/HANDOVER.md.
- DONE: pushed to GitHub (main), lock files committed. TODO: export evidence for report; send snapshots + queue URL privately to team; (team decision) start EC2 only when needed.
- Rules: no apply/destroy without team approval; no keys in files/GitHub; do not read SQS repeatedly (5 receives -> DLQ).
