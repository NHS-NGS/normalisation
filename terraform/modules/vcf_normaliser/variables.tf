variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
}

variable "name" {
  description = "Short identifier for this genome config, used as a suffix in resource names (e.g. 'grch38')"
  type        = string
}

variable "input_bucket_arn" {
  description = "ARN of the input S3 bucket"
  type        = string
}

variable "input_prefix" {
  description = "S3 key prefix this Lambda reads from (must end with /)"
  type        = string
}

variable "output_prefix" {
  description = "S3 key prefix this Lambda writes to (must end with /)"
  type        = string
}

variable "genome_ref_bucket" {
  description = "S3 bucket containing the reference genome FASTA"
  type        = string
}

variable "genome_ref_key" {
  description = "S3 key for the reference genome FASTA (.fai must be at <key>.fai)"
  type        = string
}

variable "lambda_memory_mb" {
  description = "Memory allocated to the Lambda function in MB"
  type        = number
  default     = 2048
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 600
}

variable "lambda_ephemeral_storage_mb" {
  description = "Ephemeral storage (/tmp) for the Lambda in MB"
  type        = number
  default     = 4096
}

variable "ecr_image_uri" {
  description = "Full ECR image URI including tag (e.g. 123456789.dkr.ecr.eu-west-2.amazonaws.com/vcf-normalisation:latest)"
  type        = string
}

variable "extra_s3_prefixes" {
  description = "Additional S3 prefix pairs (read/write) for the Lambda, e.g. for integration testing"
  type = list(object({
    read_prefix  = string
    write_prefix = string
  }))
  default = []
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
