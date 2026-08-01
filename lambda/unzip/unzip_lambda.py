import boto3
import zipfile
import os
import shutil
import urllib.parse

# Initialize Boto3 S3 client to interact with AWS S3 APIs
s3 = boto3.client("s3")

# Extract environment variable injected by Terraform (data lake bucket name)
BUCKET_NAME = os.environ["BUCKET_NAME"]

def lambda_handler(event, context):
    # Parse S3 event notification payload to retrieve the uploaded object key
    raw_key = event["Records"][0]["s3"]["object"]["key"]
    
    # Decode URL-encoded object key (converts '%20' or '+' to spaces and special characters)
    zip_file = urllib.parse.unquote_plus(raw_key)
    
    print("S3 Event File:", zip_file)

    # Local file paths inside AWS Lambda's /tmp ephemeral storage space
    local_zip = "/tmp/" + os.path.basename(zip_file)
    extract_folder = "/tmp/extracted"

    # Workspace Hygiene: Clean up local /tmp directories from previous warm container runs
    # Prevents storage leaks and leftover file collisions
    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)
    os.makedirs(extract_folder, exist_ok=True)

    if os.path.exists(local_zip):
        os.remove(local_zip)

    # Download raw ZIP archive from S3 raw/ folder into local /tmp workspace
    print("Downloading:", zip_file)
    s3.download_file(BUCKET_NAME, zip_file, local_zip)

    # In-memory extraction: Unzip contents locally into the extracted folder
    print("Extracting ZIP file...")
    with zipfile.ZipFile(local_zip, "r") as zip_ref:
        zip_ref.extractall(extract_folder)

    # Extract base dataset name (e.g., '2m-Sales-Records' from '2m-Sales-Records.zip')
    dataset_name = os.path.splitext(os.path.basename(zip_file))[0]

    # Iterate through extracted files and upload them to the S3 archive/ zone
    for file_name in os.listdir(extract_folder):
        local_file = os.path.join(extract_folder, file_name)
        archive_file_name = dataset_name + ".csv"

        print("Uploading to archive/", archive_file_name)
        
        # Upload CSV to s3://<bucket>/archive/<dataset_name>.csv
        # This upload automatically triggers the downstream Transform Lambda via S3 Event Notifications
        s3.upload_file(local_file, BUCKET_NAME, "archive/" + archive_file_name)

    # Return standard HTTP 200 Success response
    return {
        "statusCode": 200,
        "message": "Dataset extracted and uploaded to archive"
    }