{{ config(materialized='external', format='parquet', location=env_var('MOBILITY_BUILD_DIR', '.data/ci-mobility') ~ '/lake/bronze/rpt_mobility_coverage/data.parquet') }}

select
    mode,
    pole_id,
    count(*) as expected,
    count(*) filter (where status = 'ok') as ok,
    count(*) filter (where status = 'sem_rota') as sem_rota,
    count(*) filter (where status = 'falha') as falha,
    count(*) filter (where status = 'pendente') as pendente,
    count(*) filter (where stale) as stale
from {{ ref('stg_municipality_pole_distance') }}
group by mode, pole_id
