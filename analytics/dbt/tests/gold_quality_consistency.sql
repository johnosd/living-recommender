{{ config(tags=['gold']) }}
-- US2 / SC-008 (spec 011) e FR-014 (spec 012): o mart de qualidade fecha as contas, cobre todo o catálogo e bate com
-- os perfis municipal e de freguesia. Cobertura é só valor próprio; os herdados são contados pelo nível de origem.
with quality as (select * from {{ ref('gold_data_quality') }}),
catalog as (select * from {{ ref('gold_criteria_catalog') }}),
profile as (
    select 'municipio' as level, criterion_id, variant, value, value_status, is_older_period, is_stale, origin,
           origin_level
    from {{ ref('gold_municipality_indicator') }}
    union all
    select 'freguesia', criterion_id, variant, value, value_status, is_older_period, is_stale, origin, origin_level
    from {{ ref('gold_parish_indicator') }}
),
counted as (
    select level, criterion_id, variant, count(*) as rows_found,
           count(value) filter (where origin = 'proprio') as with_value,
           count(*) filter (where origin = 'proprio' and value_status = 'zero_convencao_fonte') as zero_by_convention,
           count(*) filter (where origin = 'proprio' and is_older_period) as older_period,
           count(*) filter (where origin = 'proprio' and is_stale) as stale,
           count(*) filter (where origin = 'herdado') as inherited,
           count(*) filter (where origin = 'herdado' and origin_level = 'municipio') as inherited_municipio,
           count(*) filter (where origin = 'herdado' and origin_level = 'distrito') as inherited_distrito,
           count(*) filter (where origin = 'herdado' and origin_level = 'regiao') as inherited_regiao
    from profile
    group by all
)
select 'conta' as check_name, criterion_id, level, variant
from quality
where with_value + missing <> territories_expected
   or inherited <> inherited_municipio + inherited_distrito + inherited_regiao
   or inherited > missing
   or (level = 'municipio' and inherited_municipio <> 0)
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
join counted p using (level, criterion_id, variant)
where q.territories_expected <> p.rows_found or q.with_value <> p.with_value
   or q.zero_by_convention <> p.zero_by_convention or q.older_period <> p.older_period or q.stale <> p.stale
   or q.inherited <> p.inherited or q.inherited_municipio <> p.inherited_municipio
   or q.inherited_distrito <> p.inherited_distrito or q.inherited_regiao <> p.inherited_regiao
