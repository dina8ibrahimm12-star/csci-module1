variable "region" {
  type        = string
  default     = "eu-north-1"
  description = "Must equal the Region AWS assigned to your project (AWS Settings > Project > Additional info). It cannot be changed in the new AWS experience."
}

variable "project" {
  type    = string
  default = "csci"
}

variable "logs_bucket_name" {
  type        = string
  description = "Name of the persistent log bucket created by infra/evidence (output: logs_bucket)."
}

variable "create_web_server" {
  type        = bool
  default     = false
  description = "Creates the EC2 web server. OFF by default; turn on only after team approval."
}

variable "create_config_recorder" {
  type        = bool
  default     = true
  description = "AWS Config allows ONE recorder and ONE delivery channel per region. Set false if the account already has Config set up."
}

variable "create_flow_logs" {
  type    = bool
  default = true
}

variable "create_budget" {
  type        = bool
  default     = false
  description = "Create an AWS Budget alert with Terraform (needs alert_email). You may create the budget in the console instead (docs/RUNBOOK.md step 4)."
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "monthly_budget_usd" {
  type    = number
  default = 20
}
