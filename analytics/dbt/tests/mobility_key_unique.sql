{{ config(tags=['mobility']) }}
select dico, pole_id, mode, count(*) as occurrences
from {{ ref('stg_municipality_pole_distance') }}
group by dico, pole_id, mode
having count(*) > 1
