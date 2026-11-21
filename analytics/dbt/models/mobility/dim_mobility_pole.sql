{{ config(materialized='external', format='parquet', location=env_var('MOBILITY_BUILD_DIR', '.data/ci-mobility') ~ '/lake/bronze/dim_mobility_pole/data.parquet') }}

select
    cast(pole_id as varchar) as pole_id,
    cast(name as varchar) as name,
    cast(kind as varchar) as kind,
    cast(routing_group as varchar) as routing_group,
    cast(scope as varchar) as scope,
    cast(dico as varchar) as dico,
    cast(latitude as double) as latitude,
    cast(longitude as double) as longitude,
    cast(district_or_island as varchar) as district_or_island,
    cast(source_ref as varchar) as source_ref
from read_parquet('{{ env_var('MOBILITY_PREPARED_DIR', '.data/ci-mobility/prepared') }}/poles.parquet')
