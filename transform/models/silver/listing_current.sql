-- depends_on: {{ ref('listing_versions') }}
SELECT * FROM {{ ref('listing_versions') }} WHERE dbt_valid_to IS NULL
