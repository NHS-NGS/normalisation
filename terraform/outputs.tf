output "lambda_function_arns" {
  description = "ARN of each normalisation Lambda function, keyed by genome config name"
  value       = { for k, v in module.normaliser : k => v.lambda_function_arn }
}

output "lambda_function_names" {
  description = "Name of each normalisation Lambda function, keyed by genome config name"
  value       = { for k, v in module.normaliser : k => v.lambda_function_name }
}

output "ecr_repository_url" {
  description = "URL of the shared ECR repository for the Lambda container image"
  value       = aws_ecr_repository.this.repository_url
}

output "input_bucket_arn" {
  description = "ARN of the input S3 bucket"
  value       = data.aws_s3_bucket.input.arn
}
