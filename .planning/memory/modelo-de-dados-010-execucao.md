# Modelo de dados 010 — execução (2026-11-22)

Feature: visibilidade das tabelas e relacionamentos (spec `.sdd/specs/010-visibilidade-modelo-dados/`). Três comandos:
`model_docs` (documento `.docs/modelo_de_dados.md`, conferido no CI), `lake_catalog` (`.data/catalog.duckdb`) e
`dbt_docs_site` (site local do `dbt docs`). Guia de uso em `.docs/runbooks/modelo_de_dados.md`.

## Achados duráveis

- **`dbt parse` basta e não precisa de lake nem de banco.** Gera o manifest do projeto inteiro (25 modelos, 15 testes
  `relationships`) em ~4 s, e o `--check` do CI roda sem fixture. O projeto é um só (`caop_territory`); só os builds são
  isolados por tag.
- **A fonte do dbt não é o modelo.** `source('caop_silver','dim_municipality')` é um nó de fonte sem ligação com o
  modelo `dim_municipality` de outro build; 10 das 15 arestas passam por isso. `load_model` resolve a fonte para o
  modelo homônimo, e o site liga as duas pontas em `parent_map`/`child_map` (`link_sources_to_models`).
- **Manifest no Windows traz barra invertida** (`models\bronze\schema.yml`). Normalizar para `analytics/dbt/...`, senão o
  documento muda conforme o SO.
- **`description` vazia é `''`**, não `None`; testes singulares não têm `test_metadata`; o manifest só conhece as colunas
  **declaradas** no `schema.yml` (por isso a Fase 4 declarou todas as das 18 tabelas principais).
- **CRLF:** o Git do Windows converte o `.md` no checkout; grave LF e compare ignorando `\r\n`.
- **`DBT_TARGET_PATH` relativo é resolvido a partir da pasta do projeto dbt** (`analytics/dbt/`), não do diretório atual:
  passe caminho absoluto. `dbt docs generate --empty-catalog` ainda abre uma conexão DuckDB; aponte `CAOP_DUCKDB_PATH` para
  dentro da saída, nunca para `.data/ci`.
- **DuckDB:** `executemany` recusa lista vazia; coluna inteiramente nula vem de `DESCRIBE` como `"NULL"` (entre aspas);
  `CALL start_ui()` funciona em conexão `read_only` e baixa a extensão `ui` na primeira vez (precisa de rede).
- **O arquivo `.duckdb` aberto no DBeaver/UI não pode ser trocado no Windows:** o catálogo é montado ao lado e trocado
  por `os.replace`; se falhar, o anterior continua intacto.
- **Contrato 1 e `.data`:** a asserção `".data" not in document` casa com qualquer lacuna `tabela.dataset_id` (ou outra
  coluna `data*` sem descrição). Emenda aprovada pelo autor em 2026-11-24: a asserção agora é `".data/"` e a trava foi
  regravada (R-011 resolvido).
- **Navegador embutido não abre `localhost` subido pela sessão**, então a conferência visual do grafo (R-002) é manual.
- **Relacionamento declarado não é linhagem** (converge, 2026-11-24). Os modelos de mobilidade (e outros) leem parquet
  direto por `read_parquet(env_var(...))`, sem `ref`/`source`: no manifest o `parent_map` deles é vazio, e a ligação com
  `dim_municipality` existe só pelo nó do teste `relationships`. Os únicos modelos que dependem de verdade da fonte
  `caop_silver.dim_municipality` são `rpt_climate_coverage`, `rpt_climate_points` e `rpt_observation_coverage`. Para
  saber se uma aresta aparece no grafo do dbt docs, olhe o `parent_map` do modelo, não o `schema.yml`. Decisão do autor
  (R-012): o site desenha também uma aresta por `relationships` (`link_relationships`), então no grafo do site uma
  aresta pode ser relacionamento declarado, não dependência de SQL.

## Números reais do lake do autor

25 tabelas (14 bronze, 11 silver; 18 principais e 7 relatórios), 43 manifests de 9 fontes, catálogo de ~1,6 MB. Havia
345 colunas reais ainda não declaradas antes da Fase 4; hoje a consulta de completude em `meta.columns` volta vazia para
as principais.

## Limitações

- A qualidade dos textos das descrições só se verifica por revisão humana (R-007); cada texto tem evidência no SQL, no
  coletor ou nos valores do lake, e onde faltou certeza o texto diz "pode ser nulo".
- A aresta fonte→modelo no grafo do `dbt docs` depende de o site ler `parent_map`/`child_map`; não é automatizável.
