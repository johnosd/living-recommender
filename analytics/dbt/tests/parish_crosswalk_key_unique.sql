{{ config(tags=['parish_crosswalk']) }}
-- Uma linha retornada reprova o build: o par (freguesia de 2013, freguesia de 2025) é único.
select dicofre_2013, dicofre_2025, count(*) as occurrences
from {{ ref('xwalk_parish_2013_2025') }}
group by dicofre_2013, dicofre_2025
having count(*) > 1
