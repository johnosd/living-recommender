{{ config(tags=['gold']) }}
-- Faixas plausíveis (FR-031), no município e na freguesia: aluguel mediano 100–10 000 €/mês, percentuais 0–100,
-- TCI 0–100, distâncias não negativas.
select 'rent_median' as check_name, dico as territory, typology as detail, rent_median as value
from {{ ref('gold_rent_by_municipality_typology') }}
where rent_median is not null and (rent_median < 100 or rent_median > 10000)
union all
select 'percent', dico, criterion_id, value
from {{ ref('gold_municipality_indicator') }}
where value is not null and (criterion_id like '%\_pct' escape '\' or criterion_id like 'populacao\_pct\_%' escape '\')
  and (value < 0 or value > 100)
union all
select 'tci_monthly', dico, year_month, tci
from {{ ref('gold_municipality_climate_monthly') }}
where tci is not null and (tci < 0 or tci > 100)
union all
select 'tci_annual', dico, criterion_id, value
from {{ ref('gold_municipality_indicator') }}
where criterion_id = 'clima_tci_anual' and value is not null and (value < 0 or value > 100)
union all
select 'parish_rent_median', dicofre, typology, rent_median
from {{ ref('gold_rent_by_parish_typology') }}
where rent_median is not null and (rent_median < 100 or rent_median > 10000)
union all
select 'parish_percent', dicofre, criterion_id, value
from {{ ref('gold_parish_indicator') }}
where value is not null and (criterion_id like '%\_pct' escape '\' or criterion_id like 'populacao\_pct\_%' escape '\'
                             or criterion_id = 'clima_tci_anual')
  and (value < 0 or value > 100)
union all
select 'distance', dico, criterion_id, value
from {{ ref('gold_municipality_indicator') }}
where criterion_id like 'distancia\_%' escape '\' and value < 0
