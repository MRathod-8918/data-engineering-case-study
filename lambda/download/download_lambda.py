import boto3
import urllib.request
import os
from botocore.exceptions import ClientError

# Initialize the AWS Boto3 S3 client to interact with S3 bucket APIs
s3 = boto3.client("s3")

# Extract environment variables dynamically injected by Terraform
# This avoids hardcoding bucket names or URLs in the source code
BUCKET_NAME = os.environ["BUCKET_NAME"]
DATASET_URL = os.environ["DATASET_URL"]

def lambda_handler(event, context):
    # Extract the file name (e.g., '2m-Sales-Records.zip') from the dataset URL
    file_name = DATASET_URL.split("/")[-1]
    target_key = f"raw/{file_name}"

    print(f"Checking idempotency for s3://{BUCKET_NAME}/{target_key}...")

    # --------------------------------------------------------------------------
    # 1. IDEMPOTENCY CHECK: Check if raw file already exists in S3
    # --------------------------------------------------------------------------
    try:
        existing_file = s3.head_object(Bucket=BUCKET_NAME, Key=target_key)
        file_size_mb = round(existing_file['ContentLength'] / (1024 * 1024), 2)
        print(f"IDEMPOTENCY MATCH: {target_key} already exists in S3 ({file_size_mb} MB). Skipping HTTP download!")
        
        # DUPLICATE FILE: Set skipped = True so Choice State branches to Skip
        return {
            "statusCode": 200,
            "skipped": True,
            "raw_key": target_key,
            "body": f"Dataset {file_name} already exists in S3 raw/. HTTP download skipped (Idempotent)."
        }
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code in ['404', '403', 'NotFound']:
            print(f"File {target_key} not found in S3 raw/. Initiating fresh download...")
        else:
            raise e

    # --------------------------------------------------------------------------
    # 2. FRESH DOWNLOAD LOGIC
    # --------------------------------------------------------------------------
    # Define ephemeral local storage path inside AWS Lambda's /tmp directory

    local_path = f"/tmp/{file_name}"

    # Construct an HTTP Request with custom headers to prevent HTTP 403 Forbidden errors
    # Mimics a real web browser request to ensure successful file downloads
    req = urllib.request.Request(
        DATASET_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/zip,application/octet-stream,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://eforexcel.com/"
        }
    )

    print(f"Downloading dataset from {DATASET_URL}...")

    # Stream the ZIP file directly to /tmp using 8KB (8192 bytes) chunking
    # Optimization: Prevents loading the full file into memory, keeping Lambda RAM usage minimal
    with urllib.request.urlopen(req) as response:
        with open(local_path, "wb") as file:
            while chunk := response.read(8192):
                file.write(chunk)

    print(f"Uploading to s3://{BUCKET_NAME}/{target_key}...")
    
    # Upload the downloaded ZIP archive from local /tmp to the S3 raw/ prefix
    s3.upload_file(local_path, BUCKET_NAME, target_key)

    # Clean up local /tmp file
    if os.path.exists(local_path):
        os.remove(local_path)

    print("Download and S3 upload completed successfully!")
    
    # FIRST-TIME DOWNLOAD: Set skipped = False so Choice State proceeds to Unzip
    return {
        "statusCode": 200,
        "skipped": False,
        "raw_key": target_key,
        "body": f"Dataset {file_name} uploaded successfully to S3 raw/"
    }