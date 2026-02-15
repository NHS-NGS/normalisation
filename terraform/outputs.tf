output "lambda_function_arn" {
  description = "ARN of the normalisation Lambda function"
  value       = aws_lambda_function.normalise.arn
}

output "lambda_function_name" {
  description = "Name of the normalisation Lambda function"
  value       = aws_lambda_function.normalise.function_name
}

output "ecr_repository_url" {
  description = "URL of the ECR repository for the Lambda container image"
  value       = aws_ecr_repository.this.repository_url
}

output "input_bucket_arn" {
  description = "ARN of the input S3 bucket"
  value       = data.aws_s3_bucket.input.arn
}
