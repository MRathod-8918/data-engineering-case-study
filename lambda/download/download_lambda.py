import boto3
import urllib.request
import os

# Initialize the AWS Boto3 S3 client to interact with S3 bucket APIs
s3 = boto3.client("s3")

# Extract environment variables dynamically injected by Terraform
# This avoids hardcoding bucket names or URLs in the source code
BUCKET_NAME = os.environ["BUCKET_NAME"]
DATASET_URL = os.environ["DATASET_URL"]

def lambda_handler(event, context):
    # Extract the file name (e.g., '2m-Sales-Records.zip') from the dataset URL
    file_name = DATASET_URL.split("/")[-1]
    
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

    # Define target S3 key path under the raw/ folder (Medallion Data Lake architecture)
    target_key = f"raw/{file_name}"
    print(f"Uploading to s3://{BUCKET_NAME}/{target_key}...")
    
    # Upload the downloaded ZIP archive from local /tmp to the S3 raw/ prefix
    s3.upload_file(local_path, BUCKET_NAME, target_key)

    print("Download and S3 upload completed successfully!")
    
    # Return standard HTTP 200 Success response payload
    return {
        "statusCode": 200,
        "body": f"Dataset {file_name} uploaded successfully to S3 raw/"
    }