{% snapshot listing_versions %}
{{
    config(
      target_schema='silver',
      unique_key="source || '-' || source_listing_id || '-' || mode",
      strategy='check',
      check_cols=['price_total'],
      invalidate_hard_deletes=True
    )
}}

SELECT * FROM {{ ref('stg_bronze_listings') }}

{% endsnapshot %}
