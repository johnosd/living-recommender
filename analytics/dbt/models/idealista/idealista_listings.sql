{{ config(materialized='external', format='parquet', location=env_var('IDEALISTA_BUILD_DIR', '.data/ci-idealista') ~ '/lake/silver/idealista_listings/data.parquet') }}

-- A escolha canônica e os conflitos são preparados em Python, sem inferir recência.
select *
from read_parquet('{{ env_var('IDEALISTA_PREPARED_DIR', '.data/ci-idealista/prepared') }}/listings.parquet')
