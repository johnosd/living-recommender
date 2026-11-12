{{ config(materialized='external', format='parquet', location=env_var('CLIMATE_BUILD_DIR', '.data/ci-climate') ~ '/lake/bronze/stg_climate_daily/data.parquet') }}

select
    cast(source_id as varchar) as source_id,
    cast(dico as varchar) as dico,
    cast(variable as varchar) as variable,
    cast(date as date) as date,
    cast(value as double) as value,
    cast(unit as varchar) as unit,
    cast(model as varchar) as model,
    cast(window_start as date) as window_start,
    cast(window_end as date) as window_end,
    cast(source_run_id as varchar) as source_run_id,
    cast(license_id as varchar) as license_id,
    cast(attribution as varchar) as attribution,
    cast(usage_restriction as varchar) as usage_restriction,
    cast(collected_at_utc as varchar) as collected_at_utc,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('CLIMATE_PREPARED_DIR', '.data/ci-climate/prepared') }}/climate_daily.parquet')
