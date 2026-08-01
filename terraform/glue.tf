# ------------------------------------------------------------------------------
# 1. AWS Glue Catalog Database
# ------------------------------------------------------------------------------
# Logical container inside the AWS Glue Data Catalog to organize data lake tables
resource "aws_glue_catalog_database" "iata_db" {
  name = var.db_name # Referenced from variables.tf (default: iata_data_lake_db)
}

# ------------------------------------------------------------------------------
# 2. Production Processed Parquet External Table
# ------------------------------------------------------------------------------
# Defines the metadata schema, file location, and partition rules for Athena SQL
resource "aws_glue_catalog_table" "processed_parquet_table" {
  name          = "sales_records"
  database_name = aws_glue_catalog_database.iata_db.name
  table_type    = "EXTERNAL_TABLE" # Points to underlying S3 data without owning the storage

  # Table parameters enabling Athena Partition Projection and metadata properties
  parameters = {
    "EXTERNAL"            = "TRUE"
    "parquet.compression" = "SNAPPY"

    # PARTITION PROJECTION: Allows Athena to calculate S3 partition locations dynamically in memory
    # Optimization: Completely eliminates the need to run costly/slow Glue Crawlers or MSCK REPAIR TABLE
    "projection.enabled"                  = "true"
    "projection.country.type"             = "injected" # Allows filtering by country dynamically in SQL WHERE clauses
    
    # S3 Hive Path Template: Matches the PyArrow output structure (country=<Country_Name>)
    "projection.country.locationtemplate" = "s3://${aws_s3_bucket.iata_data_lake.bucket}/processed/country=$${country}/"
    "storage.location.template"           = "s3://${aws_s3_bucket.iata_data_lake.bucket}/processed/country=$${country}/"
  }

  # Storage Descriptor: Specifies S3 location, SerDe (Serializer/Deserializer), and schema
  storage_descriptor {
    location      = "s3://${aws_s3_bucket.iata_data_lake.bucket}/processed/"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    # Hive SerDe for reading Apache Parquet columnar binary files
    ser_de_info {
      name                  = "ParquetHiveSerDe"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    # Data Schema Definition: Matches the Pandas DataFrame column structure
    columns {
      name = "Region"
      type = "string"
    }
    columns {
      name = "Item Type"
      type = "string"
    }
    columns {
      name = "Sales Channel"
      type = "string"
    }
    columns {
      name = "Order Priority"
      type = "string"
    }
    columns {
      name = "Order Date"
      type = "string"
    }
    columns {
      name = "Order ID"
      type = "bigint"
    }
    columns {
      name = "Ship Date"
      type = "string"
    }
    columns {
      name = "Units Sold"
      type = "int"
    }
    columns {
      name = "Unit Price"
      type = "double"
    }
    columns {
      name = "Unit Cost"
      type = "double"
    }
    columns {
      name = "Total Revenue"
      type = "double"
    }
    columns {
      name = "Total Cost"
      type = "double"
    }
    columns {
      name = "Total Profit"
      type = "double"
    }
    
    # AUDIT COLUMN: Data lineage column populated by Transform Lambda
    columns {
      name = "filename"
      type = "string"
    }
  }

  # Partition Key: Tells Athena that data is physically partitioned by 'country' in S3 subdirectories
  partition_keys {
    name = "country"
    type = "string"
  }
}