{{ config(materialized='external', format='parquet', location=env_var('GOLD_BUILD_DIR', '.data/ci-gold-build') ~ '/lake/gold/gold_data_quality/data.parquet') }}

select
    cast(catalog_version as varchar) as catalog_version,
    cast(criterion_id as varchar) as criterion_id,
    cast(level as varchar) as level,
    cast(variant as varchar) as variant,
    cast(status as varchar) as status,
    cast(territories_expected as bigint) as territories_expected,
    cast(with_value as bigint) as with_value,
    cast(missing as bigint) as missing,
    cast(zero_by_convention as bigint) as zero_by_convention,
    cast(older_period as bigint) as older_period,
    cast(inherited as bigint) as inherited,
    cast(inherited_municipio as bigint) as inherited_municipio,
    cast(inherited_distrito as bigint) as inherited_distrito,
    cast(inherited_regiao as bigint) as inherited_regiao,
    cast(stale as bigint) as stale,
    cast(outliers as bigint) as outliers,
    cast(dataset_latest_period as varchar) as dataset_latest_period,
    cast(pending_reason as varchar) as pending_reason,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('GOLD_PREPARED_DIR', '.data/ci-gold-build/prepared') }}/data_quality.parquet')
