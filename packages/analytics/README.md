# packages/analytics

This package will contain:

- H3 assignment logic
- daily rollups
- median and quantile calculations
- trend computation
- score and ranking experiments

Keep analytics deterministic and reproducible from raw observations.

## dbt Project

dbt transformation project for BigQuery is in:

- `packages/analytics/dbt`

It defines Bronze -> Silver -> Gold SQL models with separate rent/sale tracks.
