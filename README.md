Serverless Data Engineering Pipeline (IATA Case Study)
An end-to-end, fully automated, event-driven serverless data lake pipeline built on AWS using Terraform (Infrastructure as Code).

This pipeline ingests raw dataset archives, extracts them, converts raw CSV data into partitioned Apache Parquet format, and exposes it for high-performance SQL analytics via AWS Glue Data Catalog and Amazon Athena.

Architecture Overview
The pipeline follows a decoupled, event-driven Lambda architecture:

Plaintext
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
       ▼ (Writes extracted CSV)
[ S3: archive/ ]
       │
       ▼ (3. S3 Event Notification)
[ AWS Lambda: Transform ]
       │
       ▼ (Converts CSV to Parquet partitioned by country)
[ S3: processed/country=... ]
       │
       ▼ (4. Partition Projection)
[ AWS Glue Catalog & Amazon Athena ]
Key Architecture Highlights
Zero Infrastructure Management: Fully serverless design using AWS Lambda, S3, Glue, and Athena with zero server provisioning or idle running costs.

Fast Query Performance: Converting raw CSV to Snappy-compressed columnar Parquet reduces storage footprint by over 70% and drastically lowers Athena S3 scan costs.

Cost Guardrails with Injected Partition Projection: Partitioning data by country and enforcing mandatory partition filters in Glue prevents expensive, accidental full-table scans across millions of records.

Automated Ingestion Cascade: Fully event-driven flow triggered directly by S3 ObjectCreated notifications, eliminating manual execution steps between ingestion, unzipping, and Parquet conversion.

Production-Grade IaC: 100% of AWS infrastructure—including S3 buckets, IAM roles, Lambda functions, event triggers, and Glue Catalog schemas—is declared, managed, and deployed via Terraform.

Repository Structure
Plaintext
.
├── lambda/
│   ├── download/         # Lambda 1: HTTP downloader logic
│   ├── unzip/            # Lambda 2: Zip extraction logic
│   └── transform/        # Lambda 3: Pandas/PyArrow CSV-to-Parquet logic
├── terraform/
│   ├── main.tf           # Terraform AWS Provider & Bucket settings
│   ├── lambda.tf         # Lambda definitions & IAM roles/policies
│   ├── glue.tf           # Glue Database & Partition-Projected Table
│   └── outputs.tf        # Bucket names & Resource IDs
└── README.md             # Project documentation
Quickstart & Deployment
Prerequisites
Terraform (version 1.0 or higher)

AWS CLI configured with administrative credentials

Python 3.11+ (for local Lambda packaging)

Deployment Steps
Clone the Repository:

Bash
git clone <YOUR_PUBLIC_GITHUB_REPO_URL>
cd <REPO_FOLDER>
Deploy Infrastructure via Terraform:

Bash
cd terraform
terraform init
terraform apply -auto-approve
Trigger the Data Pipeline:
Invoke the initial download Lambda function to start the ingestion cascade:

Bash
aws lambda invoke --function-name iata-download-dataset response.json
Validation & SQL Analytics
Once the pipeline completes, open the Amazon Athena Console and execute these sample queries to test performance and data accuracy across partitions:

1. Revenue & Profit Summary for France
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
2. Item Type Profitability in Germany
SQL
SELECT 
    "item type",
    COUNT("order id") AS total_orders,
    ROUND(SUM("total profit"), 2) AS total_profit
FROM iata_economics_db.sales_records
WHERE country = 'Germany'
GROUP BY "item type"
ORDER BY total_profit DESC;
Production Enhancements (Next Steps)
If extended for full enterprise production, the following enhancements would be added:

Orchestration: Replace direct S3 event triggers with AWS Step Functions for centralized state management, visual monitoring, and automatic retry policies.

Large Scale Processing: Transition from Pandas/PyArrow on Lambda to AWS Glue PySpark or EMR Serverless if single-file input sizes exceed Lambda /tmp disk bounds (greater than 10GB).

Data Quality Framework: Integrate AWS Glue Data Quality or Great Expectations to validate row counts, null constraints, and datatypes prior to Parquet storage.

CI/CD Automation: Implement GitHub Actions to run automated terraform plan checks, linting, and unit testing on pull requests.