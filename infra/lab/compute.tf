data "aws_ssm_parameter" "al2023" {
  count = var.create_web_server ? 1 : 0
  name  = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

# "AppRole" from the proposal figures: can read the customer-data bucket.
resource "aws_iam_role" "app" {
  name               = "AppRole"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

data "aws_iam_policy_document" "app_s3" {
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.customer_data.arn}/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.customer_data.arn]
  }
}

resource "aws_iam_role_policy" "app_s3" {
  name   = "ReadCustomerData"
  role   = aws_iam_role.app.id
  policy = data.aws_iam_policy_document.app_s3.json
}

resource "aws_iam_instance_profile" "app" {
  name = "${local.prefix}-app-profile"
  role = aws_iam_role.app.name
}

# OFF by default (var.create_web_server = false).
resource "aws_instance" "web" {
  count                  = var.create_web_server ? 1 : 0
  ami                    = data.aws_ssm_parameter.al2023[0].value
  instance_type          = "t3.micro"
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.web.id]
  iam_instance_profile   = aws_iam_instance_profile.app.name

  metadata_options { http_tokens = "required" }
  root_block_device { encrypted = true }

  tags = { Name = "web-server", Role = "web" }
}
