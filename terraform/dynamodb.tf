# ==============================================================================
# 1. DynamoDB Table for Data Pipeline Audit Logging
# ==============================================================================
resource "aws_dynamodb_table" "pipeline_audit" {
  name         = "iata-pipeline-audit-log"
  billing_mode = "PAY_PER_REQUEST" # Free Tier Friendly / On-Demand Capacity
  hash_key     = "file_id"

  attribute {
    name = "file_id"
    type = "S"
  }
  
  tags = {
    Environment = "Test"
    Project     = "IATA-Data-Engineering"
  }
}

# ==============================================================================
# 2. IAM Policy & Attachment for Lambda DynamoDB Audit Logging
# ==============================================================================

# IAM Policy allowing Lambda functions to insert and retrieve audit records
resource "aws_iam_policy" "dynamodb_write_policy" {
  name        = "iata-lambda-dynamodb-policy"
  description = "Allows Lambda functions to write audit status logs to DynamoDB"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:GetItem"
        ]
        Resource = aws_dynamodb_table.pipeline_audit.arn
      }
    ]
  })
}

# Attaches the DynamoDB Policy directly to your existing Lambda IAM role (aws_iam_role.lambda_role)
resource "aws_iam_role_policy_attachment" "lambda_dynamodb_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.dynamodb_write_policy.arn
}