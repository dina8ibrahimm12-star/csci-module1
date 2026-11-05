# Config recorder + VPC Flow Logs for the lab.
# They deliver into the persistent log bucket from infra/evidence.
# CloudTrail lives in infra/evidence as well.

data "aws_s3_bucket" "logs" {
  bucket = var.logs_bucket_name # fails at plan time if the evidence stack is not applied
}

# ---------- AWS Config ----------
# AWS allows ONE configuration recorder AND ONE delivery channel per region.
# create_config_recorder = false skips all of them (use it if the account already has Config set up).
data "aws_iam_policy_document" "config_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["config.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "config" {
  count              = var.create_config_recorder ? 1 : 0
  name               = "${local.prefix}-config-role"
  assume_role_policy = data.aws_iam_policy_document.config_assume.json
}

resource "aws_iam_role_policy_attachment" "config" {
  count      = var.create_config_recorder ? 1 : 0
  role       = aws_iam_role.config[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

data "aws_iam_policy_document" "config_s3" {
  statement {
    actions   = ["s3:PutObject", "s3:PutObjectAcl"]
    resources = ["${data.aws_s3_bucket.logs.arn}/AWSLogs/${local.account_id}/Config/*"]
  }
  statement {
    actions   = ["s3:GetBucketAcl"]
    resources = [data.aws_s3_bucket.logs.arn]
  }
}

resource "aws_iam_role_policy" "config_s3" {
  count  = var.create_config_recorder ? 1 : 0
  name   = "config-deliver-to-logs"
  role   = aws_iam_role.config[0].id
  policy = data.aws_iam_policy_document.config_s3.json
}

# Limited resource types to control cost
resource "aws_config_configuration_recorder" "main" {
  count    = var.create_config_recorder ? 1 : 0
  name     = "${local.prefix}-recorder"
  role_arn = aws_iam_role.config[0].arn
  recording_group {
    all_supported = false
    resource_types = [
      "AWS::EC2::Instance",
      "AWS::EC2::SecurityGroup",
      "AWS::EC2::VPC",
      "AWS::EC2::Subnet",
      "AWS::IAM::Role",
      "AWS::IAM::Policy",
      "AWS::S3::Bucket",
    ]
  }
}

resource "aws_config_delivery_channel" "main" {
  count          = var.create_config_recorder ? 1 : 0
  name           = "${local.prefix}-delivery"
  s3_bucket_name = data.aws_s3_bucket.logs.id
  depends_on     = [aws_config_configuration_recorder.main, aws_iam_role_policy.config_s3]
}

resource "aws_config_configuration_recorder_status" "main" {
  count      = var.create_config_recorder ? 1 : 0
  name       = aws_config_configuration_recorder.main[0].name
  is_enabled = true
  # The recorder may only start after the delivery channel exists AND the role
  # has both its managed policy and the S3 delivery policy.
  depends_on = [
    aws_config_delivery_channel.main,
    aws_iam_role_policy_attachment.config,
    aws_iam_role_policy.config_s3,
  ]
}

# ---------- VPC Flow Logs ----------
resource "aws_flow_log" "vpc" {
  count                = var.create_flow_logs ? 1 : 0
  vpc_id               = aws_vpc.lab.id
  traffic_type         = "ALL"
  log_destination_type = "s3"
  log_destination      = data.aws_s3_bucket.logs.arn
}
