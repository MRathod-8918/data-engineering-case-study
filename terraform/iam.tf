# ------------------------------------------------------------------------------
# 1. IAM Role for AWS Lambda Functions
# ------------------------------------------------------------------------------
# Creates the execution role that AWS Lambda functions assume when running
resource "aws_iam_role" "lambda_role" {
  name = "iata-lambda-role"

  # Trust Policy: Allows the AWS Lambda service to assume this role via STS (Security Token Service)
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com" # Grants permission strictly to AWS Lambda
        }
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# 2. Lambda IAM Policy Attachments
# ------------------------------------------------------------------------------
# Policy Attachment 1: Grants full read/write access to S3 buckets
# Allows Lambdas to download raw ZIPs, save extracted CSVs, and write Parquet partitions
resource "aws_iam_role_policy_attachment" "lambda_s3_access" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Policy Attachment 2: Grants logging permissions to Amazon CloudWatch Logs
# Enables stdout/stderr print statements and error tracebacks to be ingested into CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ------------------------------------------------------------------------------
# 3. IAM Role for AWS Glue Services
# ------------------------------------------------------------------------------
# Creates the service role that AWS Glue catalog services assume
resource "aws_iam_role" "glue_role" {
  name = "iata-glue-role"

  # Trust Policy: Allows the AWS Glue service to assume this execution role
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com" # Grants permission strictly to AWS Glue
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# ------------------------------------------------------------------------------
# 4. Glue IAM Policy Attachments
# ------------------------------------------------------------------------------
# Policy Attachment 1: Grants standard AWS Glue service execution permissions
# Allows Glue to read/write catalog databases, tables, and schema definitions
resource "aws_iam_role_policy_attachment" "glue_service_role" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Policy Attachment 2: Grants AWS Glue access to S3 data lake storage
# Enables schema verification and cataloging against underlying S3 objects
resource "aws_iam_role_policy_attachment" "glue_s3_access" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}