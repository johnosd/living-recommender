{{ config(materialized='external', format='parquet', location=env_var('CAOP_BUILD_DIR', '.data/ci') ~ '/lake/bronze/stg_caop_municipalities/data.parquet') }}

select
    cast(dico as varchar) as dico,
    cast(official_name as varchar) as official_name,
    cast(normalized_name as varchar) as normalized_name,
    cast(district_or_island as varchar) as district_or_island,
    cast(autonomous_region as varchar) as autonomous_region,
    cast(region as varchar) as region,
    cast(source_crs as varchar) as source_crs,
    geometry_wkb,
    cast(area_km2 as double) as area_km2,
    cast(representative_lat as double) as representative_lat,
    cast(representative_lon as double) as representative_lon,
    cast(caop_version as varchar) as caop_version,
    cast(source_run_id as varchar) as source_run_id,
    cast(reference_period as varchar) as reference_period,
    cast(license_id as varchar) as license_id,
    cast(collected_at_utc as varchar) as collected_at_utc,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('CAOP_PREPARED_DIR', '.data/ci/prepared') }}/municipalities.parquet')
