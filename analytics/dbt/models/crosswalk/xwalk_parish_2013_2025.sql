{{ config(materialized='external', format='parquet', location=env_var('XWALK_BUILD_DIR', '.data/ci-xwalk') ~ '/lake/silver/xwalk_parish_2013_2025/data.parquet') }}

-- Uma linha por par (freguesia de 2013, freguesia de 2025). O Parquet de entrada já traz a derivação feita em Python
-- (`derive_parish_crosswalk`, que é a função do contrato); aqui os tipos são fixados e os testes de `schema.yml` e de
-- `tests/parish_crosswalk_*.sql` barram o resultado inválido antes da promoção. Nada é imputado nem repartido.
select
    cast(dicofre_2013 as varchar) as dicofre_2013,
    cast(name_2013 as varchar) as name_2013,
    cast(dicofre_2025 as varchar) as dicofre_2025,
    cast(name_2025 as varchar) as name_2025,
    cast(relation as varchar) as relation,
    cast(inherited as boolean) as inherited,
    cast(partial_origin as boolean) as partial_origin,
    cast(name_changed as boolean) as name_changed,
    cast(municipality_changed as boolean) as municipality_changed,
    cast(pre2013_codes as varchar[]) as pre2013_codes,
    cast(source_run_id_2013 as varchar) as source_run_id_2013,
    cast(source_run_id_2025 as varchar) as source_run_id_2025,
    cast(sha256_2013 as varchar) as sha256_2013,
    cast(sha256_2025 as varchar) as sha256_2025,
    cast(license_id as varchar) as license_id,
    cast(attribution as varchar) as attribution,
    cast(collected_at_utc as varchar) as collected_at_utc,
    cast(processed_at_utc as varchar) as processed_at_utc
from read_parquet('{{ env_var('XWALK_PREPARED_DIR', '.data/ci-xwalk/prepared') }}/crosswalk.parquet')
