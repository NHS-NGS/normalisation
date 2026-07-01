output "lambda_function_arn" {
  description = "ARN of the normalisation Lambda function"
  value       = aws_lambda_function.normalise.arn
}

output "lambda_function_name" {
  description = "Name of the normalisation Lambda function"
  value       = aws_lambda_function.normalise.function_name
}
