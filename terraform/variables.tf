variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "vcf-normalisation"
}

variable "input_bucket_name" {
  description = "Name of the S3 bucket where input VCF files are uploaded"
  type        = string
}

variable "input_prefix" {
  description = "S3 key prefix that triggers the Lambda (must end with /)"
  type        = string
  default     = "input/"
}

variable "output_prefix" {
  description = "S3 key prefix where normalised VCFs are written"
  type        = string
  default     = "output/"
}

variable "genome_ref_bucket" {
  description = "S3 bucket containing the reference genome (.fa and .fa.fai)"
  type        = string
}

variable "genome_ref_key" {
  description = "S3 key for the reference genome FASTA file (the .fai index must be at <key>.fai)"
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

variable "ecr_image_tag" {
  description = "Tag of the container image in ECR to deploy"
  type        = string
  default     = "latest"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
