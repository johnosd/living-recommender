{{ config(tags=['censos']) }}
with categories as (
  select distinct age_code from {{ ref('census_parish_observation') }}
), expected as (
  select dicofre, age_code from {{ source('caop_silver','dim_parish') }} cross join categories
), actual as (
  select dicofre, age_code from {{ ref('census_coverage') }}
)
select * from (select * from expected except select * from actual)
union all
select * from (select * from actual except select * from expected)
union all
select dicofre, age_code from actual group by dicofre, age_code having count(*) <> 1
union all
select dicofre, age_code from (
 select dicofre, age_code, coverage_status, reason from {{ ref('census_coverage') }}
 except
 select dicofre, age_code, coverage_status, reason from {{ ref('census_parish_observation') }}
)
