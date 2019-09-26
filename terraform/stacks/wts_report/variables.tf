variable "stack_name" {
  default = "wts_report"
}

variable "availability_zone" {
  default = "ap-southeast-2c"
}

variable "wts_report_trigger_file" {
  default = "wtc_complete"
}

################################################################################
## workspace variables

variable "workspace_wts_report_image_id" {
  default = {
    prod = "ami-0dec783a1085e23e1"
    dev = "ami-0d49b1b22eabc9826"
  }
}

variable "workspace_slack_lambda_arn" {
  type = "map"

  default = {
    prod = "arn:aws:lambda:ap-southeast-2:472057503814:function:bootstrap_slack_lambda_prod"
    dev  = "arn:aws:lambda:ap-southeast-2:620123204273:function:bootstrap_slack_lambda_dev"
  }
}

variable "workspace_primary_data_bucket" {
  type = "map"

  default = {
    prod = "umccr-primary-data-prod"
    dev  = "umccr-primary-data-dev2"
  }
}

variable "workspace_temp_bucket" {
  type = "map"

  default = {
    prod = "umccr-temp"
    dev  = "umccr-misc-temp"
  }
}

variable "workspace_refdata_bucket" {
  type = "map"

  default = {
    prod = "umccr-umccrise-refdata-prod"
    dev  = "umccr-misc-temp"
  }
}

variable "workspace_wts_report_buckets" {
  type = "map"

  default = {
    prod = ["arn:aws:s3:::umccr-primary-data-prod", "arn:aws:s3:::umccr-primary-data-prod/*", "arn:aws:s3:::umccr-umccrise-prod", "arn:aws:s3:::umccr-umccrise-prod/*", "arn:aws:s3:::umccr-umccrise-refdata-prod", "arn:aws:s3:::umccr-umccrise-refdata-prod/*"]
    dev  = ["arn:aws:s3:::umccr-primary-data-dev2", "arn:aws:s3:::umccr-primary-data-dev2/*", "arn:aws:s3:::umccr-misc-temp", "arn:aws:s3:::umccr-misc-temp/*"]
  }
}

variable "wts_report_mem" {
  type = "map"

  default = {
    prod = 50000
    dev = 50000
  }
}
variable "wts_report_vcpus" {
  type = "map"

  default = {
    prod = 8
    dev = 8
  }
}
