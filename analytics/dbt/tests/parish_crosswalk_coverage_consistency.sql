{{ config(tags=['parish_crosswalk']) }}
-- Uma linha retornada reprova o build: o relatório precisa fechar a conta. A linha `all` tem de somar as quatro
-- naturezas, bater com a tabela e com a dim_parish, e a cobertura não pode passar do esperado.
with report as (
    select * from {{ ref('rpt_parish_crosswalk_coverage') }}
),

parts as (
    select sum(pairs) as pairs from report where relation <> 'all'
)

select r.relation, r.pairs, p.pairs as sum_of_relations, r.parishes_expected, r.parishes_with_origin
from report r
cross join parts p
where r.relation = 'all'
  and (
      r.pairs <> p.pairs
      or r.pairs <> (select count(*) from {{ ref('xwalk_parish_2013_2025') }})
      or r.parishes_expected <> (select count(*) from {{ source('caop_silver', 'dim_parish') }})
      or r.parishes_with_origin <> r.parishes_expected
  )
