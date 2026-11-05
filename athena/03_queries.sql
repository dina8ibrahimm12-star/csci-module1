-- Athena queries on CloudTrail (database: csci_logs, table: cloudtrail_logs)
-- Run athena/generated/01_*.sql and 02_*.sql first (created by terraform in infra/evidence).
-- Always filter on the partition column "date" (yyyy/MM/dd) to limit scan cost.
-- In SELECT use double quotes around "date"; in CREATE TABLE it needs backticks.

-- Q1. Security Group ingress changes: who / what / from where
SELECT eventtime, useridentity.arn AS actor, eventname, sourceipaddress, requestparameters
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01'
  AND eventname IN ('AuthorizeSecurityGroupIngress','RevokeSecurityGroupIngress','ModifySecurityGroupRules')
ORDER BY eventtime DESC;

-- Q2. Rules opened to the whole Internet (SSH/RDP/any)
SELECT eventtime, useridentity.arn AS actor, requestparameters
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01'
  AND eventname = 'AuthorizeSecurityGroupIngress'
  AND (requestparameters LIKE '%0.0.0.0/0%' OR requestparameters LIKE '%::/0%')
ORDER BY eventtime DESC;

-- Q3. IAM policy changes
SELECT eventtime, useridentity.arn AS actor, eventname, requestparameters
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01'
  AND eventsource = 'iam.amazonaws.com'
  AND eventname IN ('PutRolePolicy','AttachRolePolicy','DetachRolePolicy','CreatePolicy',
                    'CreatePolicyVersion','SetDefaultPolicyVersion','PutUserPolicy','AttachUserPolicy')
ORDER BY eventtime DESC;

-- Q4. S3 exposure-related changes
SELECT eventtime, useridentity.arn AS actor, eventname, requestparameters
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01'
  AND eventsource = 's3.amazonaws.com'
  AND eventname IN ('PutBucketPolicy','DeleteBucketPolicy','PutBucketAcl',
                    'PutBucketPublicAccessBlock','DeleteBucketPublicAccessBlock',
                    'PutPublicAccessBlock','DeletePublicAccessBlock',
                    'PutAccountPublicAccessBlock','DeleteAccountPublicAccessBlock')
ORDER BY eventtime DESC;

-- Q5. Failed API calls (AccessDenied etc.)
SELECT eventtime, useridentity.arn AS actor, eventname, errorcode, sourceipaddress
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01' AND errorcode IS NOT NULL
ORDER BY eventtime DESC
LIMIT 100;

-- Q6. Root account usage
SELECT eventtime, eventname, sourceipaddress, useragent
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01' AND useridentity.type = 'Root'
ORDER BY eventtime DESC;

-- Q7. Console logins
SELECT eventtime, useridentity.arn AS actor, sourceipaddress, responseelements
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01' AND eventname = 'ConsoleLogin'
ORDER BY eventtime DESC;

-- Q8. Full activity timeline of one actor (replace the ARN fragment)
SELECT eventtime, eventsource, eventname, sourceipaddress
FROM csci_logs.cloudtrail_logs
WHERE "date" >= '2026/10/01' AND useridentity.arn LIKE '%ahmed%'
ORDER BY eventtime;

-- Q9. Rejected traffic from VPC Flow Logs (needs 02_create_flowlogs_table.sql)
SELECT srcaddr, dstaddr, dstport, protocol, sum(packets) AS packets
FROM csci_logs.vpc_flow_logs
WHERE action = 'REJECT'
GROUP BY srcaddr, dstaddr, dstport, protocol
ORDER BY packets DESC
LIMIT 50;
