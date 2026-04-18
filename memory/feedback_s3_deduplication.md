---
name: Duplicate specimen detection pattern
description: Pattern for finding and removing duplicate specimens from S3 VCF buckets
type: feedback
originSessionId: a9527a11-0aa9-4c3f-8d3a-cfa40bee725a
---
## Pattern

VCF filenames follow: `<numeric_id>-<specimen_id>-<run_id>-<panel>-<sex>-<suffix>.vcf.gz`

Specimen ID is the **second** `-`-delimited field. Duplicate specimens have the same specimen ID
but different run IDs (e.g. same sample reprocessed in a newer run).

```bash
# Find duplicate specimen IDs
aws s3api list-objects-v2 --bucket BUCKET --prefix PREFIX \
  --query 'Contents[?ends_with(Key, `vcf.gz`)].[Key]' \
  --output text --profile PROFILE \
  | awk -F'/' '{print $NF}' | cut -d'-' -f2 | sort | uniq -d
```

## Run ID ordering

Run IDs encode the year and run number: `25NGSHO63` = year 25, run 63.
To determine which is newer: higher run number within a year is newer; year 26 > year 25.
Cross-year comparison: `26NGSHO1` > `25NGSHO77`.

**Keep the newer run (higher run number / later year). Delete the older.**

## Bulk delete

```bash
aws s3api delete-objects --bucket BUCKET --profile PROFILE \
  --delete '{"Objects": [{"Key": "prefix/filename.vcf.gz"}, ...], "Quiet": false}'
```

`"Quiet": false` returns confirmation of every deleted key.

**Why:** Before importing VCFs into a HealthOmics variant store, duplicates must be removed —
the variant store will contain the same sampleid twice otherwise, corrupting frequency counts.

**How to apply:** Run duplicate check before any variant store import or batch processing job.
