{{ config(materialized='external', format='parquet', location=env_var('MOBILITY_BUILD_DIR', '.data/ci-mobility') ~ '/lake/bronze/stg_municipality_pole_distance/data.parquet') }}

select
    cast(dico as varchar) as dico,
    cast(pole_id as varchar) as pole_id,
    cast(mode as varchar) as mode,
    cast(km as double) as km,
    cast(minutes as double) as minutes,
    cast(status as varchar) as status,
    cast(no_route_reason as varchar) as no_route_reason,
    cast(error as varchar) as error,
    cast(method as varchar) as method,
    cast(departure_time as varchar) as departure_time,
    cast(stale as boolean) as stale,
    cast(calculated_at_utc as varchar) as calculated_at_utc,
    cast(source_run_id as varchar) as source_run_id,
    cast(caop_version as varchar) as caop_version,
    cast(poles_catalog_version as varchar) as poles_catalog_version,
    cast(license_id as varchar) as license_id,
    cast(attribution as varchar) as attribution,
    cast(usage_restriction as varchar) as usage_restriction,
    cast(reference_period as varchar) as reference_period,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('MOBILITY_PREPARED_DIR', '.data/ci-mobility/prepared') }}/distances.parquet')
