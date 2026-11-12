{{ config(materialized='external', format='parquet', location=env_var('XWALK_BUILD_DIR', '.data/ci-xwalk') ~ '/lake/silver/rpt_parish_crosswalk_coverage/data.parquet') }}

-- Cobertura da correspondência: uma linha por natureza da relação (sempre as quatro, mesmo com zero pares) e uma linha
-- `all` com os totais, a cobertura da `dim_parish` e as estatísticas das tabelas de origem (células numéricas
-- normalizadas, legendas ignoradas e linhas com o marcador "(parte)", que é textual: ver plan R-006).
with pairs as (
    select * from {{ ref('xwalk_parish_2013_2025') }}
),

dimension as (
    select dicofre, caop_version from {{ source('caop_silver', 'dim_parish') }}
),

stats as (
    select * from read_parquet('{{ env_var('XWALK_PREPARED_DIR', '.data/ci-xwalk/prepared') }}/table_stats.parquet')
),

relations as (
    select * from (values ('one_to_one'), ('one_to_many'), ('many_to_one'), ('many_to_many')) as v(relation)
),

by_relation as (
    select
        r.relation,
        count(p.dicofre_2013) as pairs,
        count(distinct p.dicofre_2013) as codes_2013,
        count(distinct p.dicofre_2025) as codes_2025,
        count(*) filter (where p.inherited) as inherited_pairs,
        count(*) filter (where p.partial_origin) as partial_origin_pairs,
        count(*) filter (where p.name_changed) as name_changed_pairs,
        count(*) filter (where p.municipality_changed) as municipality_changed_pairs,
        cast(null as bigint) as parishes_expected,
        cast(null as bigint) as parishes_with_origin,
        cast(null as bigint) as source_rows_read,
        cast(null as bigint) as source_ignored_rows,
        cast(null as bigint) as source_numeric_codes_normalized,
        cast(null as bigint) as source_partial_rows,
        cast(null as varchar) as caop_version,
        cast(null as varchar) as collected_at_utc,
        (select max(attribution) from pairs) as attribution
    from relations r
    left join pairs p on p.relation = r.relation
    group by r.relation
),

total as (
    select
        'all' as relation,
        count(*) as pairs,
        count(distinct dicofre_2013) as codes_2013,
        count(distinct dicofre_2025) as codes_2025,
        count(*) filter (where inherited) as inherited_pairs,
        count(*) filter (where partial_origin) as partial_origin_pairs,
        count(*) filter (where name_changed) as name_changed_pairs,
        count(*) filter (where municipality_changed) as municipality_changed_pairs,
        (select count(*) from dimension) as parishes_expected,
        (select count(*) from dimension where dicofre in (select dicofre_2025 from pairs)) as parishes_with_origin,
        (select sum(rows_read) from stats) as source_rows_read,
        (select sum(ignored_rows) from stats) as source_ignored_rows,
        (select sum(numeric_codes_normalized) from stats) as source_numeric_codes_normalized,
        (select sum(partial_rows) from stats) as source_partial_rows,
        (select max(caop_version) from dimension) as caop_version,
        max(collected_at_utc) as collected_at_utc,
        max(attribution) as attribution
    from pairs
)

select * from by_relation
union all
select * from total
