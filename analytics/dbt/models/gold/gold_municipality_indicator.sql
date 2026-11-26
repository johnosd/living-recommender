{{ config(materialized='external', format='parquet', location=env_var('GOLD_BUILD_DIR', '.data/ci-gold-build') ~ '/lake/gold/gold_municipality_indicator/data.parquet') }}

select
    cast(dico as varchar) as dico,
    cast(criterion_id as varchar) as criterion_id,
    cast(category as varchar) as category,
    cast(variant as varchar) as variant,
    cast(value as double) as value,
    cast(unit as varchar) as unit,
    cast(period as varchar) as period,
    cast(dataset_latest_period as varchar) as dataset_latest_period,
    cast(is_older_period as boolean) as is_older_period,
    cast(value_status as varchar) as value_status,
    cast(missing_reason as varchar) as missing_reason,
    cast(source_symbol as varchar) as source_symbol,
    cast(source_id as varchar) as source_id,
    cast(dataset_id as varchar) as dataset_id,
    cast(license_id as varchar) as license_id,
    cast(attribution as varchar) as attribution,
    cast(usage_restriction as varchar) as usage_restriction,
    cast(is_stale as boolean) as is_stale,
    cast(catalog_version as varchar) as catalog_version,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('GOLD_PREPARED_DIR', '.data/ci-gold-build/prepared') }}/municipality_indicator.parquet')
