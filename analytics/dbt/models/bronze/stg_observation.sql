{{ config(materialized='external', format='parquet', location=env_var('OBS_BUILD_DIR', '.data/ci-obs') ~ '/lake/bronze/stg_observation/data.parquet') }}

-- Uma linha por observação municipal de cada dataset do Pordata e do INE. O Parquet de entrada já traz o
-- `dico` resolvido pelo normalizador Python; aqui os tipos são fixados (inclusive colunas inteiramente nulas,
-- como `symbol`) e os testes de `schema.yml` e de `tests/observations_*.sql` barram o resultado inválido.
select
    cast(source_id as varchar) as source_id,
    cast(dataset_id as varchar) as dataset_id,
    cast(dico as varchar) as dico,
    cast(source_name as varchar) as source_name,
    cast(period as integer) as period,
    cast(filter_1 as varchar) as filter_1,
    cast(filter_2 as varchar) as filter_2,
    cast(filter_3 as varchar) as filter_3,
    cast(value as double) as value,
    cast(symbol as varchar) as symbol,
    cast(unit as varchar) as unit,
    cast(source_run_id as varchar) as source_run_id,
    cast(license_id as varchar) as license_id,
    cast(attribution as varchar) as attribution,
    cast(collected_at_utc as varchar) as collected_at_utc,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('OBS_PREPARED_DIR', '.data/ci-obs/prepared') }}/observations.parquet')
