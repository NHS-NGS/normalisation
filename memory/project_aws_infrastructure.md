---
name: AWS infrastructure — accounts and resources
description: AWS account names, profiles, and key resource identifiers used in this project
type: project
originSessionId: a9527a11-0aa9-4c3f-8d3a-cfa40bee725a
---
## AWS Accounts

| Account | ID | CLI Profile | Purpose |
|---|---|---|---|
| east-testbox | 212315286023 | `testbox-admin` | VCF normalisation Lambda + input/output S3 |
| eastgenomics | 471112938470 | `main-admin` / `main-healthomics` | HealthOmics variant stores, Athena, S3 reference data |

## Key Resources — east-testbox

- Lambda function: `vcf-normalisation`
- Input/output bucket: `s3://my-vcf-data`
- Reference genome bucket: `s3://my-reference-genomes`

## Key Resources — eastgenomics

- HealthOmics reference store ID: `8433245455`
- Reference genome: GRCh38-GIABv3 (ID: `6062241118`)
- ARN: `arn:aws:omics:eu-west-2:471112938470:referenceStore/8433245455/reference/6062241118`
- Athena results bucket: `s3://003-250913-athena-results/`
- Variant store import service role: `arn:aws:iam::471112938470:role/service-role/OmicsAnalytics-20250914T202155`
- Data catalog: `471112938470` (ARN: `arn:aws:glue:eu-west-2:471112938470:catalog`)
- Athena Lake Formation databases: `egg-variants` (holds gnomAD tables and view resource links)

## How to apply:
Use correct profile per account. `main-healthomics` role for Athena/HealthOmics queries;
`main-admin` for Terraform/S3/Lambda ops on eastgenomics.
