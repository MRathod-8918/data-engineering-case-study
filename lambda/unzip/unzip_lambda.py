import boto3
import zipfile
import os
import shutil
import urllib.parse
from datetime import datetime, timezone

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = os.environ["BUCKET_NAME"]
AUDIT_TABLE_NAME = os.environ["AUDIT_TABLE_NAME"]
audit_table = dynamodb.Table(AUDIT_TABLE_NAME)

def lambda_handler(event, context):
    raw_key = event["raw_key"]
    zip_file = urllib.parse.unquote_plus(raw_key)
    
    # 1. Catch the exact file_id from the upstream event (2m-Sales-Records.zip)
    file_id = event.get("file_id", os.path.basename(zip_file))

    audit_table.update_item(
        Key={"file_id": file_id},
        UpdateExpression="SET unzip_status = :s, last_updated = :t",
        ExpressionAttributeValues={":s": "IN_PROGRESS", ":t": datetime.now(timezone.utc).isoformat()}
    )

    local_zip = "/tmp/" + os.path.basename(zip_file)
    extract_folder = "/tmp/extracted"

    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)
    os.makedirs(extract_folder, exist_ok=True)
    if os.path.exists(local_zip):
        os.remove(local_zip)

    s3.download_file(BUCKET_NAME, zip_file, local_zip)
                                                                                                                        
    with zipfile.ZipFile(local_zip, "r") as zip_ref:
        zip_ref.extractall(extract_folder)

    dataset_name = os.path.splitext(os.path.basename(zip_file))[0]
    extracted_csv_key = ""

    for extracted_file in os.listdir(extract_folder):
        local_file = os.path.join(extract_folder, extracted_file)
        archive_file_name = dataset_name + ".csv"
        extracted_csv_key = "archive/" + archive_file_name
        s3.upload_file(local_file, BUCKET_NAME, extracted_csv_key)

    if os.path.exists(local_zip):
        os.remove(local_zip)
    if os.path.exists(extract_folder):
        shutil.rmtree(extract_folder)

    audit_table.update_item(
        Key={"file_id": file_id},
        UpdateExpression="SET unzip_status = :s, extracted_csv_key = :k, last_updated = :t",
        ExpressionAttributeValues={
            ":s": "SUCCESS",
            ":k": extracted_csv_key,
            ":t": datetime.now(timezone.utc).isoformat()
        }
    )

    # 2. Pass file_id down to Transform
    return {"statusCode": 200, "raw_key": extracted_csv_key, "file_id": file_id}