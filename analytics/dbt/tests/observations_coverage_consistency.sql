{{ config(tags=['observations']) }}
-- Uma linha retornada reprova o build: a cobertura precisa fechar a conta (com valor + sem valor = esperado)
-- e a lista de ausentes precisa ter exatamente o tamanho de "sem valor".
select source_id, dataset_id, municipalities_expected, municipalities_with_value, municipalities_without_value
from {{ ref('rpt_observation_coverage') }}
where municipalities_with_value + municipalities_without_value <> municipalities_expected
   or len(missing_dico) <> municipalities_without_value
   or municipalities_with_value < 0
