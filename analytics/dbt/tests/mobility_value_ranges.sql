{{ config(tags=['mobility']) }}
-- Portugal e as regiões autónomas cabem em ~3.500 km em linha reta; o carro, em ~3.000 minutos.
select * from {{ ref('stg_municipality_pole_distance') }}
where km < 0 or km > 3500 or minutes < 0 or minutes > 3000
