terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-2"
}

data "aws_s3_bucket" "input" {
  bucket = var.input_bucket_name
}

# ---------------------------------------------------------------------------
# ECR Repository — shared across all genome configs (same container image)
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "this" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep only the last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# ---------------------------------------------------------------------------
# One Lambda + IAM role per genome config
# ---------------------------------------------------------------------------

module "normaliser" {
  for_each = { for cfg in var.genome_configs : cfg.name => cfg }

  source = "./modules/vcf_normaliser"

  project_name                = var.project_name
  name                        = each.value.name
  input_bucket_arn            = data.aws_s3_bucket.input.arn
  input_prefix                = each.value.input_prefix
  output_prefix               = each.value.output_prefix
  genome_ref_bucket           = each.value.genome_ref_bucket
  genome_ref_key              = each.value.genome_ref_key
  lambda_memory_mb            = var.lambda_memory_mb
  lambda_timeout              = var.lambda_timeout
  lambda_ephemeral_storage_mb = var.lambda_ephemeral_storage_mb
  ecr_image_uri               = "${aws_ecr_repository.this.repository_url}:${var.ecr_image_tag}"
  extra_s3_prefixes           = each.value.extra_s3_prefixes
  tags                        = var.tags
}

# ---------------------------------------------------------------------------
# S3 Event Notification — single resource covers all genome configs
# S3 only permits one aws_s3_bucket_notification per bucket; dynamic blocks
# generate one trigger block per (genome_config × file_suffix) combination.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_notification" "input" {
  bucket = data.aws_s3_bucket.input.id

  dynamic "lambda_function" {
    for_each = {
      for pair in flatten([
        for cfg in var.genome_configs : [
          { key = "${cfg.name}-vcfgz", name = cfg.name, prefix = cfg.input_prefix, suffix = ".vcf.gz" },
          { key = "${cfg.name}-vcf",   name = cfg.name, prefix = cfg.input_prefix, suffix = ".vcf" },
        ]
      ]) : pair.key => pair
    }

    content {
      lambda_function_arn = module.normaliser[lambda_function.value.name].lambda_function_arn
      events              = ["s3:ObjectCreated:*"]
      filter_prefix       = lambda_function.value.prefix
      filter_suffix       = lambda_function.value.suffix
    }
  }

  # Lambda permissions must exist before S3 can register the notification
  depends_on = [module.normaliser]
}
