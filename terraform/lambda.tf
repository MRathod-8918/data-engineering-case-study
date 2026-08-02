# ==============================================================================
# 1. Download Lambda Function & Packaging
# ==============================================================================

# Automatically packages the download Lambda code into a ZIP archive
data "archive_file" "download_lambda_zip" {
  type        = "zip"
  source_dir  = "../lambda/download"
  output_path = "../lambda/download.zip"
}

# Ingestion Lambda: Fetches external zipped dataset over HTTP
resource "aws_lambda_function" "download_lambda" {
  filename      = data.archive_file.download_lambda_zip.output_path
  function_name = "iata-download-dataset"
  role          = aws_iam_role.lambda_role.arn

  # UPDATED HANDLER: Points specifically to download_lambda.py -> lambda_handler
  handler = "download_lambda.lambda_handler"

  runtime     = "python3.12"
  timeout     = 300 # 5-minute timeout for streaming large HTTP downloads
  memory_size = 512 # Allocated RAM for optimal streaming performance

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.iata_data_lake.bucket
      DATASET_URL = var.dataset_url # Parameterized URL from variables.tf
      AUDIT_TABLE_NAME = aws_dynamodb_table.pipeline_audit.name
    }
  }
}

# ==============================================================================
# 2. Unzip Lambda Function & Packaging
# ==============================================================================

# Packages the unzipping Lambda code into a ZIP archive
data "archive_file" "unzip_lambda_zip" {
  type        = "zip"
  source_dir  = "../lambda/unzip"
  output_path = "../lambda/unzip.zip"
}

# Event-Driven Unzip Lambda: Extracts ZIP archives in S3 raw/ to CSVs in archive/
resource "aws_lambda_function" "unzip_lambda" {
  filename      = data.archive_file.unzip_lambda_zip.output_path
  function_name = "iata-unzip-dataset"
  role          = aws_iam_role.lambda_role.arn

  # UPDATED HANDLER: Points specifically to unzip_lambda.py -> lambda_handler
  handler = "unzip_lambda.lambda_handler"

  runtime     = "python3.12"
  timeout     = 300
  memory_size = 512

  # Production Optimization: Expanded /tmp disk space to 2GB (2048MB) for multi-million row files
  ephemeral_storage {
    size = 2048
  }

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.iata_data_lake.bucket
      AUDIT_TABLE_NAME = aws_dynamodb_table.pipeline_audit.name
    }
  }
}

# ==============================================================================
# 3. Transform Lambda Function (CSV to Partitioned Parquet)
# ==============================================================================

# Packages the transformation Lambda code into a ZIP archive
data "archive_file" "transform_lambda_zip" {
  type        = "zip"
  source_dir  = "../lambda/transform"
  output_path = "../lambda/transform.zip"
}

# Transformation Lambda: Cleans CSVs, adds 'filename' audit column, exports Snappy Parquet
resource "aws_lambda_function" "transform_lambda" {
  filename      = data.archive_file.transform_lambda_zip.output_path
  function_name = "iata-transform-dataset"
  role          = aws_iam_role.lambda_role.arn

  # UPDATED HANDLER: Points specifically to transform_lambda.py -> lambda_handler
  handler = "transform_lambda.lambda_handler"

  runtime     = "python3.12"
  timeout     = 900  # Max 15-minute execution limit for dataset transformations
  memory_size = 2048 # 2GB RAM for fast in-memory Pandas & PyArrow processing

  ephemeral_storage {
    size = 2048 # 2GB ephemeral storage for writing local Parquet partitions
  }

  # AWS MANAGED LAYER (US-EAST-1): Bundles Pandas, PyArrow, and NumPy
  # Solves 413 RequestEntityTooLarge error by avoiding massive direct ZIP package uploads
  layers = [
    "arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python312:13"
  ]

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.iata_data_lake.bucket
      AUDIT_TABLE_NAME = aws_dynamodb_table.pipeline_audit.name
    }
  }
}

# ==============================================================================
# 4. Lambda Execution Permissions (S3 Invocation Rights)
# ==============================================================================

# Grants S3 permission to trigger the Unzip Lambda when an object lands in raw/
resource "aws_lambda_permission" "allow_s3_unzip" {
  statement_id  = "AllowExecutionFromS3Unzip"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.unzip_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.iata_data_lake.arn
}

# Grants S3 permission to trigger the Transform Lambda when an object lands in archive/
resource "aws_lambda_permission" "allow_s3_transform" {
  statement_id  = "AllowExecutionFromS3Transform"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.transform_lambda.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.iata_data_lake.arn
}

# ==============================================================================
# 5. S3 Event Notifications (Automated Event-Driven Pipeline)
# ==============================================================================

# Configures S3 object creation triggers to drive the decoupled serverless pipeline
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = aws_s3_bucket.iata_data_lake.id

  # Event Rule 1: Trigger Unzip Lambda strictly when a .zip lands under raw/
  lambda_function {
    lambda_function_arn = aws_lambda_function.unzip_lambda.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "raw/"
    filter_suffix       = ".zip"
  }

  # Event Rule 2: Trigger Transform Lambda strictly when a .csv lands under archive/
  # Prevents Circular Loops: Prefix/suffix filters guarantee triggers won't loop infinitely
  lambda_function {
    lambda_function_arn = aws_lambda_function.transform_lambda.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "archive/"
    filter_suffix       = ".csv"
  }

  # Explicit dependency ensuring permissions exist before linking bucket notification rules
  depends_on = [
    aws_lambda_permission.allow_s3_unzip,
    aws_lambda_permission.allow_s3_transform
  ]
}