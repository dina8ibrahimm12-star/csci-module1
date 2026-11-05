variable "region" {
  type        = string
  default     = "eu-north-1"
  description = "Must equal the Region AWS assigned to your project (AWS Settings > Project > Additional info). It cannot be changed in the new AWS experience."
}

variable "project" {
  type    = string
  default = "csci"
}

variable "log_retention_days" {
  type        = number
  default     = 365
  description = "Days before logs expire. Must cover the whole project + report period."
}

variable "create_cloudtrail" {
  type        = bool
  default     = true
  description = "Set false if the account already has a trail that you are allowed to use."
}

variable "cloudtrail_multi_region" {
  type        = bool
  default     = false
  description = "The new AWS experience does not support multi-Region features, so this is false. Set true only on an account that allows it."
}

variable "athena_date_start" {
  type        = string
  default     = "2026/10/01"
  description = "First day (yyyy/MM/dd) covered by the Athena CloudTrail table."
}
