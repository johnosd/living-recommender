{{ config(tags=['gold']) }}
-- Spec 012, FR-005 / FR-015: todo distrito da tabela existe na CAOP, cada distrito tem uma única região e toda região
-- distrital tem a sua linha na tabela regional. Teste singular de propósito: `district_or_island` se repete na CAOP.
select 'distrito fora da CAOP' as check_name, district_or_island as area
from {{ ref('gold_rent_by_district_typology') }}
where district_or_island not in (
    select district_or_island from {{ source('caop_silver', 'dim_municipality') }}
    where district_or_island is not null
)
union all
select 'distrito com mais de uma região', district_or_island
from {{ ref('gold_rent_by_district_typology') }}
group by district_or_island
having count(distinct coalesce(source_region, '')) > 1
union all
select 'região sem linha regional', source_region
from {{ ref('gold_rent_by_district_typology') }}
where source_region is not null
  and source_region not in (select source_region from {{ ref('gold_rent_by_region_typology') }})
