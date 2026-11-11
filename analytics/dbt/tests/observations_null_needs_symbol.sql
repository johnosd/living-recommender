{{ config(tags=['observations']) }}
-- Uma linha retornada reprova o build: valor ausente precisa trazer o símbolo da fonte
-- (nada é inventado nem convertido em zero), e um valor presente precisa ser um número finito.
select dataset_id, dico, period, filter_1, 'ausente_sem_simbolo' as issue
from {{ ref('stg_observation') }}
where value is null and symbol is null

union all
select dataset_id, dico, period, filter_1, 'valor_nao_finito'
from {{ ref('stg_observation') }}
where value is not null and (isnan(value) or isinf(value))
