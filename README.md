# VCF Normalisation Pipeline

Serverless pipeline that normalises VCF files using `bcftools norm`. Deployed as a Lambda container image triggered by S3 uploads.

## Architecture

```
S3 (input/)  →  S3 Event Notification  →  Lambda (bcftools container)  →  S3 (output/)
```

Each of the 7 groups deploys the same Terraform module into their own AWS account.

## Prerequisites

- AWS CLI v2 configured with credentials for the target account
- Terraform >= 1.5
- Docker
- An existing S3 bucket for VCF uploads (the "input bucket")
- A reference genome (`.fa`) and its fasta index (`.fa.fai`) uploaded to an S3 bucket

## Deployment

Deployment is a two-pass process: Terraform creates the ECR repository first, then you push the container image and apply again to update the Lambda.

### Step 1 — Configure Terraform variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your account-specific values:

```hcl
input_bucket_name = "my-group-vcf-data"
genome_ref_bucket = "my-group-reference-genomes"
genome_ref_key    = "genomes/hg38/genome.fa"
```

The reference genome index must exist at `<genome_ref_key>.fai` in the same bucket (e.g. `genomes/hg38/genome.fa.fai`).

### Step 2 — First Terraform apply (creates ECR repo)

```bash
terraform init
terraform apply
```

This will fail on the Lambda resource because no container image exists in ECR yet. That's expected — it creates the ECR repository, IAM roles, and S3 notification configuration.

Grab the ECR repository URL from the output:

```bash
ECR_REPO=$(terraform output -raw ecr_repository_url)
```

### Step 3 — Build and push the container image

```bash
# From the project root
cd ..

# Build the image
docker build -t vcf-normalisation .

# Authenticate Docker to ECR
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Tag and push
docker tag vcf-normalisation:latest "$ECR_REPO:latest"
docker push "$ECR_REPO:latest"
```

### Step 4 — Second Terraform apply (deploys Lambda)

```bash
cd terraform
terraform apply
```

This time the Lambda function will be created successfully using the image you just pushed.

### Updating the Lambda

When you update the handler code or bcftools version:

```bash
docker build -t vcf-normalisation .
docker tag vcf-normalisation:latest "$ECR_REPO:latest"
docker push "$ECR_REPO:latest"

# Force Lambda to pick up the new image
aws lambda update-function-code \
  --function-name vcf-normalisation \
  --image-uri "$ECR_REPO:latest"
```

### Tearing down

```bash
cd terraform
terraform destroy
```

## Running the normalisation

### Automatic — upload a file

Upload a compressed VCF to the `input/` prefix in your bucket. The Lambda triggers automatically:

```bash
aws s3 cp sample.vcf.gz s3://my-group-vcf-data/input/sample.vcf.gz
```

The normalised file appears at the `output/` prefix:

```bash
# Check it arrived
aws s3 ls s3://my-group-vcf-data/output/sample.vcf.gz

# Download it
aws s3 cp s3://my-group-vcf-data/output/sample.vcf.gz normalised_sample.vcf.gz
```

### Manual — re-process a file

Use the helper script to re-invoke the Lambda for a specific file:

```bash
./scripts/invoke.sh my-group-vcf-data input/sample.vcf.gz
```

Or invoke directly with the AWS CLI:

```bash
aws lambda invoke \
  --function-name vcf-normalisation \
  --payload '{"bucket": "my-group-vcf-data", "key": "input/sample.vcf.gz"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### Monitoring

View Lambda logs in CloudWatch:

```bash
aws logs tail /aws/lambda/vcf-normalisation --follow
```

Check for invocation errors:

```bash
aws lambda get-function --function-name vcf-normalisation \
  --query 'Configuration.{State:State,LastModified:LastModified}'
```

## Configuration

See `terraform/variables.tf` for all options. Key variables:

| Variable | Description | Default |
|---|---|---|
| `input_bucket_name` | S3 bucket for VCF uploads | (required) |
| `genome_ref_bucket` | S3 bucket with reference genome | (required) |
| `genome_ref_key` | S3 key for the `.fa` file | (required) |
| `input_prefix` | S3 prefix that triggers Lambda | `input/` |
| `output_prefix` | S3 prefix for normalised output | `output/` |
| `lambda_memory_mb` | Lambda memory (MB) | 2048 |
| `lambda_timeout` | Lambda timeout (seconds) | 600 |
| `lambda_ephemeral_storage_mb` | Ephemeral `/tmp` storage (MB) | 4096 |
| `ecr_image_tag` | Container image tag to deploy | `latest` |

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
