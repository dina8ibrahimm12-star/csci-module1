# Lab data buckets (fake data, safe to delete with the lab).
# The LOG bucket lives in infra/evidence and is NOT managed here.

resource "aws_s3_bucket" "customer_data" {
  bucket        = "${var.project}-customer-data-${local.account_id}"
  force_destroy = true
  tags = {
    Name        = "customer-data"
    Sensitivity = "high"
    DataClass   = "customer-data"
  }
}

resource "aws_s3_bucket" "app_assets" {
  bucket        = "${var.project}-app-assets-${local.account_id}"
  force_destroy = true
  tags = {
    Name        = "app-assets"
    Sensitivity = "low"
    DataClass   = "app-assets"
  }
}

resource "aws_s3_bucket_public_access_block" "customer_data" {
  bucket                  = aws_s3_bucket.customer_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "app_assets" {
  bucket                  = aws_s3_bucket.app_assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "customer_data" {
  bucket = aws_s3_bucket.customer_data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_assets" {
  bucket = aws_s3_bucket.app_assets.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_object" "sample_customers" {
  bucket       = aws_s3_bucket.customer_data.id
  key          = "customers.csv"
  content      = "id,name,email\n1,Test User,test@example.com\n2,Demo User,demo@example.com\n"
  content_type = "text/csv"
}
