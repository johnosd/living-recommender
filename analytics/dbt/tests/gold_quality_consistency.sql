{{ config(tags=['gold']) }}
-- US2 / SC-008: o mart de qualidade fecha as contas, cobre todo o catálogo e bate com o perfil municipal.
with quality as (select * from {{ ref('gold_data_quality') }}),
catalog as (select * from {{ ref('gold_criteria_catalog') }}),
municipal as (
    select criterion_id, variant, count(*) as rows_found, count(value) as with_value,
           count(*) filter (where value_status = 'zero_convencao_fonte') as zero_by_convention,
           count(*) filter (where is_older_period) as older_period,
           count(*) filter (where is_stale) as stale
    from {{ ref('gold_municipality_indicator') }}
    group by all
)
select 'conta' as check_name, criterion_id, level, variant
from quality
where with_value + missing <> territories_expected
union all
select 'pendente com cobertura', criterion_id, level, variant
from quality
where status = 'fonte_pendente' and (territories_expected <> 0 or with_value <> 0 or pending_reason is null)
union all
select 'critério fora da qualidade', c.criterion_id, null, null
from catalog c
where c.criterion_id not in (select criterion_id from quality)
union all
select 'nível declarado sem linha', c.criterion_id, 'municipio', null
from catalog c
where c.levels like '%"municipio"%'
  and not exists (select 1 from quality q where q.criterion_id = c.criterion_id and q.level = 'municipio')
union all
select 'diverge do perfil', q.criterion_id, q.level, q.variant
from quality q
join municipal m using (criterion_id, variant)
where q.level = 'municipio'
  and (q.territories_expected <> m.rows_found or q.with_value <> m.with_value
       or q.zero_by_convention <> m.zero_by_convention or q.older_period <> m.older_period or q.stale <> m.stale)
