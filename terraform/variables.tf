variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "vcf-normalisation"
}

variable "input_bucket_name" {
  description = "Name of the S3 bucket where input VCF files are uploaded"
  type        = string
}

variable "genome_configs" {
  description = <<-EOT
    One entry per genome/prefix pair. Each entry gets its own Lambda function and
    IAM role, named <project_name>-<name>. All entries share the same ECR repository.

    Single-genome accounts (the common case) just supply one item in the list.
  EOT
  type = list(object({
    name              = string # short id used in resource names, e.g. "grch38"
    name_override     = optional(string, null) # preserve existing resource names when migrating
    input_prefix      = string # S3 prefix to watch for incoming VCFs (must end with /)
    output_prefix     = string # S3 prefix to write normalised VCFs (must end with /)
    genome_ref_bucket = string # S3 bucket containing the reference FASTA
    genome_ref_key    = string # S3 key for the FASTA (.fai must be at <key>.fai)
    extra_s3_prefixes = optional(list(object({
      read_prefix  = string
      write_prefix = string
    })), [])
  }))

  validation {
    condition     = length(var.genome_configs) >= 1
    error_message = "At least one genome_config entry is required."
  }

  validation {
    condition     = alltrue([for cfg in var.genome_configs : can(regex("/$", cfg.input_prefix))])
    error_message = "Each input_prefix must end with a trailing slash."
  }

  validation {
    condition     = alltrue([for cfg in var.genome_configs : can(regex("/$", cfg.output_prefix))])
    error_message = "Each output_prefix must end with a trailing slash."
  }

  validation {
    condition     = length(var.genome_configs) == length(distinct([for cfg in var.genome_configs : cfg.name]))
    error_message = "Each genome_config name must be unique."
  }

  validation {
    condition     = alltrue([for cfg in var.genome_configs : can(regex("^[a-zA-Z0-9_-]+$", cfg.name))])
    error_message = "Each genome_config name must contain only letters, numbers, hyphens, and underscores (used in Lambda/IAM resource names)."
  }

  validation {
    condition     = alltrue([for cfg in var.genome_configs : cfg.name_override == null || can(regex("^[a-zA-Z0-9_-]+$", cfg.name_override))])
    error_message = "Each genome_config name_override must contain only letters, numbers, hyphens, and underscores."
  }

  validation {
    condition     = alltrue([for cfg in var.genome_configs : cfg.input_prefix != cfg.output_prefix])
    error_message = "input_prefix and output_prefix must differ for each genome_config — identical prefixes would cause the Lambda to re-trigger on its own output."
  }

  validation {
    condition     = length(var.genome_configs) == length(distinct([for cfg in var.genome_configs : cfg.input_prefix]))
    error_message = "Each genome_config input_prefix must be unique — duplicate prefixes would cause the same upload to be processed by multiple Lambdas."
  }

  validation {
    condition     = length(var.genome_configs) == length(distinct([for cfg in var.genome_configs : cfg.output_prefix]))
    error_message = "Each genome_config output_prefix must be unique — shared output prefixes allow genomes to overwrite each other's normalised files."
  }

  validation {
    condition = alltrue(flatten([
      for cfg in var.genome_configs : [
        for other in var.genome_configs :
        cfg.name == other.name || !startswith(other.input_prefix, cfg.input_prefix)
      ]
    ]))
    error_message = "No input_prefix may be a leading prefix of another input_prefix — overlapping prefixes cause S3 notifications to fire on unintended uploads."
  }

  validation {
    condition = alltrue(flatten([
      for out_cfg in var.genome_configs : [
        for in_cfg in var.genome_configs :
        !startswith(out_cfg.output_prefix, in_cfg.input_prefix)
      ]
    ]))
    error_message = "Each output_prefix must not start with any input_prefix — otherwise normalised files can re-trigger a normaliser."
  }

  validation {
    condition = alltrue(flatten([
      for cfg in var.genome_configs : [
        for p in cfg.extra_s3_prefixes : [
          can(regex("/$", p.read_prefix)),
          can(regex("/$", p.write_prefix)),
        ]
      ]
    ]))
    error_message = "Each extra_s3_prefixes read_prefix and write_prefix must end with a trailing slash."
  }

  validation {
    condition = alltrue(flatten([
      for cfg in var.genome_configs : [
        for p in cfg.extra_s3_prefixes : [
          !can(regex("[*?]", p.read_prefix)),
          !can(regex("[*?]", p.write_prefix)),
        ]
      ]
    ]))
    error_message = "extra_s3_prefixes read_prefix and write_prefix must not contain IAM wildcard characters (* or ?)."
  }
}

variable "lambda_memory_mb" {
  description = "Memory allocated to each Lambda function in MB"
  type        = number
  default     = 2048
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 600
}

variable "lambda_ephemeral_storage_mb" {
  description = "Ephemeral storage (/tmp) for each Lambda in MB"
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
