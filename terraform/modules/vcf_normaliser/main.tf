data "aws_caller_identity" "current" {}

locals {
  resource_name = "${var.project_name}-${var.name}"
}

# ---------------------------------------------------------------------------
# IAM Role for Lambda
# ---------------------------------------------------------------------------

resource "aws_iam_role" "lambda" {
  name = "${local.resource_name}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "${local.resource_name}-s3-access"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadInputBucket"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = concat(
          ["${var.input_bucket_arn}/${var.input_prefix}*"],
          [for p in var.extra_s3_prefixes : "${var.input_bucket_arn}/${p.read_prefix}*"],
        )
      },
      {
        Sid    = "WriteOutputBucket"
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = concat(
          ["${var.input_bucket_arn}/${var.output_prefix}*"],
          [for p in var.extra_s3_prefixes : "${var.input_bucket_arn}/${p.write_prefix}*"],
        )
      },
      {
        Sid    = "ReadGenomeRef"
        Effect = "Allow"
        Action = ["s3:GetObject"]
        Resource = [
          "arn:aws:s3:::${var.genome_ref_bucket}/${var.genome_ref_key}",
          "arn:aws:s3:::${var.genome_ref_bucket}/${var.genome_ref_key}.fai",
          "arn:aws:s3:::${var.genome_ref_bucket}/${var.genome_ref_key}.gzi",
        ]
      },
    ]
  })
}

# ---------------------------------------------------------------------------
# Lambda Function
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "normalise" {
  function_name = local.resource_name
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = var.ecr_image_uri
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory_mb

  ephemeral_storage {
    size = var.lambda_ephemeral_storage_mb
  }

  environment {
    variables = {
      GENOME_REF_BUCKET = var.genome_ref_bucket
      GENOME_REF_KEY    = var.genome_ref_key
      OUTPUT_PREFIX     = var.output_prefix
    }
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Lambda Permission (allows S3 to invoke this function)
# ---------------------------------------------------------------------------

resource "aws_lambda_permission" "s3" {
  statement_id   = "AllowS3Invoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.normalise.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = var.input_bucket_arn
  source_account = data.aws_caller_identity.current.account_id
}
