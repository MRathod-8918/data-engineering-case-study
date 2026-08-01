IATA Case Study

Business Context
IATA’s Economics department urgently acquired a sales dataset to analyze prior to a leadership meeting with the French Minister of Transportation. This project provides an automated, serverless pipeline to ingest, format, partition, and expose the dataset in AWS for immediate SQL analytics.

Architecture Overview
[ HTTP Target URL ]
       │
       ▼ (1. Trigger / Manual Call)
[ AWS Lambda: Download ]
       │
       ▼ (Writes raw ZIP)
[ S3: raw/ ]
       │
       ▼ (2. S3 Event Notification)
[ AWS Lambda: Unzip ]
       │
       ▼ (Extracts CSV & Moves ZIP)
[ S3: archive/ ]
       │
       ▼ (3. S3 Event Notification)
[ AWS Lambda: Transform ]
       │
       ▼ (Converts CSV to Parquet partitioned by Country)
[ S3: processed/country=... ]
       │
       ▼ (4. Partition Projection)
[ AWS Glue Catalog & Amazon Athena ]

Key Highlights
1. Decoupled Architecture: Built as 3 single-responsibility Lambdas (Download -> Unzip -> Transform) triggered automatically via S3 ObjectCreated events.
2. Cost & Query Optimization: Converts CSV to Snappy-compressed Apache Parquet partitioned by Country, dramatically reducing S3 storage size and Athena query costs.
3. 100% Serverless & IaC: Provisioned entirely via Terraform (S3, IAM, Lambda, Glue) with zero server maintenance and zero idle costs.

Repository Structure
├── lambda/
│   ├── download/     # Lambda 1: Streamed HTTP downloader
│   ├── unzip/        # Lambda 2: Zip extraction & archive management
│   └── transform/    # Lambda 3: Pandas/PyArrow CSV-to-Parquet converter
├── terraform/        # Complete IaC setup (main.tf, lambda.tf, glue.tf, etc.)
└── README.md

Quickstart & Deployment
1. Deploy Infrastructure
Bash
cd terraform
terraform init
terraform apply -auto-approve
2. Trigger Pipeline
Bash
aws lambda invoke --function-name iata-download-dataset response.json

SQL Analytics via Athena
Once processed, query the partitioned dataset directly in Amazon Athena:
SQL
SELECT 
    country,
    COUNT(*) AS total_orders,
    SUM("units sold") AS total_units,
    ROUND(SUM("total revenue"), 2) AS gross_revenue,
    ROUND(SUM("total profit"), 2) AS net_profit
FROM iata_economics_db.sales_records
WHERE country = 'France'
GROUP BY country;

Production Enhancements (Next Steps)
1. Orchestration: 
Transition S3 event triggers to AWS Step Functions for state tracking, retries, and error handling.
2. Large Scale Processing: 
Upgrade Lambda transform step to AWS Glue PySpark for files exceeding Lambda /tmp limits (>10 GB).
3. CI/CD & Governance: 
Implement GitHub Actions for automated terraform plan checks and Great Expectations for automated schema/data validation.
