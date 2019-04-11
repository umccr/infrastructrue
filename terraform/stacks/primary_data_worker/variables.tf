################################################################################
# General variables

variable "stack_name" {
  default = "primary_data_worker"
}

variable "instance_ami" {
  default = "ami-02fd0b06f06d93dfc"
}

variable "instance_type" {
  default = "t2.micro"
}

variable "instance_vol_size" {
  default = 10
}

variable "instance_profile_name" {
  default = "AmazonEC2InstanceProfileforSSM"
}

################################################################################
# Workspace specific variables

variable "workspace_buckets" {
  type = "map"

  default = {
    dev = ["umccr-primary-data-dev"]
  }
}
