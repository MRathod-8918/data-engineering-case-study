# ==============================================================================
# Central Data Lake S3 Bucket Creation
# ==============================================================================
resource "aws_s3_bucket" "iata_data_lake" {
  bucket = var.bucket_name # Referenced from variables.tf
}

# ==============================================================================
# Medallion Data Lake Sub-Directory Provisioning
# ==============================================================================
# Bronze Zone: Incoming raw .zip archives
resource "aws_s3_object" "raw_folder" {
  bucket = aws_s3_bucket.iata_data_lake.id
  key    = "raw/"
}

# Silver Zone: Extracted uncompressed .csv files
resource "aws_s3_object" "archive_folder" {
  bucket = aws_s3_bucket.iata_data_lake.id
  key    = "archive/"
}

# Gold Zone: Snappy-compressed Parquet files partitioned by country
resource "aws_s3_object" "processed_folder" {
  bucket = aws_s3_bucket.iata_data_lake.id
  key    = "processed/"
}

# Analytics Zone: Output directory for Amazon Athena SQL query results
resource "aws_s3_object" "athena_results_folder" {
  bucket = aws_s3_bucket.iata_data_lake.id
  key    = "athena-results/"
}