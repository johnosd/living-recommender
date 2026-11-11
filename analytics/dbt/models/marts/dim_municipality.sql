{{ config(materialized='external', format='parquet', location=env_var('CAOP_BUILD_DIR', '.data/ci') ~ '/lake/silver/dim_municipality/data.parquet') }}

select
    dico,
    official_name,
    normalized_name,
    district_or_island,
    autonomous_region,
    area_km2,
    representative_lat,
    representative_lon,
    caop_version,
    source_run_id,
    reference_period,
    license_id,
    collected_at_utc,
    processed_at_utc
from {{ ref('stg_caop_municipalities') }}
