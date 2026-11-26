{{ config(materialized='external', format='parquet', location=env_var('GOLD_BUILD_DIR', '.data/ci-gold-build') ~ '/lake/gold/gold_rent_by_region_typology/data.parquet') }}

select
    cast(source_region as varchar) as source_region,
    cast(typology as varchar) as typology,
    cast(n_listings as bigint) as n_listings,
    cast(n_outliers as bigint) as n_outliers,
    cast(n_eligible as bigint) as n_eligible,
    cast(rent_median as double) as rent_median,
    cast(rent_p25 as double) as rent_p25,
    cast(rent_p75 as double) as rent_p75,
    cast(n_eur_m2 as bigint) as n_eur_m2,
    cast(eur_m2_median as double) as eur_m2_median,
    cast(sample_status as varchar) as sample_status,
    cast(snapshot_month as varchar) as snapshot_month,
    cast(source_id as varchar) as source_id,
    cast(license_id as varchar) as license_id,
    cast(attribution as varchar) as attribution,
    cast(catalog_version as varchar) as catalog_version,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('GOLD_PREPARED_DIR', '.data/ci-gold-build/prepared') }}/rent_region.parquet')
