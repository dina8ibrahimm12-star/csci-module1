# Read-only role used by src/discovery/discover.py (security requirement: read-only discovery)
data "aws_iam_policy_document" "discovery_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
  }
}

resource "aws_iam_role" "discovery" {
  name               = "${local.prefix}-discovery-readonly"
  assume_role_policy = data.aws_iam_policy_document.discovery_trust.json
}

data "aws_iam_policy_document" "discovery" {
  statement {
    actions = [
      "ec2:Describe*",
      "iam:Get*", "iam:List*",
      "s3:ListAllMyBuckets", "s3:GetBucketTagging", "s3:GetBucketPolicy",
      "s3:GetBucketPolicyStatus", "s3:GetBucketAcl", "s3:GetBucketLocation",
      "s3:GetBucketPublicAccessBlock", "s3:GetAccountPublicAccessBlock",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "discovery" {
  name   = "discovery-readonly"
  role   = aws_iam_role.discovery.id
  policy = data.aws_iam_policy_document.discovery.json
}
