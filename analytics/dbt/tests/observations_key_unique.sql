{{ config(tags=['observations']) }}
-- Uma linha retornada reprova o build: a chave de uma observação é única por dataset.
select
    dataset_id, dico, period, filter_1, filter_2, filter_3, count(*) as occurrences
from {{ ref('stg_observation') }}
group by dataset_id, dico, period, filter_1, filter_2, filter_3
having count(*) > 1
