# Log architecture
```mermaid
flowchart LR
  subgraph EV[infra/evidence - persistent]
    CT[CloudTrail multi-region trail] --> S3[(S3 logs bucket<br/>versioned, encrypted, retention)]
    S3 --> ATH[Athena + Glue]
  end
  subgraph LAB[infra/lab - destroyable]
    A[API calls in lab account] --> CT
    CFG[AWS Config recorder] --> S3
    FL[VPC Flow Logs] --> S3
    CT -. management events .-> EB[EventBridge rules]
    CFG --> EB
    EB --> SQS[SQS change-events queue] --> DLQ[(Dead-letter queue)]
  end
  SQS --> COL[Collector / Normalizer - Role 4/5]
```
Single lab account in the Region AWS assigned to the project (eu-north-1 here). A single-Region CloudTrail trail is used because the new AWS experience does not support multi-Region features. The log bucket, CloudTrail and Athena live in a separate Terraform stack so that
destroying the lab never deletes report evidence. Config records 7 resource types only (cost control).
Failed queue processing goes to a DLQ after 5 attempts.
