{{ config(tags=['mobility']) }}
-- FR-022: toda linha do Google leva a atribuição e a licença da fonte.
select * from {{ ref('stg_municipality_pole_distance') }}
where mode in ('driving', 'transit') and (attribution is null or license_id is null)
