-- Catálogo de tabelas do lake (spec 010). Rode no DBeaver ou na DuckDB UI conectada a `.data/catalog.duckdb`.
-- No DBeaver: Alt+X executa o script inteiro (uma aba de resultado por consulta); Ctrl+Enter executa só a consulta
-- sob o cursor. Gere o catálogo de novo com `uv run --locked python -m pipelines.cli.lake_catalog --root .data`
-- depois de um build ou de mudar um schema.yml.

-- 1. Todas as tabelas: camada, domínio, tipo, linhas, colunas e fontes
select t.layer, t.table_name, t.domain, t.kind, t.status, t.row_count,
       (select count(*) from meta.columns c
         where c.layer = t.layer and c.table_name = t.table_name and c.in_lake) as colunas,
       t.source_ids as fontes, t.description as descricao
from meta.tables t
order by t.layer, t.kind, t.table_name;

-- 2. Relacionamentos declarados entre as tabelas
select from_table, from_column, to_table, to_column
from meta.relationships
order by from_table, from_column;

-- 3. Todas as colunas de todas as tabelas, com tipo e descrição
select layer, table_name, column_name, position, type_actual, description
from meta.columns
where in_lake
order by layer, table_name, position;

-- 4. Fontes de origem: coletas registradas no raw
select source_id, count(*) as coletas, max(collected_at_utc) as ultima_coleta, any_value(license_id) as licenca
from meta.raw_runs
group by 1
order by 1;

-- 5. Amostra de cada tabela (10 linhas)

-- bronze.rpt_climate_coverage (relatorio)
select * from bronze.rpt_climate_coverage limit 10;

-- bronze.rpt_climate_points (relatorio)
select * from bronze.rpt_climate_points limit 10;

-- bronze.rpt_mobility_coverage (relatorio)
select * from bronze.rpt_mobility_coverage limit 10;

-- bronze.rpt_observation_coverage (relatorio)
select * from bronze.rpt_observation_coverage limit 10;

-- bronze.census_age_category (principal)
select * from bronze.census_age_category limit 10;

-- bronze.census_observation (principal)
select * from bronze.census_observation limit 10;

-- bronze.dim_mobility_pole (principal)
select * from bronze.dim_mobility_pole limit 10;

-- bronze.idealista_occurrences (principal)
select * from bronze.idealista_occurrences limit 10;

-- bronze.stg_caop_municipalities (principal)
select * from bronze.stg_caop_municipalities limit 10;

-- bronze.stg_caop_parishes (principal)
select * from bronze.stg_caop_parishes limit 10;

-- bronze.stg_climate_daily (principal)
select * from bronze.stg_climate_daily limit 10;

-- bronze.stg_municipality_pole_distance (principal)
select * from bronze.stg_municipality_pole_distance limit 10;

-- bronze.stg_observation (principal)
select * from bronze.stg_observation limit 10;

-- bronze.wikipedia_revision (principal)
select * from bronze.wikipedia_revision limit 10;

-- silver.census_coverage (relatorio)
select * from silver.census_coverage limit 10;

-- silver.rpt_parish_crosswalk_coverage (relatorio)
select * from silver.rpt_parish_crosswalk_coverage limit 10;

-- silver.wikipedia_coverage (relatorio)
select * from silver.wikipedia_coverage limit 10;

-- silver.census_parish_observation (principal)
select * from silver.census_parish_observation limit 10;

-- silver.dim_municipality (principal)
select * from silver.dim_municipality limit 10;

-- silver.dim_parish (principal)
select * from silver.dim_parish limit 10;

-- silver.idealista_listings (principal)
select * from silver.idealista_listings limit 10;

-- silver.wikipedia_article (principal)
select * from silver.wikipedia_article limit 10;

-- silver.wikipedia_block (principal)
select * from silver.wikipedia_block limit 10;

-- silver.wikipedia_section (principal)
select * from silver.wikipedia_section limit 10;

-- silver.xwalk_parish_2013_2025 (principal)
select * from silver.xwalk_parish_2013_2025 limit 10;
