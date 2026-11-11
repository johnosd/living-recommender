{{ config(materialized='external', format='parquet', location=env_var('OBS_BUILD_DIR', '.data/ci-obs') ~ '/lake/bronze/rpt_observation_coverage/data.parquet') }}

-- Cobertura por dataset: um município "tem valor" se houver pelo menos uma observação não nula no período mais
-- recente do dataset. A cobertura por combinação de filtros fica para a camada Gold. Ausência nunca é imputada.
with observations as (
    select * from {{ ref('stg_observation') }}
),

municipalities as (
    select dico from {{ source('caop_silver', 'dim_municipality') }}
),

latest as (
    select
        source_id,
        dataset_id,
        max(period) as latest_period,
        max(period) filter (where value is not null) as latest_period_with_data
    from observations
    group by source_id, dataset_id
),

with_value as (
    select o.source_id, o.dataset_id, o.dico
    from observations o
    join latest l on l.source_id = o.source_id and l.dataset_id = o.dataset_id and l.latest_period = o.period
    where o.value is not null
    group by o.source_id, o.dataset_id, o.dico
),

counts as (
    select source_id, dataset_id, count(*) as municipalities_with_value
    from with_value
    group by source_id, dataset_id
),

missing as (
    select
        l.source_id,
        l.dataset_id,
        list(m.dico order by m.dico) filter (where w.dico is null) as missing_dico
    from latest l
    cross join municipalities m
    left join with_value w on w.source_id = l.source_id and w.dataset_id = l.dataset_id and w.dico = m.dico
    group by l.source_id, l.dataset_id
),

stats as (
    select * from read_parquet('{{ env_var('OBS_PREPARED_DIR', '.data/ci-obs/prepared') }}/dataset_stats.parquet')
)

select
    l.source_id,
    l.dataset_id,
    l.latest_period,
    l.latest_period_with_data,
    (select count(*) from municipalities) as municipalities_expected,
    coalesce(c.municipalities_with_value, 0) as municipalities_with_value,
    (select count(*) from municipalities) - coalesce(c.municipalities_with_value, 0) as municipalities_without_value,
    coalesce(m.missing_dico, []::varchar[]) as missing_dico,
    s.aggregate_rows_excluded
from latest l
left join counts c on c.source_id = l.source_id and c.dataset_id = l.dataset_id
left join missing m on m.source_id = l.source_id and m.dataset_id = l.dataset_id
left join stats s on s.source_id = l.source_id and s.dataset_id = l.dataset_id
