---
name: HealthOmics variant store — haemonc panel v3
description: Details of the haemonc panel v3 sentieon variant store created 2026-04-14
type: project
originSessionId: a9527a11-0aa9-4c3f-8d3a-cfa40bee725a
---
## Variant Store

| Field | Value |
|---|---|
| Name | `haemonc_panel_v3_sentieon_250811_260413` |
| Store ID | `c636b4ab0a5c` |
| ARN | `arn:aws:omics:eu-west-2:471112938470:variantStore/haemonc_panel_v3_sentieon_250811_260413` |
| Database | `haemonc_panel_v3_sentieon_250811_260413` |
| Reference genome | GRCh38-GIABv3 (ID: 6062241118) |
| N samples | 2,542 |
| Input date range | 2025-08-11 to 2026-04-13 |
| S3 source | `s3://002-haemonc/panel-v3/sentieon_lambda_normalised/` |
| Jira | DI-3138 |
| Confluence | https://cuhbioinformatics.atlassian.net/wiki/spaces/DV/pages/4639293465/ |

## Athena Access

- Views created in `egg-variants` database (has gnomAD table access)
- `ctas_approach=False` required — `main-healthomics` role lacks `CreateTable` on variant store DB
- HQ view: `haemonc_v3_senti_norm_260413_qual_filtered`
- HQ+gnomAD+AF view: `haemonc_v3_senti_norm_260413_qual_gnomad_filtered`
- Cross-DB reference syntax: `"haemonc_panel_v3_sentieon_250811_260413".haemonc_panel_v3_sentieon_250811_260413`

## EDA

- Script: `eda_haemonc_v3_norm.py`
- Notebook: `haemonc_v3_norm_eda.ipynb` (HTML: `haemonc_v3_norm_eda.html`)
- Previous EDA (v0.1, n=673): `~/Downloads/HaemOnc_v3_sentieon_norm_queries.html`

**Why:** First variant store for haemonc panel v3 normalised VCFs, for use in variant frequency filtering.
**How to apply:** Use `main-healthomics` profile for Athena queries. Views already exist in `egg-variants`.
