{{ config(materialized='external', format='parquet', location=env_var('CLIMATE_BUILD_DIR', '.data/ci-climate') ~ '/lake/bronze/rpt_climate_points/data.parquet') }}

select t.dico, p.dico is not null as collected, p.* exclude(dico)
from {{ source('caop_silver', 'dim_municipality') }} t
left join read_parquet('{{ env_var('CLIMATE_PREPARED_DIR', '.data/ci-climate/prepared') }}/climate_points.parquet') p
    on t.dico = p.dico
