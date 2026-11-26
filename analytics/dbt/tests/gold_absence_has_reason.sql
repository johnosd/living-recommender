{{ config(tags=['gold']) }}
-- Constitution III: valor nulo ⇔ motivo preenchido ⇔ `ausente`; valor presente sempre com fonte, período e licença.
select dico, criterion_id, variant, value, value_status, missing_reason
from {{ ref('gold_municipality_indicator') }}
where (value is null) <> (missing_reason is not null)
   or (value is null) <> (value_status = 'ausente')
   or (value_status = 'zero_convencao_fonte' and value <> 0)
   or (value is not null and (source_id is null or period is null or license_id is null))
