{{ config(tags=['gold']) }}
-- FR-001 / SC-002: todo critério disponível do município tem uma linha por município e variante, e só esses.
with expected as (select count(*) as municipalities from {{ source('caop_silver', 'dim_municipality') }}),
counts as (
    select criterion_id, variant, count(*) as rows_found, count(distinct dico) as municipalities_found
    from {{ ref('gold_municipality_indicator') }}
    group by all
),
available as (
    select criterion_id from {{ ref('gold_criteria_catalog') }}
    where status = 'disponivel' and levels like '%"municipio"%'
)
select c.criterion_id, c.variant, c.rows_found, e.municipalities
from counts c cross join expected e
where c.rows_found <> e.municipalities or c.municipalities_found <> e.municipalities
union all
select a.criterion_id, null, 0, e.municipalities
from available a cross join expected e
where a.criterion_id not in (select criterion_id from counts)
union all
select c.criterion_id, c.variant, c.rows_found, null
from counts c
where c.criterion_id not in (select criterion_id from available)
