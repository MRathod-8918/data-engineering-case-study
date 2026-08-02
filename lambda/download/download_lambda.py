import boto3
import urllib.request
import os
from datetime import datetime, timezone
from botocore.exceptions import ClientError

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = os.environ["BUCKET_NAME"]
DATASET_URL = os.environ["DATASET_URL"]
AUDIT_TABLE_NAME = os.environ["AUDIT_TABLE_NAME"]
audit_table = dynamodb.Table(AUDIT_TABLE_NAME)

def lambda_handler(event, context):
    file_name = DATASET_URL.split("/")[-1]
    target_key = f"raw/{file_name}"
    
    # 1. Master ID for the database row
    file_id = file_name 

    try:
        existing_file = s3.head_object(Bucket=BUCKET_NAME, Key=target_key)
        
        audit_table.update_item(
            Key={"file_id": file_id},
            UpdateExpression="SET download_status = :s, last_updated = :t",
            ExpressionAttributeValues={":s": "SKIPPED", ":t": datetime.now(timezone.utc).isoformat()}
        )
        return {"statusCode": 200, "skipped": True, "raw_key": target_key, "file_id": file_id}
    except ClientError:
        pass

    audit_table.update_item(
        Key={"file_id": file_id},
        UpdateExpression="SET download_status = :s, last_updated = :t",
        ExpressionAttributeValues={":s": "IN_PROGRESS", ":t": datetime.now(timezone.utc).isoformat()}
    )

    local_path = f"/tmp/{file_name}"
    
    # --- FIXED HEADERS ---
    # Spoofing a full Chrome browser to bypass 406 Not Acceptable errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    req = urllib.request.Request(DATASET_URL, headers=headers)
    
    with urllib.request.urlopen(req) as response:
        with open(local_path, "wb") as file:
            while chunk := response.read(8192):
                file.write(chunk)

    s3.upload_file(local_path, BUCKET_NAME, target_key)
    if os.path.exists(local_path):
        os.remove(local_path)

    audit_table.update_item(
        Key={"file_id": file_id},
        UpdateExpression="SET download_status = :s, last_updated = :t",
        ExpressionAttributeValues={":s": "SUCCESS", ":t": datetime.now(timezone.utc).isoformat()}
    )
    
    # 2. Pass file_id down to Unzip
    return {
        "statusCode": 200,
        "skipped": False,
        "raw_key": target_key,
        "file_id": file_id
    }