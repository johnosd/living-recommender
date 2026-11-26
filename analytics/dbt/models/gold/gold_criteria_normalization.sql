{{ config(materialized='external', format='parquet', location=env_var('GOLD_BUILD_DIR', '.data/ci-gold-build') ~ '/lake/gold/gold_criteria_normalization/data.parquet') }}

select
    cast(catalog_version as varchar) as catalog_version,
    cast(criterion_id as varchar) as criterion_id,
    cast(level as varchar) as level,
    cast(variant as varchar) as variant,
    cast(n as bigint) as n,
    cast(min as double) as min,
    cast(p5 as double) as p5,
    cast(p95 as double) as p95,
    cast(max as double) as max,
    cast(is_degenerate as boolean) as is_degenerate,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('GOLD_PREPARED_DIR', '.data/ci-gold-build/prepared') }}/criteria_normalization.parquet')
