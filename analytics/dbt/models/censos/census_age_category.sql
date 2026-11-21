{{ config(materialized='external', format='parquet', location=env_var('CENSOS_BUILD_DIR', '.data/ci-censos') ~ '/lake/bronze/census_age_category/data.parquet') }}
select * replace (cast(age_min as integer) as age_min, cast(age_max as integer) as age_max)
from read_parquet('{{ env_var('CENSOS_PREPARED_DIR', '.data/ci-censos/prepared') }}/census_age_category.parquet')
