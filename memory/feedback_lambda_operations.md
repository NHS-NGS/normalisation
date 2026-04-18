---
name: Lambda operational patterns
description: Patterns for stopping, re-triggering, and monitoring the vcf-normalisation Lambda
type: feedback
originSessionId: a9527a11-0aa9-4c3f-8d3a-cfa40bee725a
---
## Stopping in-flight Lambda jobs

Lambda cannot kill in-flight executions. Set reserved concurrency to 0 to throttle immediately:

```bash
aws lambda put-function-concurrency \
  --function-name vcf-normalisation \
  --reserved-concurrent-executions 0 \
  --profile testbox-admin
```

Restore with `delete-function-concurrency` once issue is resolved.

**Why:** Wrong genome reference files were uploaded; needed to stop further invocations immediately.

## Re-triggering existing S3 files without re-uploading

Lambda supports a manual invocation payload `{"bucket": "...", "key": "..."}`. Loop over S3 files:

```bash
aws s3 ls "s3://${BUCKET}/input/" --recursive --profile testbox-admin \
  | awk '{print $4}' | while read key; do
    aws lambda invoke --function-name vcf-normalisation \
      --invocation-type Event \
      --payload "{\"bucket\": \"${BUCKET}\", \"key\": \"${key}\"}" \
      --cli-binary-format raw-in-base64-out \
      --profile testbox-admin /tmp/resp.json
  done
```

## Log monitoring

```bash
aws logs tail "/aws/lambda/vcf-normalisation" --follow --profile testbox-admin
```

`$FUNCTION_NAME` must be set explicitly — an unset variable gives `InvalidParameterException`.

**How to apply:** Use these patterns whenever Lambda jobs need operational intervention.
