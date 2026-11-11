{{ config(tags=['caop']) }}
-- Uma linha retornada reprova o build. O ponto dentro do polígono é verificado
-- pelo normalizador e novamente pela CLI antes da promoção da Silver.
with municipalities as (
    select * from {{ ref('dim_municipality') }}
),
parishes as (
    select * from {{ ref('dim_parish') }}
),
failures as (
    select 'municipality_count' as issue, cast(count(*) as varchar) as code
    from municipalities
    having count(*) <> 308

    union all
    select 'municipality_code', dico from municipalities
    where not regexp_matches(dico, '^[0-9]{4}$')

    union all
    select 'parish_code', dicofre from parishes
    where not regexp_matches(dicofre, '^[0-9]{4}[0-9A-Z]{2}$')

    union all
    select 'parish_parent', dicofre from parishes
    where left(dicofre, 4) <> dico

    union all
    select 'municipality_area_or_point', dico from municipalities
    where area_km2 is null or area_km2 <= 0
       or representative_lat is null or representative_lon is null
       or representative_lat not between -90 and 90
       or representative_lon not between -180 and 180

    union all
    select 'parish_area_or_point', dicofre from parishes
    where area_km2 is null or area_km2 <= 0
       or representative_lat is null or representative_lon is null
       or representative_lat not between -90 and 90
       or representative_lon not between -180 and 180

    union all
    select 'municipality_provenance', dico from municipalities
    where source_run_id <> '{{ env_var('CAOP_SOURCE_RUN_ID', 'ci-fixture') }}'
       or caop_version is null or reference_period is null or license_id is null
       or collected_at_utc is null or processed_at_utc is null

    union all
    select 'parish_provenance', dicofre from parishes
    where source_run_id <> '{{ env_var('CAOP_SOURCE_RUN_ID', 'ci-fixture') }}'
       or caop_version is null or reference_period is null or license_id is null
       or collected_at_utc is null or processed_at_utc is null

    union all
    select 'parish_count', cast(count(*) as varchar) from parishes
    having count(*) <> (select count(*) from {{ ref('stg_caop_parishes') }})
)
select * from failures
