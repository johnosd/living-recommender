# Handoff: spec 010 — visibilidade do modelo de dados

## Contexto

- Repositório `living-recommender`, Python 3.12 + dbt Core 1.12.6 + dbt-duckdb (DuckDB 2.0.0), pytest, ruff. Windows 11
  no autor e Ubuntu no CI.
- **Branch**: o planejamento foi feito no `main`, com tudo ainda **sem commit**. Antes de commitar, crie
  `feature/010-visibilidade-modelo-dados` (`git switch -c ...`). Commits curtos, em inglês, terminando com a linha
  `Co-Authored-By` que a sessão pedir.
- Próximo comando: `/sdd-execute 010-visibilidade-modelo-dados` (modo pausado por padrão; o autor costuma pedir contínuo).
- Status no backlog: `Planejada` (0/38 itens).
- Arquivos alterados em disco fora do planejamento: `.planning/backlog.md` (entradas pós-009 e a linha da 010). Releia-o.
- O `.data/` do autor tem o lake real (25 parquets, 43 manifests), útil para as Fases 3 a 5. Ele está fora do Git.

## O que a feature entrega

- **US1 (P1)**: `pipelines.cli.model_docs` gera `.docs/modelo_de_dados.md` (diagrama Mermaid dos 15 relacionamentos
  declarados + dicionário + lacunas). O CI reprova se ele divergir (`--check`).
- **US2 (P2)**: `pipelines.cli.lake_catalog` gera `.data/catalog.duckdb` (views sobre os parquets, `meta.*`, inventário
  do `raw/`), consultável no DuckDB UI e no DBeaver.
- **US3 (P2)**: descrição, `data_type` e `meta.source_ids` das **18 tabelas principais** nos `schema.yml`. **Decisão do
  autor: sem gate de CI para modelos novos**; relatórios (`rpt_*`, `*_coverage`) ficam como estão.
- **US4 (P3)**: `pipelines.cli.dbt_docs_site` gera o site do `dbt docs` local, com a fonte `caop_silver.X` ligada ao
  modelo `X`.

## Leitura obrigatória, em ordem

1. `spec.md` — requisitos FR-001..025, SC-001..009 e as decisões do autor em Clarifications.
2. `plan.md` — decisões invariantes D1..D10, Constitution Check, estratégia de testes e riscos R-001..R-010.
3. `tasks.md` — 27 tasks em 6 fases; o número de cada stub aponta para a task que o implementa.
4. `logic/documento.md` — **formato exato do documento**, que os contratos travados verificam. Leia inteiro.
5. `logic/site.md` — sequência do site e o ajuste de `parent_map`/`child_map`.
6. `data-model.md` — esquema do catálogo (`meta.tables`, `meta.columns`, `meta.relationships`, `meta.raw_runs`) e o que
   muda nos `schema.yml`.
7. `contracts/cli.md` — flags, saídas e códigos de saída das 3 CLIs.
8. `research.md` — o que foi verificado em 2026-11-22 (por que `dbt parse`, por que views).
9. `quickstart.md` — verificação final, inclusive a checagem manual do grafo no navegador.
10. `.planning/memory/constitution.md` — gates I, III, V, VI e VII são os tocados.

## Testes de contrato

- Arquivo travado: `tests/contracts/test_modeldocs_contract.py` (**5 testes**, Fases 1, 2 e 3) e os helpers
  `tests/fixtures/modeldocs/manifests.py` e `lake.py`. **Não os edite.**
- Rodar: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp`
- Integridade: `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados`
- Hoje os 5 estão vermelhos por `NotImplementedError` (T001, T003 e T005). O de catálogo também falha em `load_model`
  (T001), porque o teste monta o `DataModel` antes de chamar `build_catalog`.
- O verificador não tem adaptador de contagem (mostra `unknown testes`); a contagem de 5 foi conferida à mão.
- Não quebra a trava de nenhuma outra feature: os contratos de `test_mobility_contract.py` e demais seguem verdes.

## Stubs criados (não travados)

- `pipelines/modeldocs/model.py`: dataclasses prontas; `load_model` e `run_dbt_parse` são `NotImplementedError` (T001).
- `pipelines/modeldocs/render.py`: `load_sources_info` (T003) e `render_markdown` (T004).
- `pipelines/modeldocs/catalog.py`: `CatalogResult` pronto; `build_catalog` (T008, e T009 para o inventário).
- `pipelines/modeldocs/site.py`: `link_sources_to_models` (T020) e `lake_catalog_json` (T021).
- `pipelines/cli/model_docs.py`: `main` (T005). `lake_catalog.py` (T010) e `dbt_docs_site.py` (T022) **não existem**: crie-os.

## Armadilhas já mapeadas

- **Barra invertida no Windows**: `original_file_path` e `patch_path` do manifest vêm como `models\bronze\schema.yml`.
  Normalize para `analytics/dbt/models/bronze/schema.yml`, senão o documento muda de acordo com o SO e o CI falha.
- **`description` vazia é `''`, não `None`** no manifest do dbt: trate como "sem descrição".
- **Testes singulares** (24) não têm `test_metadata`: ignore-os ao montar os testes das colunas.
- **A fonte do dbt não é o modelo**: `source('caop_silver','dim_municipality')` aponta para um nó de fonte; a aresta do
  diagrama deve apontar para o **modelo** homônimo. 10 das 15 arestas são assim.
- **CRLF**: o Git do Windows converte o `.md` para CRLF no checkout; grave sempre LF e compare ignorando `\r\n` no `--check`.
- **O manifest só conhece colunas declaradas**: por isso a Fase 4 declara todas; use `meta.columns` para listar as
  reais antes de escrever.
- **Descrição sem evidência é pior que nenhuma** (constitution III): se não achar no SQL, no coletor ou nos docs,
  deixe sem descrição. Nada de dado pessoal nas descrições do Idealista.
- **`dbt docs generate --empty-catalog` abre uma conexão DuckDB**: aponte `CAOP_DUCKDB_PATH` para dentro da pasta de
  saída, nunca para `.data/ci/caop.duckdb`.
- **Windows não troca arquivo aberto**: o `os.replace` do catálogo falha se o DBeaver estiver com ele aberto; trate.
- **O lake tem mais coisa que tabela**: CSVs (`mobility_*.csv`, `coverage.csv`...) e pastas de relatório
  (`census_reports`, `wikipedia_reports`, `idealista_reports`) não são tabelas; só `<camada>/<tabela>/data.parquet`.
- **`dbt` precisa estar no PATH** nos testes que rodam o `dbt parse` real: use sempre `uv run --locked python -m pytest`.
- **Pytest e `%TEMP%`**: se o pytest recusar o diretório temporário padrão, use `--basetemp` (ex.: `.pytest_tmp`).
- **Não altere `.sql`, `data_tests` nem `analytics/dbt/dbt_project.yml`**; a Fase 4 só acrescenta `description`,
  `data_type` e `meta`.
- **Servidor local**: o `--serve` é um servidor de desenvolvimento em `127.0.0.1`, não um serviço. Mantenha só localhost.

## Pendências do Analyze

| ID | Sev. | Resumo | Recomendação |
| --- | --- | --- | --- |
| A-001 | MEDIUM | FR-025 diz "sem servidor", mas `dbt_docs_site --serve` sobe um servidor local | Entender FR-025 como "nenhum serviço implantado ou com custo"; manter `--serve` só em `127.0.0.1` e opcional |
| A-002 | MEDIUM | SC-002, SC-007 e US3-AC3 (qualidade das descrições) só se verificam por revisão humana | Revisão do autor ao fechar a Fase 4 (R-007) |
| A-003 | LOW | A verificação visual da aresta no grafo (R-002) não é automatizável | T027 do quickstart; fallback descrito em `logic/site.md` |
| A-004 | LOW | O verificador de trava não conta testes (`unknown`) | Contagem de 5 conferida à mão |

## Gate de pronto

- 5/5 contratos verdes + trava íntegra; `uv run --locked ruff check pipelines tests` limpo; suíte completa verde
  (hoje 715 testes coletados: 710 antigos + 5 contratos).
- `model_docs --check` com exit 0; documento commitado igual ao gerado; CI remoto verde (`quality` e gitleaks).
- `dbt build` de cada domínio continua verde no CI depois das mudanças nos `schema.yml`.
- Consulta de completude em `meta.columns` vazia para as 18 principais (registrar no Registro da Fase 4).
- Docs a atualizar no Polish: `README.md`, `.docs/runbooks/modelo_de_dados.md`, `.docs/fontes_de_dados.md` (uma linha) e
  a nota em `.planning/memory/`.
- Passada manual no navegador (T027) é **gate** para fechar a Fase 5 (R-002).
