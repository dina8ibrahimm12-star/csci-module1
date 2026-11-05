# EventBridge -> SQS change feed (consumed by the Collector module).
#
# KNOWN LIMIT (new AWS experience, Region eu-north-1): IAM is a global service and its
# API calls are logged in us-east-1, so this rule may NOT see IAM events such as
# PutRolePolicy (scenario S2). Cross-Region rules are not supported there. Test it on the
# account (docs/RUNBOOK.md step 8); fall back to CloudTrail/Athena or Config if absent.
#
# eventName values must match what CloudTrail records. S3 Block Public Access
# names are listed in several spellings because sources differ between the bucket
# API name (DeletePublicAccessBlock) and the older names; unknown names are harmless.
# Verify on the real account (docs/RUNBOOK.md step 8, "Check the real event names").

locals {
  watched_api_events = [
    # EC2 / Security Groups
    "AuthorizeSecurityGroupIngress", "RevokeSecurityGroupIngress",
    "AuthorizeSecurityGroupEgress", "RevokeSecurityGroupEgress",
    "ModifySecurityGroupRules", "UpdateSecurityGroupRuleDescriptionsIngress",
    "CreateSecurityGroup", "DeleteSecurityGroup",
    "RunInstances", "ModifyInstanceAttribute", "ModifyNetworkInterfaceAttribute",
    "AssociateIamInstanceProfile", "ReplaceIamInstanceProfileAssociation",
    # IAM
    "PutRolePolicy", "DeleteRolePolicy", "AttachRolePolicy", "DetachRolePolicy",
    "CreatePolicy", "CreatePolicyVersion", "SetDefaultPolicyVersion",
    "UpdateAssumeRolePolicy", "PutUserPolicy", "AttachUserPolicy",
    # S3 - bucket policy / ACL
    "PutBucketPolicy", "DeleteBucketPolicy", "PutBucketAcl",
    # S3 - Block Public Access (bucket level)
    "PutBucketPublicAccessBlock", "DeleteBucketPublicAccessBlock",
    "PutPublicAccessBlock", "DeletePublicAccessBlock",
    # S3 - Block Public Access (account level)
    "PutAccountPublicAccessBlock", "DeleteAccountPublicAccessBlock",
  ]
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${local.prefix}-change-events-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "changes" {
  name                       = "${local.prefix}-change-events"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 10
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_cloudwatch_event_rule" "api_calls" {
  name        = "${local.prefix}-risky-api-calls"
  description = "Security-relevant CloudTrail API calls"
  event_pattern = jsonencode({
    source        = ["aws.ec2", "aws.iam", "aws.s3"]
    "detail-type" = ["AWS API Call via CloudTrail"]
    detail        = { eventName = local.watched_api_events }
  })
}

resource "aws_cloudwatch_event_rule" "config_changes" {
  name        = "${local.prefix}-config-changes"
  description = "AWS Config configuration item changes"
  event_pattern = jsonencode({
    source        = ["aws.config"]
    "detail-type" = ["Config Configuration Item Change"]
  })
}

resource "aws_cloudwatch_event_target" "api_calls" {
  rule = aws_cloudwatch_event_rule.api_calls.name
  arn  = aws_sqs_queue.changes.arn
}

resource "aws_cloudwatch_event_target" "config_changes" {
  rule = aws_cloudwatch_event_rule.config_changes.name
  arn  = aws_sqs_queue.changes.arn
}

data "aws_iam_policy_document" "queue" {
  statement {
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.changes.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values = [
        aws_cloudwatch_event_rule.api_calls.arn,
        aws_cloudwatch_event_rule.config_changes.arn,
      ]
    }
  }
}

resource "aws_sqs_queue_policy" "changes" {
  queue_url = aws_sqs_queue.changes.id
  policy    = data.aws_iam_policy_document.queue.json
}
