#!/usr/bin/env bash
#
# Manually invoke the VCF normalisation Lambda for a specific file.
#
# Usage:
#   ./scripts/invoke.sh <bucket> <key>
#
# Example:
#   ./scripts/invoke.sh my-vcf-bucket input/sample.vcf.gz

set -euo pipefail

FUNCTION_NAME="${FUNCTION_NAME:-vcf-normalisation}"

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <bucket> <key>" >&2
    exit 1
fi

BUCKET="$1"
KEY="$2"
PAYLOAD=$(printf '{"bucket": "%s", "key": "%s"}' "$BUCKET" "$KEY")

echo "Invoking ${FUNCTION_NAME} with payload: ${PAYLOAD}"

aws lambda invoke \
    --function-name "$FUNCTION_NAME" \
    --payload "$PAYLOAD" \
    --cli-binary-format raw-in-base64-out \
    /dev/stdout 2>/dev/null | jq .
