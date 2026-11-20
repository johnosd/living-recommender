{{ config(materialized='external', format='parquet', location=env_var('WIKIPEDIA_BUILD_DIR', '.data/ci-wikipedia') ~ '/lake/silver/wikipedia_article/data.parquet') }}
select * from read_parquet('{{ env_var('WIKIPEDIA_PREPARED_DIR', '.data/ci-wikipedia/prepared') }}/wikipedia_article.parquet')
