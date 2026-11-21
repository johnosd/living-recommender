{{ config(materialized='external', format='parquet', location=env_var('CENSOS_BUILD_DIR', '.data/ci-censos') ~ '/lake/silver/census_coverage/data.parquet') }}
select * from read_parquet('{{ env_var('CENSOS_PREPARED_DIR', '.data/ci-censos/prepared') }}/census_coverage.parquet')
