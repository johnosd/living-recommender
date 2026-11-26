{{ config(tags=['gold']) }}
-- FR-008 / ADR-002 D8: todo valor de carro leva "Tempos de viagem: Google" e a restrição de uso do Google.
select dico, criterion_id, attribution, usage_restriction
from {{ ref('gold_municipality_indicator') }}
where value is not null
  and (source_id = 'google_distances' or criterion_id like 'distancia\_%\_carro\_%' escape '\')
  and (source_id is distinct from 'google_distances'
       or attribution is distinct from 'Tempos de viagem: Google'
       or usage_restriction is null)
