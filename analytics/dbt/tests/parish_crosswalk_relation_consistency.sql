{{ config(tags=['parish_crosswalk']) }}
-- Uma linha retornada reprova o build: a natureza da relação e a herança precisam bater com as contagens por par
-- (destinos de um código de 2013 e origens de um código de 2025), a regra de `research.md` R4.
with counted as (
    select
        *,
        count(*) over (partition by dicofre_2013) as destinations,
        count(*) over (partition by dicofre_2025) as origins
    from {{ ref('xwalk_parish_2013_2025') }}
)
select dicofre_2013, dicofre_2025, relation, inherited, destinations, origins
from counted
where relation <> case
        when destinations = 1 and origins = 1 then 'one_to_one'
        when destinations > 1 and origins = 1 then 'one_to_many'
        when destinations = 1 and origins > 1 then 'many_to_one'
        else 'many_to_many'
    end
   or inherited <> (destinations > 1)
