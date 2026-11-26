{{ config(tags=['gold']) }}
-- Spec 012, FR-016 / SC-003: todo aluguel herdado de distrito ou região é cópia exata da linha de origem (valor,
-- período, licença e atribuição), e só os dois critérios de aluguel do Idealista podem usar esses níveis.
with inherited as (
    select dico, criterion_id, variant, origin_level, value, period, license_id, attribution
    from {{ ref('gold_municipality_indicator') }}
    where origin_level in ('distrito', 'regiao')
),
places as (
    select distinct dico, district_or_island, source_region
    from {{ ref('gold_rent_by_municipality_typology') }}
),
areas as (
    select 'distrito' as level, district_or_island as area, typology, rent_median, eur_m2_median, snapshot_month,
           license_id, attribution
    from {{ ref('gold_rent_by_district_typology') }}
    union all
    select 'regiao', source_region, typology, rent_median, eur_m2_median, snapshot_month, license_id, attribution
    from {{ ref('gold_rent_by_region_typology') }}
),
compared as (
    select i.dico, i.criterion_id, i.variant, i.origin_level, i.value, i.period, i.license_id, i.attribution,
           case i.criterion_id
               when 'custo_aluguel_mediana' then a.rent_median
               when 'custo_aluguel_m2' then a.eur_m2_median
           end as source_value,
           a.snapshot_month, a.license_id as source_license_id, a.attribution as source_attribution
    from inherited i
    left join places p using (dico)
    left join areas a
        on a.level = i.origin_level and a.typology = i.variant
        and a.area = case i.origin_level when 'distrito' then p.district_or_island else p.source_region end
)
select 'herdado diverge da origem' as check_name, dico, criterion_id, variant, origin_level
from compared
where value is distinct from source_value
   or period is distinct from snapshot_month
   or license_id is distinct from source_license_id
   or attribution is distinct from source_attribution
union all
select 'critério sem origem conhecida', dico, criterion_id, variant, origin_level
from inherited
where criterion_id not in ('custo_aluguel_mediana', 'custo_aluguel_m2')
union all
-- a mediana herdada exige a amostra insuficiente no próprio município (a cadeia começa no valor próprio)
select 'herdado com amostra própria', i.dico, i.criterion_id, i.variant, i.origin_level
from inherited i
join {{ ref('gold_rent_by_municipality_typology') }} m on m.dico = i.dico and m.typology = i.variant
where case i.criterion_id
          when 'custo_aluguel_mediana' then m.rent_median
          when 'custo_aluguel_m2' then m.eur_m2_median
      end is not null
