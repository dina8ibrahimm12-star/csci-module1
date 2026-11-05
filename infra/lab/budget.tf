# Optional. Off by default so no email address is hard-coded. You can instead create
# the budget in the console (RUNBOOK step 4). Enable here with create_budget = true + alert_email.
resource "aws_budgets_budget" "monthly" {
  count        = var.create_budget ? 1 : 0
  name         = "${local.prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }

  lifecycle {
    precondition {
      condition     = var.alert_email != ""
      error_message = "Set alert_email when create_budget = true."
    }
  }
}
