# VCF Normalisation Pipeline

Serverless pipeline that normalises VCF files using `bcftools norm`. Deployed as a Lambda container image triggered by S3 uploads.

## Architecture

```
S3 (input/)  →  S3 Event Notification  →  Lambda (bcftools container)  →  S3 (output/)
```

Each of the 7 groups deploys the same Terraform module into their own AWS account.

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform >= 1.5
- Docker (for building the Lambda image)
- An S3 bucket with the reference genome (`.fa` + `.fa.fai`)

## Setup

### 1. Build and push the container image

```bash
# Build
docker build -t vcf-normalisation .

# Tag and push to ECR (after Terraform creates the repo)
aws ecr get-login-password | docker login --username AWS --password-stdin <account_id>.dkr.ecr.<region>.amazonaws.com
docker tag vcf-normalisation:latest <ecr_repo_url>:latest
docker push <ecr_repo_url>:latest
```

### 2. Deploy infrastructure

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your account-specific values
terraform init
terraform apply
```

### 3. Upload a VCF to trigger normalisation

```bash
aws s3 cp sample.vcf.gz s3://<input-bucket>/input/sample.vcf.gz
# The normalised file will appear at s3://<input-bucket>/output/sample.vcf.gz
```

### 4. Manual re-processing

```bash
./scripts/invoke.sh <bucket> input/sample.vcf.gz
```

## Configuration

See `terraform/variables.tf` for all configurable options. Key variables:

| Variable | Description | Default |
|---|---|---|
| `input_bucket_name` | S3 bucket for VCF uploads | (required) |
| `genome_ref_bucket` | S3 bucket with reference genome | (required) |
| `genome_ref_key` | S3 key for the `.fa` file | (required) |
| `lambda_memory_mb` | Lambda memory | 2048 |
| `lambda_timeout` | Lambda timeout (seconds) | 600 |

## Testing

```bash
pytest tests/
```

## Normalisation command

The pipeline runs:

```bash
bcftools norm -f genome.fa -m -any --keep-sum AD input.vcf.gz -o output.vcf.gz
```

- `-m -any` — split multiallelic sites into biallelic records
- `--keep-sum AD` — maintain the allelic depth sum when splitting
- `-f genome.fa` — left-align and normalise indels against the reference
