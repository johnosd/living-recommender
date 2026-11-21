{{ config(materialized='external', format='parquet', location=env_var('IDEALISTA_BUILD_DIR', '.data/ci-idealista') ~ '/lake/bronze/idealista_occurrences/data.parquet') }}

-- Todas as ocorrências normalizadas; dados individuais permanecem privados.
select *
from read_parquet('{{ env_var('IDEALISTA_PREPARED_DIR', '.data/ci-idealista/prepared') }}/occurrences.parquet')
