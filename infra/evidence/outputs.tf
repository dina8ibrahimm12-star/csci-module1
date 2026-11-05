output "account_id" { value = local.account_id }
output "region" { value = var.region }
output "logs_bucket" { value = aws_s3_bucket.logs.id }
output "athena_workgroup" { value = aws_athena_workgroup.main.name }
output "glue_database" { value = aws_glue_catalog_database.logs.name }
