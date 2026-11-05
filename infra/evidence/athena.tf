resource "aws_glue_catalog_database" "logs" {
  name = "${var.project}_logs"
}

resource "aws_athena_workgroup" "main" {
  name          = "${var.project}-wg"
  force_destroy = true
  configuration {
    enforce_workgroup_configuration = true
    result_configuration {
      output_location = "s3://${aws_s3_bucket.logs.id}/athena-results/"
    }
  }
}

# Ready-to-run DDL with the real bucket / account id filled in.
# Written to athena/generated/ (git-ignored: it contains your account id).
resource "local_file" "cloudtrail_table" {
  filename = "${path.module}/../../athena/generated/01_create_cloudtrail_table.sql"
  content = templatefile("${path.module}/templates/cloudtrail_table.sql.tftpl", {
    database   = aws_glue_catalog_database.logs.name
    bucket     = aws_s3_bucket.logs.id
    account_id = local.account_id
    date_start = var.athena_date_start
    regions    = join(",", distinct([var.region, "us-east-1"]))
  })
}

resource "local_file" "flowlogs_table" {
  filename = "${path.module}/../../athena/generated/02_create_flowlogs_table.sql"
  content = templatefile("${path.module}/templates/flowlogs_table.sql.tftpl", {
    database   = aws_glue_catalog_database.logs.name
    bucket     = aws_s3_bucket.logs.id
    account_id = local.account_id
  })
}
