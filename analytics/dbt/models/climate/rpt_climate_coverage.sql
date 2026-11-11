{{ config(materialized='external', format='parquet', location=env_var('CLIMATE_BUILD_DIR', '.data/ci-climate') ~ '/lake/bronze/rpt_climate_coverage/data.parquet') }}

with meta as (
    select * from read_parquet('{{ env_var('CLIMATE_PREPARED_DIR', '.data/ci-climate/prepared') }}/climate_meta.parquet')
), observed as (
    select dico, variable, count(value) as valid_days, max(collected_at_utc) as collected_at_utc
    from {{ ref('stg_climate_daily') }} group by dico, variable
), grid as (
    select m.*, t.dico, o.valid_days, o.collected_at_utc
    from meta m cross join {{ source('caop_silver', 'dim_municipality') }} t
    left join observed o on o.dico = t.dico and o.variable = m.variable
)
select variable, any_value(unit) as unit, any_value(window_start) as window_start,
    any_value(window_end) as window_end, any_value(model) as model,
    any_value(expected_days) as expected_days, max(collected_at_utc) as collected_at_utc,
    count(*) as municipalities_expected,
    count(valid_days) as municipalities_collected,
    count(*) filter (where valid_days = expected_days) as municipalities_complete,
    count(*) filter (where valid_days < expected_days) as municipalities_with_gaps,
    count(*) filter (where valid_days is null) as municipalities_not_collected,
    cast(sum(case when valid_days is not null then expected_days-valid_days else 0 end) as bigint) as missing_days_total,
    list(struct_pack(dico := dico, missing_days := expected_days-valid_days) order by dico)
        filter (where valid_days < expected_days) as gaps,
    coalesce(list(dico order by dico) filter (where valid_days is null), []::varchar[]) as not_collected_dico
from grid group by variable
