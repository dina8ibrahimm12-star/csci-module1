# Shared data model (v1.0)

Contract between the modules: **Collector** (Role 4/5) turns raw AWS events into `ChangeEvent`;
**Classifier** (Role 2) sets `change_type`; **Security Graph** (Role 3) builds `AttackPath` from snapshots;
**Correlation & Risk** (Role 4) produces `Incident`. The raw shapes below were taken from real events
captured in the lab account (Region eu-north-1), not guessed.

## 1. Data sources

| Source | Where it comes from | Reaches us how |
|---|---|---|
| CloudTrail API call | who called which API | EventBridge -> SQS queue (`detail-type` = `AWS API Call via CloudTrail`) |
| AWS Config item change | new configuration of a resource | EventBridge -> SQS queue (`detail-type` = `Config Configuration Item Change`) |
| Snapshot | full state from `discover.py` | JSON file (`docs/snapshot-schema.md`) |
| CloudTrail history | all API calls incl. IAM | Athena table `csci_logs.cloudtrail_logs`, or `lookup-events` |

## 2. Raw event shapes (observed)

Top level (both kinds): `version, id, detail-type, source, account, time, region, resources[], detail{}`.

**CloudTrail** (`source` = `aws.ec2` / `aws.iam` / `aws.s3`), under `detail`:
`eventVersion, userIdentity{type, principalId, arn, accountId, accessKeyId, sessionContext{sessionIssuer{type,principalId,arn,accountId,userName}, attributes{creationDate, mfaAuthenticated}, signInSessionArn}, onBehalfOf{...}}, eventTime, eventSource, eventName, awsRegion, sourceIPAddress, userAgent, requestParameters{...}, responseElements{...}, requestID, eventID, readOnly, eventType, managementEvent, recipientAccountId, eventCategory, tlsDetails{...}`.
`errorCode` / `errorMessage` appear only on failed calls (standard CloudTrail fields; not present in the successful sample).
For `AuthorizeSecurityGroupIngress`: `requestParameters.groupId` and `requestParameters.ipPermissions.items[]` (protocol, ports, `ipRanges.items[].cidrIp`: standard CloudTrail layout, verify on a real event); `responseElements.securityGroupRuleSet.items[]`.

**Config** (`source` = `aws.config`), under `detail`:
`recordVersion, messageType, notificationCreationTime, configurationItemDiff{changeType, changedProperties{...}}, configurationItem{resourceType, resourceId, resourceName, ARN, awsAccountId, awsRegion, availabilityZone, configurationItemStatus, configurationItemCaptureTime, configurationStateId (number), configurationStateMd5Hash, configuration{...type specific...}, tags{...}, relationships[], relatedEvents[]}`.
For a security group, `configuration` has `groupId, groupName, vpcId, ownerId, description, ipPermissions[], ipPermissionsEgress[], tags[]`.

## 3. `ChangeEvent` (normalized, produced by the Collector)

```json
{
  "schema_version": "1.0",
  "event_id": "CloudTrail detail.eventID | Config top-level id",
  "source": "cloudtrail | config | snapshot_diff | cloudtrail_lookup",
  "event_time": "2026-11-01T21:35:49Z",
  "account_id": "123456789012",
  "region": "eu-north-1",
  "actor": {"type": "AssumedRole", "arn": "...", "principal_id": "...", "source_ip": "...", "user_agent": "...", "mfa": false},
  "action": {"name": "AuthorizeSecurityGroupIngress", "service": "ec2.amazonaws.com", "read_only": false},
  "resource": {"type": "security_group", "id": "sg-0abc", "arn": null, "name": "csci-web-sg", "tags": {}},
  "request": {},
  "outcome": {"success": true, "error_code": null, "error_message": null},
  "change_type": "UNCLASSIFIED",
  "raw": {"queue_message_id": "...", "s3_key": null}
}
```

| ChangeEvent field | CloudTrail path | Config path |
|---|---|---|
| `event_id` | `detail.eventID` | `id` |
| `event_time` | `detail.eventTime` | `detail.configurationItem.configurationItemCaptureTime` |
| `account_id` / `region` | `detail.recipientAccountId` / `detail.awsRegion` | `detail.configurationItem.awsAccountId` / `awsRegion` |
| `actor.*` | `detail.userIdentity.*`, `detail.sourceIPAddress`, `detail.userAgent`, `...sessionContext.attributes.mfaAuthenticated` | not available (Config does not say who) |
| `action.name` | `detail.eventName` | `detail.messageType` + `configurationItemDiff.changeType` |
| `resource.id` | from `requestParameters` (e.g. `groupId`, `roleName`, `bucketName`) | `detail.configurationItem.resourceId` |
| `resource.type` | from `eventSource` + `eventName` | `detail.configurationItem.resourceType` (`AWS::EC2::SecurityGroup` -> `security_group`) |
| `outcome` | `detail.errorCode` present => failed | `success: true` |

Rules for the Collector:
- **De-duplicate on `event_id`**: SQS delivers at least once.
- **Ignore or down-rank failed calls** (`outcome.success = false`). CloudTrail records them and EventBridge forwards them (we saw a failed `RevokeSecurityGroupIngress`).
- Delete the SQS message only after the event is stored. After 5 failed receives the queue moves the message to the DLQ (`csci-change-events-dlq`).
- Store the raw event next to the normalized one (for forensics / chain of custody).

## 4. `change_type` (Classifier, Role 2)

| change_type | Trigger (event names observed in the lab) | Extra condition |
|---|---|---|
| `SG_ADMIN_PORT_OPEN_WORLD` | `AuthorizeSecurityGroupIngress`, `ModifySecurityGroupRules` | a rule with `0.0.0.0/0` or `::/0` on tcp/22, tcp/3389 (or all ports) |
| `IAM_POLICY_WIDENED` | `PutRolePolicy`, `AttachRolePolicy`, `CreatePolicyVersion`, ... | policy document grants `*` / `s3:*` on `*` |
| `S3_PUBLIC_EXPOSURE` | `DeleteBucketPublicAccessBlock`, `PutBucketPublicAccessBlock`, `PutBucketPolicy`, `PutBucketAcl` | block removed, or policy/ACL grants `Principal: *` |
| `UNCLASSIFIED` | anything else | |

Confirmed real names for S3: `DeleteBucketPublicAccessBlock`, `PutBucketPublicAccessBlock`, `PutBucketPolicy`, `DeleteBucketPolicy`.
Revert events (`RevokeSecurityGroupIngress`, `DeleteRolePolicy`, ...) should be recorded as `*_CLOSED` / `*_REVERTED` so incidents can be closed.

## 5. `Finding` (Role 2)

```json
{"finding_id": "...", "source": "config_rule | guardduty | securityhub | classifier",
 "title": "...", "severity": "LOW|MEDIUM|HIGH|CRITICAL", "resource_id": "...",
 "first_seen": "...", "mitre_technique": "T1190", "raw_ref": "..."}
```
Note: GuardDuty and Security Hub are not supported by default in the new AWS experience account
(see HANDOVER.md). Findings can come from the classifier and from AWS Config rules.

## 6. `AttackPath` (Role 3)

Nodes: `internet`, `ec2` (instance), `security_group`, `iam_role`, `s3_bucket`.
Edges (with the reason that created them):
`internet -> ec2` (running, public IP, subnet has internet route, SG ingress open to `0.0.0.0/0`),
`ec2 -> iam_role` (instance profile), `iam_role -> s3_bucket` (policy allows the action on the bucket).

```json
{"path_id": "internet>i-0abc>AppRole>customer-data", "snapshot_id": "...",
 "nodes": [{"type":"internet"},{"type":"ec2","id":"i-0abc"},{"type":"iam_role","id":"AppRole"},{"type":"s3_bucket","id":"csci-customer-data-<acct>","sensitivity":"high"}],
 "edges": [{"from":"internet","to":"i-0abc","why":"sg-0web tcp/22 from 0.0.0.0/0"},
           {"from":"i-0abc","to":"AppRole","why":"instance profile"},
           {"from":"AppRole","to":"csci-customer-data-<acct>","why":"s3:GetObject, s3:ListBucket"}]}
```
**Delta** = paths(after snapshot) minus paths(before snapshot) -> `new_paths`; the reverse -> `closed_paths`.
Test data: `snapshots/baseline.json` (no path), `after-s1.json` (new path), `after-s2.json` (stronger role),
`after-s3.json` (bucket public: direct `internet -> s3_bucket`). Samples with fake ids: `samples/`.

## 7. `Incident` (Role 4)

```json
{"incident_id": "INC-0001", "status": "open|mitigated|closed",
 "root_change_event_id": "...", "related_event_ids": ["..."],
 "timeline": [{"time":"...","what":"..."}],
 "snapshot_before": "...", "snapshot_after": "...",
 "new_paths": [], "closed_paths": [],
 "risk": {"score": 70, "level": "HIGH",
          "exposure": 40, "privilege": 10, "data_sensitivity": 20, "environment": 0,
          "explanation": "SSH is open to the Internet on a server whose role can read a high-sensitivity bucket."},
 "recommended_fix": "Revoke tcp/22 from 0.0.0.0/0 on sg-0web",
 "fix_verified": false}
```
Score = Exposure (0-40) + Privilege (0-30) + Data sensitivity from tags (0-20) + Environment (0-10).
Levels: Critical >= 90, High 70-89, Medium 40-69, Low < 40. The numbers in the example are illustrative; Role 4 owns the rubric.
Data sensitivity comes from the bucket tag `Sensitivity` (`high` / `medium` / `low`).

## 8. Known limits of this account (measured, not assumed)

- **IAM changes do not arrive in the queue.** IAM is a global service logged in `us-east-1`; with the
  project Region `eu-north-1` neither the EventBridge rule nor AWS Config saw `PutRolePolicy`.
  Detect them with (a) snapshot comparison, or (b) CloudTrail history in us-east-1:
  `aws cloudtrail lookup-events --region us-east-1 --lookup-attributes AttributeKey=EventName,AttributeValue=PutRolePolicy`.
- Events that happened before the EventBridge rule existed (Terraform provisioning) are in Athena but not in the queue.
- Routine read calls (`Get*`) appear in CloudTrail history roughly every 12 hours from the account itself; the rule does not forward them.
- CloudTrail history in Athena lags by about 5-15 minutes; the queue is faster (minutes).
- The Region cannot be changed (new AWS experience); a single-Region trail is used.
