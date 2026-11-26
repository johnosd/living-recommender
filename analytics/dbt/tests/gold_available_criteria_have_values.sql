{{ config(tags=['gold']) }}
-- FR-020: critério disponível sem nenhum valor no município falha (o build Python já barra; aqui é a rede).
select catalog.criterion_id
from {{ ref('gold_criteria_catalog') }} as catalog
left join (
    select criterion_id, count(value) as with_value
    from {{ ref('gold_municipality_indicator') }}
    group by criterion_id
) as indicator using (criterion_id)
where catalog.status = 'disponivel'
  and catalog.levels like '%"municipio"%'
  and coalesce(indicator.with_value, 0) = 0
