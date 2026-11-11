{{ config(tags=['climate']) }}
select dico, variable, date, count(*) as occurrences
from {{ ref('stg_climate_daily') }}
group by dico, variable, date
having count(*) > 1
