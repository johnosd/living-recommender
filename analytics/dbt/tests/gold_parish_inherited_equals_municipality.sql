{{ config(tags=['gold']) }}
-- SC-007 / D9: herdado é cópia exata do município (valor e proveniência); toda freguesia aparece em cada critério ×
-- variante; nenhuma estatística de aluguel da freguesia abaixo de 10 anúncios.
with parish as (select * from {{ ref('gold_parish_indicator') }}),
municipal as (select * from {{ ref('gold_municipality_indicator') }}),
expected as (select count(*) as parishes from {{ source('caop_silver', 'dim_parish') }})
select 'herdado diverge' as check_name, p.dicofre, p.criterion_id, p.variant
from parish p
join municipal m using (dico, criterion_id, variant)
where p.origin = 'herdado'
  and (p.value is distinct from m.value or p.period is distinct from m.period
       or p.source_id is distinct from m.source_id or p.license_id is distinct from m.license_id
       or p.attribution is distinct from m.attribution or p.value_status is distinct from m.value_status)
union all
select 'origem incoerente', dicofre, criterion_id, variant
from parish
where (origin = 'ausente') <> (value is null)
   or (value is null) <> (missing_reason is not null)
union all
select 'cobertura', null, criterion_id, variant
from parish cross join expected
group by criterion_id, variant, expected.parishes
having count(distinct dicofre) <> expected.parishes or count(*) <> expected.parishes
union all
select 'aluguel com amostra pequena', dicofre, typology, null
from {{ ref('gold_rent_by_parish_typology') }}
where (n_eligible < 10 and rent_median is not null) or (n_eur_m2 < 10 and eur_m2_median is not null)
