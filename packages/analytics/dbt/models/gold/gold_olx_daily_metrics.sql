with base as (
  select
    snapshot_date,
    mode,
    source_listing_id,
    seller_segment,
    price_total,
    price_per_sqm
  from {{ ref('stg_olx_rent_bronze') }}

  union all

  select
    snapshot_date,
    mode,
    source_listing_id,
    seller_segment,
    price_total,
    price_per_sqm
  from {{ ref('stg_olx_sale_bronze') }}
),
aggregated as (
  select
    snapshot_date,
    mode,
    seller_segment,
    count(*) as adverts_count,
    approx_count_distinct(source_listing_id) as listings_unique,
    avg(price_total) as avg_price_total,
    avg(price_per_sqm) as avg_price_per_sqm,
    approx_quantiles(price_total, 100)[offset(50)] as median_price_total,
    approx_quantiles(price_per_sqm, 100)[offset(50)] as median_price_per_sqm
  from base
  group by snapshot_date, mode, seller_segment
)

select *
from aggregated
