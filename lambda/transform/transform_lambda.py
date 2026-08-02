import boto3
import pandas as pd
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
    bucket = event.get("bucket", BUCKET_NAME)
    raw_key = event["raw_key"]
    csv_key = urllib.parse.unquote_plus(raw_key)

    # 1. Catch the exact file_id from upstream (2m-Sales-Records.zip)
    file_id = event.get("file_id")
    if not file_id:
        base_name = os.path.splitext(os.path.basename(csv_key))[0]
        file_id = f"{base_name}.zip"

    audit_table.update_item(
        Key={"file_id": file_id},
        UpdateExpression="SET transform_status = :s, last_updated = :t",
        ExpressionAttributeValues={":s": "IN_PROGRESS", ":t": datetime.now(timezone.utc).isoformat()}
    )

    local_csv_path = "/tmp/data.csv"
    output_path = "/tmp/parquet_data"


    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    os.makedirs(output_path, exist_ok=True)

    s3.download_file(bucket, csv_key, local_csv_path)
    df = pd.read_csv(local_csv_path)

    raw_csv_rows = len(df)
    df.columns = df.columns.str.strip()
    df["filename"] = os.path.basename(csv_key)

    if "Country" in df.columns:
        df["Country"] = df["Country"].astype(str).str.strip()
        df = df.rename(columns={"Country": "country"})

    if "Order ID" in df.columns:
        df = df.drop_duplicates(subset=["Order ID"])

    final_parquet_rows = len(df)
    duplicates_removed = raw_csv_rows - final_parquet_rows
    
    df.to_parquet(output_path, engine="pyarrow", partition_cols=["country"], index=False)

    for root, dirs, files in os.walk(output_path):
        for file in files:
            if file.endswith(".parquet"):
                local_file = os.path.join(root, file)
                relative_path = os.path.relpath(local_file, output_path)
                s3_key = f"processed/{relative_path.replace('\\', '/')}"
                s3.upload_file(local_file, bucket, s3_key)

    if os.path.exists(local_csv_path):
        os.remove(local_csv_path)
    if os.path.exists(output_path):
        shutil.rmtree(output_path)

    audit_table.update_item(
        Key={"file_id": file_id},
        UpdateExpression="SET transform_status = :s, raw_csv_rows = :r, final_parquet_rows = :p, duplicates_removed = :d, last_updated = :t",
        ExpressionAttributeValues={
            ":s": "SUCCESS",
            ":r": raw_csv_rows,
            ":p": final_parquet_rows,
            ":d": duplicates_removed,
            ":t": datetime.now(timezone.utc).isoformat()
        }
    )

    return {
        "statusCode": 200,
        "raw_csv_rows": raw_csv_rows,
        "final_parquet_rows": final_parquet_rows,
        "duplicates_removed": duplicates_removed,
        "file_id": file_id
    }