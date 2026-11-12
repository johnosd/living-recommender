{{ config(tags=['parish_crosswalk']) }}
-- Uma linha retornada reprova o build: toda freguesia vigente (dim_parish) precisa ser destino de algum par.
-- É a segunda camada do gate de cobertura (a primeira é `verify_coverage`, em Python).
select d.dicofre
from {{ source('caop_silver', 'dim_parish') }} d
left join {{ ref('xwalk_parish_2013_2025') }} x on x.dicofre_2025 = d.dicofre
where x.dicofre_2025 is null
