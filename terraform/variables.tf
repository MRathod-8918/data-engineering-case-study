# ==============================================================================
# 1. AWS Region Variable
# ==============================================================================
# Defines the primary AWS target region for all provisioned cloud resources
variable "aws_region" {
  type        = string
  description = "Target AWS region for deploying S3, Lambda, Glue, and IAM resources"
  default     = "us-east-1"
}

# ==============================================================================
# 2. Central S3 Data Lake Bucket Name Variable
# ==============================================================================
# Global unique bucket identifier for the Medallion Data Lake
variable "bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name hosting raw, archive, and processed data zones"
  default     = "iata-data-engineering-project-2026"
}

# ==============================================================================
# 3. AWS Glue Catalog Database Name Variable
# ==============================================================================
# Standardized Glue Catalog Database identifier used by Athena SQL
variable "db_name" {
  type        = string
  description = "Standardized AWS Glue Data Catalog database name for organizing SQL tables"
  default     = "iata_data_lake_db"
}

# ==============================================================================
# 4. External Dataset Ingestion URL Variable
# ==============================================================================
# External source endpoint passed to Download Lambda via environment variables
variable "dataset_url" {
  type        = string
  description = "External HTTP dataset URL injected into Download Lambda environment variables"
  default     = "https://eforexcel.com/wp/wp-content/uploads/2020/09/2m-Sales-Records.zip"
}