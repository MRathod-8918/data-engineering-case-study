import boto3
import pandas as pd
import os
import shutil
import urllib.parse

# Initialize Boto3 S3 client for downloading CSVs and uploading Parquet partitions
s3 = boto3.client("s3")

# Extract environment variables dynamically injected by Terraform
BUCKET_NAME = os.environ["BUCKET_NAME"]


def lambda_handler(event, context):
    # ==========================================================================
    # STEP FUNCTIONS INPUT PARSING (No hardcoded fallbacks)
    # Reads exact parameters passed dynamically from the upstream state
    # ==========================================================================
    bucket = event.get("bucket", BUCKET_NAME)
    raw_key = event["raw_key"]

    # Decode URL-encoded object key (converts '%20' or '+' to spaces)
    csv_key = urllib.parse.unquote_plus(raw_key)
    
    print(f"Processing file: s3://{bucket}/{csv_key}")

    # Local workspace directories in Lambda's /tmp ephemeral storage
    local_csv_path = "/tmp/data.csv"
    output_path = "/tmp/parquet_data"

    # Workspace Hygiene: Clean up stale output folders from previous container runs
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path, exist_ok=True)

    # Download source CSV file from S3 archive/ folder into local /tmp
    s3.download_file(bucket, csv_key, local_csv_path)

    # Load CSV data into a Pandas DataFrame for in-memory cleaning & transformation
    df = pd.read_csv(local_csv_path)

    # --- QUALITY & DEDUPLICATION CHECKS ---
    raw_csv_rows = len(df)
    null_counts = df.isnull().sum().to_dict()
    print(f"Auditing Raw CSV: {raw_csv_rows} rows found. Null distribution: {null_counts}")

    # Strip leading/trailing whitespace from column headers
    df.columns = df.columns.str.strip()

    # AUDIT COLUMN (Data Lineage): Track original source file name
    df["filename"] = os.path.basename(csv_key)

    # Data Cleaning: Normalize 'Country' values and rename key to lowercase 'country'
    if "Country" in df.columns:
        df["Country"] = df["Country"].astype(str).str.strip()
        df = df.rename(columns={"Country": "country"})

    # DEDUPLICATION: Remove duplicate records based on primary business key 'Order ID'
    if "Order ID" in df.columns:
        df = df.drop_duplicates(subset=["Order ID"])

    final_parquet_rows = len(df)
    duplicates_removed = raw_csv_rows - final_parquet_rows
    print(
        f"Reconciliation Metric: Raw Rows = {raw_csv_rows} | "
        f"Parquet Rows = {final_parquet_rows} | "
        f"Duplicates Stripped = {duplicates_removed}"
    )

    # Conversion: Transform DataFrame into Hive-partitioned Snappy Parquet files using PyArrow
    df.to_parquet(
        output_path,
        engine="pyarrow",
        partition_cols=["country"],
        index=False
    )

    # Recursively upload generated Parquet partitions to S3 processed/ prefix
    for root, dirs, files in os.walk(output_path):
        for file in files:
            if file.endswith(".parquet"):
                local_file = os.path.join(root, file)
                relative_path = os.path.relpath(local_file, output_path)
                s3_key = f"processed/{relative_path.replace('\\', '/')}"

                print(f"Uploading: {local_file} -> s3://{bucket}/{s3_key}")
                s3.upload_file(local_file, bucket, s3_key)

    # Clean up temporary local files
    if os.path.exists(local_csv_path):
        os.remove(local_csv_path)
    if os.path.exists(output_path):
        shutil.rmtree(output_path)

    # Return reconciliation summary payload to Step Functions
    return {
        "statusCode": 200,
        "raw_csv_rows": raw_csv_rows,
        "final_parquet_rows": final_parquet_rows,
        "duplicates_removed": duplicates_removed,
        "message": "CSV successfully validated, deduplicated, and converted to partitioned Parquet!"
    }