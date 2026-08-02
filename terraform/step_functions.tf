# ==============================================================================
# 1. IAM Execution Role for AWS Step Functions
# ==============================================================================
resource "aws_iam_role" "step_functions_role" {
  name = "iata-step-functions-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "states.amazonaws.com"
        }
      }
    ]
  })
}

# IAM Policy allowing Step Functions to invoke pipeline Lambdas
resource "aws_iam_role_policy" "step_functions_lambda_policy" {
  name = "iata-step-functions-lambda-invoke-policy"
  role = aws_iam_role.step_functions_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "lambda:InvokeFunction"
        Effect = "Allow"
        Resource = [
          aws_lambda_function.download_lambda.arn,
          aws_lambda_function.unzip_lambda.arn,
          aws_lambda_function.transform_lambda.arn
        ]
      }
    ]
  })
}

# ==============================================================================
# 2. AWS Step Functions State Machine with Idempotency Choice State
# ==============================================================================
resource "aws_sfn_state_machine" "iata_pipeline_orchestrator" {
  name     = "iata-data-pipeline-orchestrator"
  role_arn = aws_iam_role.step_functions_role.arn

  definition = jsonencode({
    Comment = "IATA Data Engineering Pipeline with Idempotency Choice State"
    StartAt = "DownloadDatasetTask"
    States = {

      # ------------------------------------------------------------------------
      # Task 1: Download Lambda
      # ------------------------------------------------------------------------
      DownloadDatasetTask = {
        Type     = "Task"
        Resource = aws_lambda_function.download_lambda.arn

        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 5
            MaxAttempts     = 3
            BackoffRate     = 2.0
          }
        ]

        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "PipelineFailedState"
          }
        ]
        Next = "CheckIfSkippedChoice"
      }

      # ------------------------------------------------------------------------
      # CHOICE STATE: Branch off automatically based on 'skipped' flag
      # ------------------------------------------------------------------------
      CheckIfSkippedChoice = {
        Type = "Choice"
        Choices = [
          {
            And = [
              {
                Variable  = "$.skipped"
                IsPresent = true
              },
              {
                Variable      = "$.skipped"
                BooleanEquals = true
              }
            ]
            Next = "PipelineAlreadyProcessedState"
          }
        ]
        Default = "UnzipDatasetTask"
      }

      # ------------------------------------------------------------------------
      # Task 2: Unzip Lambda
      # ------------------------------------------------------------------------
      UnzipDatasetTask = {
        Type     = "Task"
        Resource = aws_lambda_function.unzip_lambda.arn

        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 5
            MaxAttempts     = 2
            BackoffRate     = 2.0
          }
        ]

        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "PipelineFailedState"
          }
        ]
        Next = "TransformDatasetTask"
      }

      # ------------------------------------------------------------------------
      # Task 3: Transform Lambda
      # ------------------------------------------------------------------------
      TransformDatasetTask = {
        Type     = "Task"
        Resource = aws_lambda_function.transform_lambda.arn

        Retry = [
          {
            ErrorEquals     = ["States.ALL"]
            IntervalSeconds = 5
            MaxAttempts     = 2
            BackoffRate     = 2.0
          }
        ]

        Catch = [
          {
            ErrorEquals = ["States.ALL"]
            Next        = "PipelineFailedState"
          }
        ]
        End = true
      }

      # ------------------------------------------------------------------------
      # State: Skip execution safely if file already exists
      # ------------------------------------------------------------------------
      PipelineAlreadyProcessedState = {
        Type    = "Succeed"
        Comment = "File already exists in S3 raw/. Downstream unzipping and transformation skipped."
      }

      # ------------------------------------------------------------------------
      # State: Failure Fallback
      # ------------------------------------------------------------------------
      PipelineFailedState = {
        Type  = "Fail"
        Error = "PipelineExecutionFailed"
        Cause = "A Lambda task in the pipeline encountered an error."
      }
    }
  })
}