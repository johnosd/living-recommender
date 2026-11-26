{{ config(tags=['gold']) }}
-- Grão de cada tabela Gold: nenhuma chave repetida.
select 'gold_municipality_indicator' as table_name, dico || '|' || criterion_id || '|' || variant as grain_key,
       count(*) as occurrences
from {{ ref('gold_municipality_indicator') }} group by all having count(*) > 1
union all
select 'gold_rent_by_municipality_typology', dico || '|' || typology, count(*)
from {{ ref('gold_rent_by_municipality_typology') }} group by all having count(*) > 1
union all
select 'gold_municipality_climate_monthly', dico || '|' || year_month, count(*)
from {{ ref('gold_municipality_climate_monthly') }} group by all having count(*) > 1
union all
select 'gold_criteria_normalization', criterion_id || '|' || level || '|' || variant, count(*)
from {{ ref('gold_criteria_normalization') }} group by all having count(*) > 1
union all
select 'gold_data_quality', criterion_id || '|' || level || '|' || variant, count(*)
from {{ ref('gold_data_quality') }} group by all having count(*) > 1
union all
select 'gold_parish_indicator', dicofre || '|' || criterion_id || '|' || variant, count(*)
from {{ ref('gold_parish_indicator') }} group by all having count(*) > 1
union all
select 'gold_rent_by_parish_typology', dicofre || '|' || typology, count(*)
from {{ ref('gold_rent_by_parish_typology') }} group by all having count(*) > 1
