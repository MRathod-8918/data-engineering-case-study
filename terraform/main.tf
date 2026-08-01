# ==============================================================================
# AWS Provider Configuration
# ==============================================================================
# Configures the AWS Terraform provider plugin and target cloud region
provider "aws" {
  region = var.aws_region # Referenced from variables.tf (default: us-east-1)
}