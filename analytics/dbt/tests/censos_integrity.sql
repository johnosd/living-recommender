{{ config(tags=['censos']) }}
select 'native_duplicate' as reason from {{ ref('census_observation') }}
group by dataset_id, source_dicofre, period, age_code having count(*) <> 1
union all
select 'prepared_duplicate' from {{ ref('census_parish_observation') }}
group by dicofre, period, age_code having count(*) <> 1
union all
select 'invalid_count_or_status' from {{ ref('census_observation') }}
where period <> '2021' or value < 0 or (value_status = 'observed' and value is null)
   or (value_status <> 'observed' and value is not null)
union all
select 'unexplained_absence' from {{ ref('census_parish_observation') }}
where (coverage_status = 'missing' and (reason is null or value is not null))
   or (coverage_status <> 'missing' and value is null)
