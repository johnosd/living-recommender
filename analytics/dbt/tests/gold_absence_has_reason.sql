{{ config(tags=['gold']) }}
-- Constitution III: valor nulo ⇔ motivo preenchido ⇔ `ausente`; valor presente sempre com fonte, período e licença.
-- Spec 012: `origin` e `origin_level` coerentes (próprio = município; herdado = distrito ou região; ausente = nulo).
select dico, criterion_id, variant, value, value_status, missing_reason, origin, origin_level
from {{ ref('gold_municipality_indicator') }}
where (value is null) <> (missing_reason is not null)
   or (value is null) <> (value_status = 'ausente')
   or (value_status = 'zero_convencao_fonte' and value <> 0)
   or (value is not null and (source_id is null or period is null or license_id is null))
   or (value is null) <> (origin = 'ausente')
   or (origin = 'ausente') <> (origin_level is null)
   or (origin = 'proprio' and origin_level is distinct from 'municipio')
   or (origin = 'herdado' and (origin_level is null or origin_level not in ('distrito', 'regiao')))
