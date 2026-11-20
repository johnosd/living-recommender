{{ config(materialized='external', format='parquet', location=env_var('WIKIPEDIA_BUILD_DIR', '.data/ci-wikipedia') ~ '/lake/silver/wikipedia_block/data.parquet') }}
select * from read_parquet('{{ env_var('WIKIPEDIA_PREPARED_DIR', '.data/ci-wikipedia/prepared') }}/wikipedia_block.parquet')
