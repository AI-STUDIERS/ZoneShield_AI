variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS deployment region"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment"
}

variable "deploy_ec2" {
  type        = bool
  default     = false
  description = "Whether to spin up live EC2 instances (set true when AWS credits/account ready)"
}

variable "deploy_baseline_x86" {
  type        = bool
  default     = false
  description = "Spin up x86 c7i instance for comparative 3-way benchmarking"
}

variable "graviton_cool_ami" {
  type        = string
  default     = "ami-0c55b159cbfafe1f0" # Replace with exact marketplace/custom COOL AMI
  description = "AWS Marketplace COOL AMI on Graviton (Arm64)"
}

variable "x86_ami" {
  type        = string
  default     = "ami-0c7217cdde317cfec" # Amazon Linux 2023 x86_64
  description = "Base Amazon Linux 2023 AMI for x86 baseline"
}
