# Research: visibilidade do modelo de dados (spec 010)

Verificado em 2026-11-22 com dbt 1.12.6, dbt-duckdb 1.11.1 e duckdb (Python) 2.0.0, no repositório real.

## D1. Fonte única de metadados: o manifest do `dbt parse`

- **Decisão**: as três visões partem do `manifest.json` de um único `dbt parse` do projeto inteiro.
- **Evidência**: `dbt parse --project-dir analytics/dbt --profiles-dir analytics/dbt --target local` terminou em ~4 s,
  sem lake e sem criar o arquivo DuckDB, e o manifest trouxe 25 modelos, 2 fontes, 187 testes (24 singulares) e 15
  testes `relationships`. O projeto é um só (`caop_territory`); só os **builds** são isolados por tag, então não há
  problema em tratar todos os modelos juntos.
- **Alternativas rejeitadas**: ler os `schema.yml` à mão (perde `ref`/`source` resolvidos, descrições herdadas e a
  estrutura de testes que o dbt já calcula); parsear o SQL dos modelos (frágil); abrir o lake para descobrir tabelas
  (exige dados e não traz relacionamentos).

## D2. Colunas e tipos vêm do `schema.yml`, não do lake

- **Decisão**: o documento versionado lista só colunas **declaradas** e o `data_type` **declarado**. O que existe de
  fato no lake aparece no catálogo local (`meta.columns`: `declared`, `type_declared` e `type_actual`) e no
  `catalog.json` do site.
- **Evidência**: o `schema.yml` declara de 2 a 13 colunas por tabela e o lake tem de 8 a 39 (hoje 0 descrições de
  coluna). Para as 18 tabelas principais são cerca de 345 colunas a declarar. O manifest não conhece colunas
  não declaradas.
- **Por quê**: o documento tem de ser reproduzível no CI sem lake (FR-007) e sem valores (FR-006). Declarar tipo e
  descrição no `schema.yml` torna o dado documentado a única fonte de verdade, e o `meta.columns` denuncia qualquer
  divergência com o lake real.
- **Alternativas rejeitadas**: ler tipos dos parquets de fixture no CI (exige rodar todos os builds antes do
  documento e acopla dois ambientes); mostrar `n/d` em tudo (documento pobre).

## D3. Relacionamentos: só os declarados; fonte do dbt resolve para o modelo homônimo

- **Decisão**: aresta = teste `relationships`. O alvo `source('caop_silver','dim_municipality')` resolve para o
  modelo `dim_municipality`.
- **Evidência**: 10 das 15 arestas apontam para `source('caop_silver', ...)`; sem essa regra o diagrama perderia as
  ligações com `dim_municipality` e `dim_parish`.
- **Alternativa rejeitada**: inferir relacionamentos pelo nome da coluna. Mostraria ligações que ninguém testou, o que
  contraria a constitution III; as chaves `dico`/`dicofre` sem relação ficam na lista de lacunas.

## D4. Catálogo B: views sobre `read_parquet`, schemas por camada

- **Decisão**: `CREATE VIEW` sobre os parquets, schemas `bronze`, `silver` e `meta`.
- **Evidência**: as 25 tabelas existem como `lake/<camada>/<tabela>/data.parquet`. O lake também tem CSV e pastas de
  relatório (`mobility_*.csv`, `census_reports`, `wikipedia_reports`, `idealista_reports`...) que não são tabelas e
  ficam fora, listados como ignorados.
- **Alternativas rejeitadas**: copiar os dados para tabelas (duplica ~150 MB e fica velho depois de cada build);
  um único schema com prefixo (mistura camadas e confunde os clientes SQL).

## D5. Inventário do `raw/` pelos manifests

- **Decisão**: uma linha por manifest, com `checksums` extraídos por varredura genérica da chave `sha256`.
- **Evidência**: 43 manifests de 9 fontes; o checksum está em `files[].sha256` (caop, idealista),
  `datasets[].sha256` (censos, google_distances, ine, ine_parish_crosswalk, open_meteo, pordata),
  `entries[].files[].sha256` (wikipedia) e `snapshot_sha256` (idealista). A data aparece como `collected_at_utc` ou,
  na Wikipedia, `checked_at_utc`.

## D6. Site do dbt: `docs generate --empty-catalog` + manifest com fontes ligadas + catálogo do lake

- **Decisão**: gerar o site com o catálogo vazio do dbt, ligar fonte e modelo no manifest e, se houver lake,
  preencher o `catalog.json` com os tipos reais.
- **Evidência**: `dbt docs generate --empty-catalog` terminou sem lake em ~6 s e produziu `index.html` (1,8 MB),
  `manifest.json` e `catalog.json` vazio; ele abre uma conexão DuckDB no caminho de `CAOP_DUCKDB_PATH`, que deve
  apontar para uma pasta descartável. O dbt não liga `source('caop_silver','dim_municipality')` ao modelo
  `dim_municipality`, por isso o passo de `link_sources_to_models` (`logic/site.md`).
- **Alternativas rejeitadas**: `dbt docs generate` completo (exige um banco com todas as tabelas, que não existe por
  causa dos builds isolados); site publicado (fora de escopo).

## D7. Sem dependência nova

`dbt-core`, `dbt-duckdb`, `duckdb` (via dbt-duckdb), `pyarrow` e `PyYAML` já estão no `pyproject.toml`. O Mermaid é
texto: o GitHub e a maioria dos editores o renderizam sem ferramenta própria.
