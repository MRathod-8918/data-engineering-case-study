import boto3
import pandas as pd
import os
import shutil
import urllib.parse

# Initialize Boto3 S3 client for downloading CSVs and uploading Parquet partitions
s3 = boto3.client("s3")

def lambda_handler(event, context):
    # Parse S3 event notification payload to extract bucket name and object key
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    raw_key = event["Records"][0]["s3"]["object"]["key"]
    
    # Decode URL-encoded characters (e.g., converts '%20' or '+' to spaces)
    csv_key = urllib.parse.unquote_plus(raw_key)
    
    print(f"Processing file: s3://{bucket}/{csv_key}")

    # Local workspace directories in Lambda's /tmp ephemeral storage
    local_csv_path = "/tmp/data.csv"
    output_path = "/tmp/parquet_data"

    # Workspace Hygiene: Clean up stale output folders from previous warm container invocations
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path, exist_ok=True)

    # Download source CSV file from S3 archive/ folder into local /tmp
    s3.download_file(bucket, csv_key, local_csv_path)

    # Load CSV data into a Pandas DataFrame for in-memory cleaning & transformation
    df = pd.read_csv(local_csv_path)

    # Data Cleaning 1: Strip leading/trailing whitespace from column headers
    df.columns = df.columns.str.strip()

    # AUDIT COLUMN (Data Lineage): Track the original source file name per row
    # Enables querying source file provenance directly in Amazon Athena
    df["filename"] = os.path.basename(csv_key)

    # Data Cleaning 2: Normalize 'Country' values and rename key to lowercase 'country'
    # Matches PyArrow Hive-partition folder conventions (e.g., country=India/)
    if "Country" in df.columns:
        df["Country"] = df["Country"].astype(str).str.strip()
        df = df.rename(columns={"Country": "country"})

    # Conversion: Transform DataFrame into Hive-partitioned Snappy Parquet files using PyArrow
    # Creates local nested folder structure: /tmp/parquet_data/country=<Country_Name>/
    df.to_parquet(
        output_path,
        engine="pyarrow",
        partition_cols=["country"],
        index=False
    )

    # Walk local output directory tree and upload generated Parquet partitions to S3 processed/ prefix
    for root, dirs, files in os.walk(output_path):
        for file in files:
            if file.endswith(".parquet"):
                local_file = os.path.join(root, file)
                relative_path = os.path.relpath(local_file, output_path)
                
                # Format S3 object key; convert OS backslashes (Windows) to S3 forward slashes
                s3_key = f"processed/{relative_path.replace('\\', '/')}"

                print(f"Uploading: {local_file} -> s3://{bucket}/{s3_key}")
                s3.upload_file(local_file, bucket, s3_key)

    # Clean up temporary CSV file to free up ephemeral /tmp disk space
    if os.path.exists(local_csv_path):
        os.remove(local_csv_path)

    # Return HTTP 200 success response payload
    return {
        "statusCode": 200,
        "message": "CSV successfully converted to partitioned Parquet with filename audit column!"
    }