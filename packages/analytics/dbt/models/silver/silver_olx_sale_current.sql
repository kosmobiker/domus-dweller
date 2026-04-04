with ranked as (
  select
    *,
    row_number() over (
      partition by source_listing_id
      order by snapshot_date desc, source_url desc
    ) as row_num
  from {{ ref('stg_olx_sale_bronze') }}
)

select
  *
except (row_num)
from ranked
where row_num = 1
