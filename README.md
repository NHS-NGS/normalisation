# VCF Normalisation Pipeline

Serverless pipeline that normalises VCF files using `bcftools norm`. Deployed as a Lambda container image triggered by S3 uploads.

## Architecture

```text
S3 (input/<genome>/)  →  S3 Event Notification  →  Lambda (bcftools container)  →  S3 (output/<genome>/)
```

Each of the 7 groups deploys the same Terraform module into their own AWS account. A single deployment can serve **multiple reference genomes** — each genome gets its own Lambda function and IAM role, all sharing one ECR repository and one S3 bucket notification.

## Prerequisites

- AWS CLI v2 configured with credentials for the target account
- Terraform >= 1.5
- Docker
- An existing S3 bucket for VCF uploads (the "input bucket")
- A reference genome uploaded to an S3 bucket — either uncompressed (`.fa` + `.fa.fai`) or bgzipped (`.fa.gz` + `.fa.gz.fai` + `.fa.gz.gzi`)

## Deployment

Deployment is a two-pass process: Terraform creates the ECR repository first, then you push the container image and apply again to update the Lambda.

Before starting, ensure your AWS credentials are valid and not expired:

```bash
aws sts get-caller-identity
```

If using SSO, run `aws sso login` first. Terraform and the AWS CLI both require active credentials for every step below.

### Step 1 — Configure Terraform variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your account-specific values. The `genome_configs` list contains one entry per reference genome. Single-genome accounts supply one entry; add more entries to enable additional genomes:

```hcl
input_bucket_name = "my-vcf-data"

genome_configs = [
  {
    name              = "grch38"
    input_prefix      = "input/grch38/"
    output_prefix     = "output/grch38/"
    genome_ref_bucket = "my-reference-genomes"
    genome_ref_key    = "genomes/GRCh38/genome.fa.gz"
  },
]
```

Each entry creates a separate Lambda function named `<project_name>-<name>` (e.g. `vcf-normalisation-grch38`). The `name` field is a short identifier used in resource names — it can be any unique string (e.g. `grch38`, `hg19`, `grch37`).

The following index files must exist alongside each genome in the same bucket:

- **Uncompressed genome** (`.fa`): requires `.fa.fai`
- **Bgzipped genome** (`.fa.gz`): requires `.fa.gz.fai` and `.fa.gz.gzi`

The pipeline detects the format from the file extension and downloads the appropriate indices automatically.

### Step 2 — Create the ECR repository

```bash
terraform init
terraform apply -target=aws_ecr_repository.this -target=aws_ecr_lifecycle_policy.this
```

This creates the ECR repository without attempting to create the Lambda (which needs the image to exist first).

Grab the ECR repository URL from the output:

```bash
ECR_REPO=$(terraform output -raw ecr_repository_url)
```

### Step 3 — Build and push the container image

> **Note:** Docker commands require root privileges. Prefix with `sudo` or run as root.

```bash
# From the project root
cd ..

# Build the image
sudo docker build -t vcf-normalisation .

# Authenticate Docker to ECR
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)
aws ecr get-login-password --region "$REGION" \
  | sudo docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

# Tag and push
sudo docker tag vcf-normalisation:latest "$ECR_REPO:latest"
sudo docker push "$ECR_REPO:latest"
```

### Step 4 — Full Terraform apply (deploys Lambda)

```bash
cd terraform
terraform apply
```

This creates one Lambda function and IAM role per `genome_configs` entry, plus the shared S3 event notification.

### Updating the Lambda

When you update the handler code or bcftools version:

```bash
sudo docker build -t vcf-normalisation .
sudo docker tag vcf-normalisation:latest "$ECR_REPO:latest"
sudo docker push "$ECR_REPO:latest"

# Force all genome Lambdas to pick up the new image
terraform output -json lambda_function_names \
  | jq -r '.[]' \
  | xargs -I{} aws lambda update-function-code \
      --function-name {} \
      --image-uri "$ECR_REPO:latest"
```

#### Updating from a different machine

If you are running these steps on a machine that has no local Terraform state (e.g. a fresh clone), import the existing resources before applying. The resources are now keyed by genome name, so substitute `<name>` with your `genome_configs` entry name (e.g. `grch38`):

```bash
cd terraform
terraform import aws_ecr_repository.this vcf-normalisation
terraform import 'module.normaliser["<name>"].aws_iam_role.lambda' vcf-normalisation-<name>-lambda
terraform import 'module.normaliser["<name>"].aws_lambda_function.normalise' vcf-normalisation-<name>
terraform import 'module.normaliser["<name>"].aws_lambda_permission.s3' vcf-normalisation-<name>/AllowS3Invoke
```

Replace `vcf-normalisation` with your `project_name` if you changed the default. After importing, run `terraform apply` as normal.

### Tearing down

```bash
cd terraform
terraform destroy
```

## Running the normalisation

### Automatic — upload a file

Upload a VCF to the genome-specific `input/` prefix in your bucket. Both gzipped (`.vcf.gz`) and uncompressed (`.vcf`) inputs are accepted. The Lambda triggers automatically:

```bash
aws s3 cp sample.vcf.gz s3://my-vcf-data/input/grch38/sample.vcf.gz
```

The normalised file appears under the corresponding `output/` prefix. Output is always bgzipped (`.vcf.gz`), regardless of whether the input was compressed:

```bash
# Check it arrived
aws s3 ls s3://my-vcf-data/output/grch38/sample.vcf.gz

# Download it
aws s3 cp s3://my-vcf-data/output/grch38/sample.vcf.gz normalised_sample.vcf.gz
```

### Manual — re-process a file

Use the helper script to re-invoke a specific Lambda. The `FUNCTION_NAME` env var selects which genome's Lambda to use (defaults to `vcf-normalisation`):

```bash
FUNCTION_NAME=vcf-normalisation-grch38 ./scripts/invoke.sh my-vcf-data input/grch38/sample.vcf.gz
```

Or invoke directly with the AWS CLI:

```bash
aws lambda invoke \
  --function-name vcf-normalisation-grch38 \
  --payload '{"bucket": "my-vcf-data", "key": "input/grch38/sample.vcf.gz"}' \
  --cli-binary-format raw-in-base64-out \
  /dev/stdout
```

### Monitoring

List all Lambda function names from the Terraform output:

```bash
terraform -chdir=terraform output -json lambda_function_names
# {"grch38": "vcf-normalisation-grch38", "hg19": "vcf-normalisation-hg19"}
```

View Lambda logs in CloudWatch:

```bash
aws logs tail "/aws/lambda/vcf-normalisation-grch38" --follow
```

## Configuration

See `terraform/variables.tf` for all options. Key variables:

| Variable | Description | Default |
|---|---|---|
| `input_bucket_name` | S3 bucket for VCF uploads | (required) |
| `genome_configs` | List of genome/prefix configurations (see below) | (required) |
| `lambda_memory_mb` | Lambda memory (MB) — applies to all Lambdas | 2048 |
| `lambda_timeout` | Lambda timeout (seconds) — applies to all Lambdas | 600 |
| `lambda_ephemeral_storage_mb` | Ephemeral `/tmp` storage (MB) — applies to all Lambdas | 4096 |
| `ecr_image_tag` | Container image tag to deploy | `latest` |

### `genome_configs` fields

| Field | Description |
|---|---|
| `name` | Short identifier used in resource names (e.g. `grch38`, `hg19`) — must be unique |
| `input_prefix` | S3 prefix to watch for incoming VCFs (must end with `/`) |
| `output_prefix` | S3 prefix where normalised VCFs are written (must end with `/`) |
| `genome_ref_bucket` | S3 bucket containing the reference FASTA |
| `genome_ref_key` | S3 key for the FASTA (`.fai` must be at `<key>.fai`) |
| `extra_s3_prefixes` | Optional list of `{read_prefix, write_prefix}` pairs (e.g. for integration testing) |

## Testing

### Unit tests

```bash
pytest tests/
```

### Integration tests

The integration test script invokes the Lambda on all test VCFs stored in S3 and compares outputs against expected files using three levels of comparison:

1. **`bcftools stats`** — record count sanity check (catches obvious mismatches early)
2. **`bcftools isec`** — site-level comparison (CHROM/POS/REF/ALT identity)
3. **`bcftools query` + `diff`** — field-level comparison (GT, DP, AD values — catches e.g. incorrect AD splits after multiallelic decomposition)

A file passes only if all three tiers pass. After the run, a markdown report is written to `integration_report.md` (configurable via `REPORT_FILE`) with a results table, failure details, and full diffs in an appendix.

Test data lives under separate S3 prefixes (`test/input/`, `test/expected/`), completely separate from the production `input/` → `output/` flow.

#### Local dependencies

The integration test script runs `bcftools` locally to compare output and expected files. You need:

- **bcftools** (>= 1.13) — for `bcftools stats`, `bcftools isec`, `bcftools query`, `bcftools index`, and `bcftools view`
- **bgzip** (from htslib) — bundled with most bcftools installations
- **jq** — used to construct the Lambda invocation payload
- **AWS CLI v2** — for S3 downloads and Lambda invocation
- **diff** — standard Unix diff (coreutils)

On Ubuntu/Debian:

```bash
sudo apt install bcftools jq
```

On macOS (Homebrew):

```bash
brew install bcftools jq
```

AWS CLI v2 must be installed separately — see the [AWS CLI installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html). `diff` is preinstalled on all standard Linux and macOS systems.

#### Setup

1. Grant the Lambda access to the test prefixes by adding `extra_s3_prefixes` to the relevant entry in `genome_configs` and running `terraform apply`:

```hcl
genome_configs = [
  {
    name              = "grch38"
    input_prefix      = "input/grch38/"
    output_prefix     = "output/grch38/"
    genome_ref_bucket = "my-reference-genomes"
    genome_ref_key    = "genomes/GRCh38/genome.fa.gz"
    extra_s3_prefixes = [
      {
        read_prefix  = "test/input/"
        write_prefix = "test/output/"
      }
    ]
  },
]
```

2. Upload test inputs and expected outputs to S3:

```bash
aws s3 sync ./test_vcfs/ s3://my-vcf-data/test/input/
aws s3 sync ./expected_vcfs/ s3://my-vcf-data/test/expected/
```

#### Running

```bash
FUNCTION_NAME=vcf-normalisation-grch38 ./scripts/integration_test.sh <bucket> [input_prefix] [expected_prefix]
```

| Parameter | Source | Default |
|---|---|---|
| `BUCKET` | Arg 1 | (required) |
| `INPUT_PREFIX` | Arg 2 | `test/input/` |
| `EXPECTED_PREFIX` | Arg 3 | `test/expected/` |
| `FUNCTION_NAME` | Env var | `vcf-normalisation` |
| `MAX_PARALLEL` | Env var | `10` |
| `POLL_TIMEOUT` | Env var | `120` (seconds per file) |
| `REPORT_FILE` | Env var | `integration_report.md` |

Example:

```bash
MAX_PARALLEL=20 FUNCTION_NAME=vcf-normalisation-grch38 ./scripts/integration_test.sh my-vcf-data
```

## AWS permissions

### Deployment

The user or CI role running `terraform apply` and pushing the container image needs:

| Service | Permissions | Reason |
|---------|-------------|--------|
| ECR | `ecr:CreateRepository`, `ecr:DeleteRepository`, `ecr:PutLifecyclePolicy`, `ecr:DescribeRepositories`, `ecr:ListTagsForResource`, `ecr:TagResource` | Create and manage the container repository |
| ECR (image push) | `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload` | Authenticate Docker and push images |
| Lambda | `lambda:CreateFunction`, `lambda:UpdateFunctionCode`, `lambda:UpdateFunctionConfiguration`, `lambda:DeleteFunction`, `lambda:GetFunction`, `lambda:AddPermission`, `lambda:RemovePermission`, `lambda:TagResource`, `lambda:ListTags` | Create and update Lambda functions |
| IAM | `iam:CreateRole`, `iam:DeleteRole`, `iam:AttachRolePolicy`, `iam:DetachRolePolicy`, `iam:PutRolePolicy`, `iam:DeleteRolePolicy`, `iam:GetRole`, `iam:GetRolePolicy`, `iam:PassRole`, `iam:ListRolePolicies`, `iam:ListAttachedRolePolicies`, `iam:ListInstanceProfilesForRole`, `iam:TagRole` | Manage Lambda execution roles |
| S3 | `s3:GetBucketNotification`, `s3:PutBucketNotification` | Configure the S3 event trigger |
| S3 (data source) | `s3:ListBucket`, `s3:GetBucketLocation` | Terraform data source to reference the existing bucket |
| STS | `sts:GetCallerIdentity` | Terraform uses this to determine the account ID |

### Runtime (day-to-day use)

Users who upload VCFs or manually invoke the Lambda need:

| Service | Permissions | Reason |
|---------|-------------|--------|
| S3 | `s3:PutObject` on `input/<genome>/*` | Upload input VCFs |
| S3 | `s3:GetObject` on `output/<genome>/*` | Download normalised results |
| S3 | `s3:ListBucket` | List objects in input/output prefixes |
| Lambda | `lambda:InvokeFunction` | Manual invocation via `invoke.sh` or AWS CLI |
| CloudWatch Logs | `logs:FilterLogEvents`, `logs:GetLogEvents` | View Lambda logs for monitoring |

### Integration testing

In addition to the runtime permissions above, the integration test script needs:

| Service | Permissions | Reason |
|---------|-------------|--------|
| S3 | `s3:GetObject` on `test/input/*`, `test/expected/*`, `test/output/*` | Download test inputs, expected files, and Lambda outputs |
| S3 | `s3:DeleteObject` on `test/output/*` | Clean previous test outputs before each run |
| S3 | `s3:ListBucket` (with prefix `test/input/`) | Discover test VCF files |
| Lambda | `lambda:InvokeFunction` (async) | Invoke the Lambda for each test file |

## Normalisation command

The pipeline runs:

```bash
bcftools norm -Oz -f genome.fa -m -any --keep-sum AD input.vcf.gz -o output.vcf.gz
```

- `-m -any` — split multiallelic sites into biallelic records
- `--keep-sum AD` — maintain the allelic depth sum when splitting
- `-f genome.fa` — left-align and normalise indels against the reference

## Further reading

See [technical_walkthrough.md](technical_walkthrough.md) for a detailed walkthrough of the codebase including the handler source, Dockerfile, Terraform resources, and test output.
