# VCF Normalisation Pipeline - Memory

## Project Structure
- `lambda/handler.py` — Lambda entry point (bcftools norm)
- `scripts/integration_test.sh` — Integration test (invoke Lambda, compare with bcftools isec)
- `scripts/invoke.sh` — Manual invocation helper
- `tests/test_handler.py` — Unit tests (pytest, uses env vars before import)
- `terraform/main.tf` — Infrastructure (ECR, Lambda, S3, IAM)
- `terraform/variables.tf` — Terraform variables
- `terraform/terraform.tfvars.example` — Example tfvars
- `eda_haemonc_v3_norm.py` — EDA script for haemonc v3 variant store
- `haemonc_v3_norm_eda.ipynb` / `.html` — EDA notebook and HTML export

## Key Architecture Decisions
- Output path derived from input key: replaces last `/input/` with `/output/` (rfind logic)
- `extra_s3_prefixes` variable grants Lambda access to non-production S3 prefixes (e.g. test/)
- Integration test uses async Lambda invocation (`--invocation-type Event`) with polling
- Example bucket names: `my-vcf-data`, `my-reference-genomes`

## GitHub
- Repo: `NHS-NGS/normalisation` (transferred: `woook` → `eastgenomics` → `NHS-NGS`)
- Remote URL updated to `https://github.com/NHS-NGS/normalisation.git`
- CodeRabbit bot reviews PRs automatically
- PRs are squash-merged (causes `git branch -d` to fail; use `-D` for local cleanup)

## Conventions & Preferences
- No Co-Authored-By Claude lines in commits
- PEP8 with max-line-length=100
- `tests/test_handler.py` has intentional late import (noqa: E402) — env vars must be set first
- Terraform validates trailing slashes on all S3 prefix variables
- `.terraform.lock.hcl` is gitignored

## Common Pitfalls
- AWS credentials expire frequently — check with `aws sts get-caller-identity` before terraform/lambda ops
- Merging Terraform code to GitHub does NOT update AWS — must `terraform apply`
- Lambda container image must be rebuilt+pushed for handler code changes to take effect
- Async Lambda invocations (`Event` type) fail silently — check CloudWatch logs for errors
- `aws logs tail` with `--filter-pattern "ERROR"` is useful for diagnosing Lambda failures

## Session Records
- [Credit matrix 2026-04-15](credit_2026-04-15.md) — Contribution matrix for haemonc variant store + EDA session

## Memory Files
- [AWS infrastructure — accounts and resources](project_aws_infrastructure.md) — AWS account IDs, profiles, key resource ARNs
- [HealthOmics variant store — haemonc panel v3](project_healthomics_variant_store.md) — Store details, Athena views, EDA files
- [Lambda operational patterns](feedback_lambda_operations.md) — Stop/re-trigger/monitor Lambda
- [Duplicate specimen detection pattern](feedback_s3_deduplication.md) — Find and remove S3 VCF duplicates before import
- [Jira and Confluence references](reference_jira_confluence.md) — EBH, DI projects; DV space; key page URLs
