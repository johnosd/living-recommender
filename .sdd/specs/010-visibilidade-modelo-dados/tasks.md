---
description: "Lista de tasks da spec 010 - visibilidade do modelo de dados"
---

# Tasks: Visibilidade do modelo de dados

**Input**: Documentos de design de `.sdd/specs/010-visibilidade-modelo-dados/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, logic/documento.md, logic/site.md

**Organization**: tasks agrupadas por user story. Stubs já existem em `pipelines/modeldocs/*.py` e
`pipelines/cli/model_docs.py` com `NotImplementedError("Tnnn: ...")`; o número da task que os implementa está na mensagem.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: US1 = documento (A), US2 = catálogo DuckDB (B), US3 = descrições, US4 = site do dbt (C)

## Path Conventions

- Lógica: `pipelines/modeldocs/` (pacote novo); CLIs finas: `pipelines/cli/{model_docs,lake_catalog,dbt_docs_site}.py`
- Metadados: `analytics/dbt/models/<domínio>/schema.yml` (só `description`, `data_type`, `meta`)
- Documento gerado: `.docs/modelo_de_dados.md`; runbook: `.docs/runbooks/`
- Testes: `tests/unit/test_modeldocs_*.py` e `tests/integration/test_modeldocs_*.py`; contratos travados em
  `tests/contracts/test_modeldocs_contract.py`
- Comando de teste: `uv run --locked python -m pytest <alvo> -q --basetemp .pytest_tmp`

**Restrições do executor**: os 3 arquivos travados (`tests/contracts/test_modeldocs_contract.py`,
`tests/fixtures/modeldocs/manifests.py`, `tests/fixtures/modeldocs/lake.py`) **não** se editam. Não altere `.sql`, não
remova teste dbt e não crie dependência nova.

## Phase 1: Foundational (blocking)

**Purpose**: ler o manifest do dbt e montar o `DataModel`. Bloqueia todas as stories.

### Contrato da Fase

- `test_a_relationship_to_a_table_that_does_not_exist_fails_naming_file_model_and_target` — FR-009
- Comando: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k does_not_exist`

### Implementation

- [X] T001 Implementar `load_model` e `run_dbt_parse` em `pipelines/modeldocs/model.py`, seguindo `logic/documento.md` §1 e §2 (layer por regex em `config.location`, domínio = `tags[0]`, kind por nome, `''` vira `None`, testes por coluna dos nós `test` com `test_metadata`, **caminhos do Windows normalizados**, relacionamento com fonte resolvendo para o modelo homônimo, `ModelError` com arquivo/modelo/alvo, ordem determinística). `run_dbt_parse` usa `shutil.which("dbt")` e `subprocess`, define `DBT_TARGET_PATH`, `DBT_LOG_PATH` e `CAOP_DUCKDB_PATH` dentro de `target_path` e levanta `RuntimeError` clara se o `dbt` faltar ou falhar → contrato: `test_a_relationship_to_a_table_that_does_not_exist_fails_naming_file_model_and_target`
- [X] T003 [P] Implementar `load_sources_info` em `pipelines/modeldocs/render.py`: lê `config/sources.yml` e devolve `{id: {"license_id": ..., "attribution": ...}}` (`attribution` ausente = `None`)

### Testes da Fase

- [X] T002 [P] Testes de `load_model` em `tests/unit/test_modeldocs_model.py` com `make_manifest` e com o manifest real (`parse_real_manifest`): camada e domínio, `kind`, descrição vazia vira `None`, colunas e testes, teste singular ignorado, `origin_file` igual com `\` e com `/`, alvo `ref` e alvo `source` resolvidos, ordem estável, `run_dbt_parse` real devolve ≥ 25 modelos

**Critério de Conclusão**: o contrato de FR-009 passa (`... -k does_not_exist` → 1/1 verde), `uv run --locked python -m pytest tests/unit/test_modeldocs_model.py -q` verde, ruff limpo e `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados` íntegro.

**Checkpoint**: o `DataModel` do projeto real carrega sem erro.

**Registro da Fase**:

- Status: Concluída (2026-11-22)
- Feito: `load_model` e `run_dbt_parse` em `pipelines/modeldocs/model.py` (T001); `load_sources_info` em `render.py` (T003); `tests/unit/test_modeldocs_model.py` com 8 testes (T002). O `DataModel` do projeto real carrega com 25 tabelas e 15 relacionamentos, todos resolvidos para modelos.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k does_not_exist` → 1/1 verde; `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados` → trava íntegra.
- Testes executados: `uv run --locked python -m pytest tests/unit/test_modeldocs_model.py -q --basetemp .pytest_tmp` → 8/8 verdes; ruff limpo. Uma iteração só (um heredoc do shell quebrou a gravação do arquivo; regravado com a ferramenta de escrita).
- Pendências: nenhuma.

---

## Phase 2: User Story 1 - Documento com diagrama e dicionário (Priority: P1) 🎯 MVP

**Objetivo**: `uv run --locked python -m pipelines.cli.model_docs` gera `.docs/modelo_de_dados.md`, e o CI reprova se ele ficar defasado.

**Independent Test**: sem lake, gerar o documento, conferir os 25 modelos e as 15 arestas, gerar de novo e comparar.

### Contrato da Fase

- `test_the_document_is_complete_deterministic_and_free_of_values_and_local_paths` — US1-AC1/AC2/AC5, SC-001
- `test_gaps_are_explicit_never_invented_and_territorial_keys_without_a_relationship_are_listed` — US1-AC3, FR-003/018
- `test_check_mode_flags_a_stale_document_names_the_regenerating_command_and_ignores_line_endings` — US1-AC4, FR-008
- Comando: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k "document or gaps or check_mode"`

### Implementation

- [X] T004 [US1] Implementar `render_markdown` em `pipelines/modeldocs/render.py` exatamente como em `logic/documento.md` §3 e §4: resumo, diagrama Mermaid (uma linha de aresta por relacionamento, entidades só com as colunas de chave), lacunas (cobertura com arredondamento meia-para-cima, `Sem descrição`, `Chaves territoriais sem relacionamento declarado`) e dicionário (`### <tabela>`), sem data, caminho, `run_id` nem valor → contrato: `test_the_document_is_complete_deterministic_and_free_of_values_and_local_paths`, `test_gaps_are_explicit_never_invented_and_territorial_keys_without_a_relationship_are_listed`
- [X] T005 [US1] Implementar `main` em `pipelines/cli/model_docs.py` conforme `contracts/cli.md` §1: `--check`, `--output`, `--manifest`, `--sources`; grava sempre com LF; compara ignorando `\r\n`; arquivo ausente conta como defasado; imprime a mensagem com o comando que regenera; códigos 0/1/2; `ModelError` vira exit 1 com a mensagem → contrato: `test_check_mode_flags_a_stale_document_names_the_regenerating_command_and_ignores_line_endings`
- [X] T007 [US1] Gerar o primeiro `.docs/modelo_de_dados.md` com o comando; acrescentar o passo `Check data model document` (`uv run --locked python -m pipelines.cli.model_docs --check`) em `.github/workflows/python.yml` logo depois do passo `Test without external services`, sem condição `hashFiles` (o `dbt parse` não usa fixture nem lake); linkar o documento no `README.md` e em `.docs/fontes_de_dados.md` (uma linha); criar a seção "Modelo de dados" no `.docs/runbooks/` (arquivo novo `.docs/runbooks/modelo_de_dados.md`) com o comando e o que fazer quando o CI acusar defasagem

### Testes da Fase

- [X] T006 [P] [US1] Testes de `render_markdown` e da CLI em `tests/unit/test_modeldocs_render.py`: modelo sem entrada no schema.yml, tabela sem colunas declaradas, relatório com a observação, tabela principal sem a observação, `Fontes` (com licença, fonte desconhecida, sem `source_ids`, atribuição do Google), arredondamento 0,5 → cima, `d == 0` → `n/d`, entidades do diagrama sem repetir atributos, `Nenhuma.` quando não há lacuna, `\n` final, CLI com `--manifest` de manifest real

**Critério de Conclusão**: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k "document or gaps or check_mode"` → 3/3 verdes e `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados` íntegro; `uv run --locked python -m pipelines.cli.model_docs --check` → exit 0 sobre o arquivo commitado; o documento real lista 25 tabelas e 15 relacionamentos, e a seção de lacunas cita, por exemplo, `census_observation.dico`.

**Checkpoint**: o autor consegue ler tabelas e relacionamentos sem abrir código.

**Registro da Fase**:

- Status: Concluída (2026-11-22)
- Feito: `render_markdown` (T004) e `pipelines/cli/model_docs.py` (T005); `.docs/modelo_de_dados.md` gerado com 25 tabelas e 15 relacionamentos (T007); passo `Check data model document` em `.github/workflows/python.yml`, logo depois do `Test without external services`; links no `README.md` e em `.docs/fontes_de_dados.md`; `.docs/runbooks/modelo_de_dados.md` criado (seção do documento); `tests/unit/test_modeldocs_render.py` com 9 testes (T006). Desvio: as colunas `dataset_id` de `stg_observation` e `rpt_observation_coverage` ganharam `description` no `bronze/schema.yml` (ver R-011).
- Contrato: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k "document or gaps or check_mode"` → 3/3 verdes; trava íntegra.
- Testes executados: `uv run --locked python -m pytest tests/unit/test_modeldocs_render.py -q --basetemp .pytest_tmp` → 9/9 verdes; `uv run --locked python -m pipelines.cli.model_docs --check` → exit 0; `uv run --locked ruff check pipelines tests` limpo (2 correções automáticas de importação e uma de string implícita).
- Pendências: R-011 (a asserção `".data" not in document` do contrato 1 casa com qualquer coluna chamada `dataset_id` sem descrição; proposta de emenda do contrato para `.data/` aguarda decisão do autor). Cobertura atual: tabelas 88%, colunas 2%; a Fase 4 corrige as colunas.

---

## Phase 3: User Story 2 - Catálogo DuckDB único (Priority: P2)

**Objetivo**: `uv run --locked python -m pipelines.cli.lake_catalog` gera `.data/catalog.duckdb` com as tabelas do lake, os metadados e o inventário do `raw/`.

**Independent Test**: com o lake real, abrir o arquivo e conferir contagens, um `JOIN` entre fontes e `meta.raw_runs`.

### Contrato da Fase

- `test_the_catalog_exposes_every_lake_table_without_copying_or_touching_the_lake` — US2-AC1/2/3/5/6/7, FR-010/011/013/014/015
- Comando: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k catalog`

### Implementation

- [X] T008 [US2] Implementar `build_catalog` em `pipelines/modeldocs/catalog.py` conforme `data-model.md` §2.1 e §2.2: varrer `<lake_root>/{bronze,silver}/<tabela>/data.parquet`; criar schemas `bronze`, `silver`, `meta`; uma `VIEW` com caminho absoluto por tabela; `meta.tables`, `meta.columns` (união de colunas declaradas e reais, `declared`, `in_lake`, `type_actual`, `type_declared`) e `meta.relationships`; status `ok`/`nao_construida`/`sem_modelo`; entradas do lake que não são tabelas vão para `ignored`; gravar em temporário ao lado e `os.replace` no final; nunca abrir arquivo do lake para escrita → contrato: `test_the_catalog_exposes_every_lake_table_without_copying_or_touching_the_lake`
- [X] T009 [US2] Implementar o inventário `meta.raw_runs` em `pipelines/modeldocs/catalog.py` conforme `data-model.md` §2.3 (um registro por manifest legível, data = primeiro não nulo entre `collected_at_utc`, `checked_at_utc`, `imported_at_utc`, `checksums` por varredura da chave `sha256` em qualquer profundidade, manifest ilegível conta como ignorado) → contrato: mesmo teste de T008 (`result.raw_runs == 2`, `meta.raw_runs` com 2 linhas)
- [X] T010 [US2] Criar `pipelines/cli/lake_catalog.py` conforme `contracts/cli.md` §2 (`--root`, `--output`, `--manifest`; resumo no console com tabelas por status, ignorados, manifests lidos/ignorados e tamanho; falha de `os.replace` vira exit 1 com a mensagem "feche o cliente SQL ..." sem apagar o catálogo anterior)

- [X] T012 [US2] Escrever em `.docs/runbooks/modelo_de_dados.md` a seção do catálogo: o comando, o que cada schema contém, três consultas de exemplo (listar tabelas, `JOIN` entre fontes, ver colunas não declaradas em `meta.columns`), como abrir no DuckDB UI e no DBeaver (driver DuckDB, caminho do arquivo, somente leitura), o aviso de fechar o cliente antes de regenerar e de regenerar se `.data/` mudar de lugar. **Teste cada comando de abertura antes de documentá-lo** (duckdb 2.0.0 instalado): a UI sobe com `CALL start_ui()` a partir de uma sessão que continue aberta (por exemplo `uv run --locked python -c "import duckdb; c = duckdb.connect('.data/catalog.duckdb'); c.execute('CALL start_ui()'); input('Enter para encerrar')"`), e o CLI `duckdb -ui` só serve se estiver instalado; documente só o que funcionou

### Testes da Fase

- [X] T011 [P] [US2] Testes em `tests/unit/test_modeldocs_catalog.py` e `tests/integration/test_modeldocs_catalog_cli.py`: `meta.columns` marca coluna real não declarada (`declared = false`) e divergência entre `type_declared` e `type_actual`; `meta.raw_runs` extrai `sha256` de `files[]`, `datasets[]`, `entries[].files[]` e `snapshot_sha256`, usa `checked_at_utc` quando falta `collected_at_utc`; manifest com JSON inválido não derruba; falha do `os.replace` (monkeypatch) mantém o arquivo anterior e dá exit 1; `--root` sem `lake/` termina com sucesso e tudo `nao_construida`; consulta cruzando duas fontes

**Critério de Conclusão**: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k catalog` → 1/1 verde e `check-contract-tests.ps1` íntegro; com o lake real, `uv run --locked python -m pipelines.cli.lake_catalog --root .data` gera o arquivo, as 25 tabelas aparecem com `status = ok` e a contagem de cada uma bate com `read_parquet`.

**Checkpoint**: o autor consulta qualquer tabela no DuckDB UI ou DBeaver.

**Registro da Fase**:

- Status: Concluída (2026-11-22)
- Feito: `build_catalog` com views sobre os parquets, `meta.tables`, `meta.columns`, `meta.relationships` (T008) e `meta.raw_runs` (T009); CLI `pipelines/cli/lake_catalog.py` (T010); seção do catálogo em `.docs/runbooks/modelo_de_dados.md` com o comando de abertura testado (T012). `CatalogResult` ganhou o campo `manifests_ignored` (o resumo da CLI precisa dele). Com o lake real: 25 tabelas `ok`, 43 manifests de 9 fontes, 13 entradas ignoradas, arquivo de 1,59 MB, 345 colunas reais ainda não declaradas (alvo da Fase 4).
- Contrato: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp -k catalog` → 1/1 verde; `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados` → trava íntegra.
- Testes executados: `uv run --locked python -m pytest tests/unit/test_modeldocs_catalog.py tests/integration/test_modeldocs_catalog_cli.py -q --basetemp .pytest_tmp` → 10/10 verdes (6 unitários + 4 de CLI) depois de uma correção: o `executemany` do DuckDB recusa lista vazia (modelo sem relacionamento ou sem manifests); agora há `_insert_many` e o temporário é apagado em qualquer falha. Conjunto do modeldocs: 32/32; ruff limpo. Consultas de exemplo do runbook rodadas no catálogo real; `CALL start_ui()` testado em duckdb 2.0.0 (a primeira vez baixa a extensão; o CLI `duckdb` não está instalado).
- Pendências: a abertura no navegador/DBeaver não foi exercitada de ponta a ponta nesta sessão (só o servidor subiu e respondeu `UI started at http://localhost:4213/`).

---

## Phase 4: User Story 3 - Descrições das tabelas principais (Priority: P2)

**Objetivo**: as 18 tabelas principais ficam com descrição de tabela, de **todas** as colunas, tipo e fonte nos `schema.yml`.

**Independent Test**: gerar o catálogo e a consulta `select table_name, column_name from meta.columns c join meta.tables t using (layer, table_name) where t.kind = 'principal' and (not declared or description is null or type_declared is null or lower(type_actual) <> lower(type_declared))` volta vazia.

**Regras (D9)**: para cada tabela, liste as colunas e tipos reais com `meta.columns` (T008) e descreva cada coluna a partir do `.sql` do modelo, do coletor (`pipelines/collectors/<fonte>/`), de `.docs/fontes_de_dados.md` e das specs em `.sdd/specs/`. **Sem evidência, não escreva descrição** (a coluna fica declarada, com `data_type`, e aparece como "sem descrição" nas lacunas). Descrição diz o que o campo é e a unidade ou convenção (km, minutos, estados), sem repetir o nome. `meta.source_ids` usa só ids existentes em `config/sources.yml`. Não mexa em `data_tests` nem em `.sql`.

### Implementation

- [X] T013 [P] [US3] CAOP: `analytics/dbt/models/staging/schema.yml` (`stg_caop_municipalities`, `stg_caop_parishes`) e `analytics/dbt/models/marts/schema.yml` (`dim_municipality`, `dim_parish`)
- [X] T014 [P] [US3] Observações e clima: `analytics/dbt/models/bronze/schema.yml` (`stg_observation`; `rpt_observation_coverage` fica como está) e `analytics/dbt/models/climate/schema.yml` (`stg_climate_daily`)
- [X] T015 [P] [US3] Correspondência e Idealista: `analytics/dbt/models/crosswalk/schema.yml` (`xwalk_parish_2013_2025`) e `analytics/dbt/models/idealista/schema.yml` (`idealista_listings`, `idealista_occurrences`; atenção: nada de dado pessoal nas descrições, só significado)
- [X] T016 [P] [US3] Censos: `analytics/dbt/models/censos/schema.yml` (`census_age_category`, `census_observation`, `census_parish_observation`; `census_coverage` fica como está)
- [X] T017 [P] [US3] Wikipedia: `analytics/dbt/models/wikipedia/schema.yml` (`wikipedia_revision`, `wikipedia_article`, `wikipedia_section`, `wikipedia_block`) e descrição de tabela para `wikipedia_block`, `wikipedia_section` e `wikipedia_coverage`, hoje sem nenhuma
- [X] T018 [P] [US3] Mobilidade: `analytics/dbt/models/mobility/schema.yml` (`dim_mobility_pole`, `stg_municipality_pole_distance`); fontes `caop` e `google_distances` com a atribuição já em `config/sources.yml`

### Testes da Fase

- [X] T019 [US3] `tests/unit/test_modeldocs_principal_described.py`: com o manifest real, para uma **lista fixa** das 18 principais (constante no teste; modelos novos não são cobrados) conferir descrição de tabela, `description` e `data_type` em toda coluna declarada, `meta.source_ids` com ids existentes em `config/sources.yml`, e que `data_type` esteja em minúsculas. Depois rodar localmente a consulta do "Independent Test" contra o lake real e registrar o resultado (0 linhas) no Registro da Fase

**Critério de Conclusão**: `uv run --locked python -m pytest tests/unit/test_modeldocs_principal_described.py -q --basetemp .pytest_tmp` verde; a consulta de `meta.columns` sobre o lake real volta vazia para as 18 principais; `uv run --locked python -m pipelines.cli.model_docs` regenerado, commitado, com cobertura de descrição das principais em 100% (as lacunas restantes são só relatórios); `dbt parse` sem aviso novo; `dbt build` de cada domínio continua verde no CI.

**Checkpoint**: o dicionário explica o dado, não só lista nomes. O autor revisa os textos antes do merge (R-007).

**Registro da Fase**:

- Status: Concluída (2026-11-22); textos revisados pelo autor em 2026-11-24 (R-007)
- Feito: as 18 tabelas principais ficaram com descrição de tabela, `meta.source_ids`, e **todas** as colunas reais declaradas com `description` e `data_type` (364 colunas, 345 delas novas), nos 9 `schema.yml` (T013 a T018). `wikipedia_section`, `wikipedia_block` e `wikipedia_coverage` ganharam descrição de tabela. Os `data_tests` e os `.sql` não foram tocados; a geração conferiu por parse que todo teste, e todo modelo fora da lista, ficou semanticamente igual. Cada texto vem do SQL, do coletor (`pipelines/collectors/*`), de `config/` ou dos valores reais do lake; onde o coletor não deixa certeza o texto diz "pode ser nulo" em vez de afirmar. `pipelines/modeldocs/catalog.py` passou a gravar o tipo `NULL` sem aspas (o DuckDB devolve `"NULL"` para colunas inteiramente nulas), o que permitiu declarar `data_type: "null"` nessas colunas sem divergência (hoje `symbol` nos censos). Documento regerado: cobertura de descrição tabelas 100% das principais e colunas 100% das principais (95% no total; as lacunas restantes são só relatórios).
- Contrato: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes; trava íntegra.
- Testes executados: `uv run --locked python -m pytest tests/unit/test_modeldocs_principal_described.py -q --basetemp .pytest_tmp` → 19/19 verdes (lista fixa das 18 + conferência de que a lista é exatamente o conjunto das principais); consulta de completude em `meta.columns` sobre o lake real (principais com `not declared` ou sem descrição ou sem `type_declared` ou com tipo divergente) → **0 linhas**; `model_docs --check` → exit 0; `dbt parse` sem aviso novo; ruff limpo.
- Pendências: (1) revisão humana dos textos (SC-002, SC-007, US3-AC3); (2) o `dbt build` de cada domínio só roda em T026; (3) R-011: com os dois `dataset_id` descritos o contrato 1 passa, mas continua frágil a colunas `data*` sem descrição.

---

## Phase 5: User Story 4 - Grafo e catálogo no dbt (Priority: P3)

**Objetivo**: `uv run --locked python -m pipelines.cli.dbt_docs_site --serve` abre o site do dbt docs com a aresta `dim_municipality` → `caop_silver.dim_municipality`.

**Independent Test**: gerar o site e conferir, no `manifest.json` gerado, o `child_map` do modelo `dim_municipality` contendo a fonte `source.caop_territory.caop_silver.dim_municipality`; abrir no navegador (T027).

### Implementation

- [X] T020 [US4] Implementar `link_sources_to_models` em `pipelines/modeldocs/site.py` conforme `logic/site.md` (cópia profunda, `parent_map` e `child_map`, sem duplicar, fonte sem modelo homônimo intacta)
- [X] T021 [US4] Implementar `lake_catalog_json` em `pipelines/modeldocs/site.py` conforme `logic/site.md` (`DESCRIBE` do parquet, colunas reais inclusive as não declaradas, sem valores, vazio quando não há lake)
- [X] T022 [US4] Criar `pipelines/cli/dbt_docs_site.py` conforme `contracts/cli.md` §3 e `logic/site.md` (sequência com `dbt docs generate --empty-catalog`, `CAOP_DUCKDB_PATH` e `DBT_TARGET_PATH` dentro da saída, ligar fontes, catálogo do lake, `--serve` só em `127.0.0.1` via `dbt docs serve --host 127.0.0.1 --no-browser`)

### Testes da Fase

- [X] T023 [P] [US4] `tests/unit/test_modeldocs_site.py` e `tests/integration/test_modeldocs_site_cli.py`: `link_sources_to_models` não altera o dict de entrada, liga `dim_municipality` e `dim_parish`, não duplica na segunda aplicação e ignora fonte sem modelo; `lake_catalog_json` com lake minúsculo (`write_table`) traz as colunas reais, sem lake ou com lake parcial (modelo sem parquet) devolve só o que existe, sem erro (US4-AC4); a CLI, com `dbt` injetado ou real, gera `index.html`, `manifest.json` com a aresta e `catalog.json`, e não cria nada em `.data/ci` nem altera o lake (hash antes/depois)
- [X] T024 [US4] Seção do site no `.docs/runbooks/modelo_de_dados.md`: o comando, `--serve`, a URL, como achar o grafo de uma tabela, e a observação de que o site é local e não é publicado

**Critério de Conclusão**: `uv run --locked python -m pytest tests/unit/test_modeldocs_site.py tests/integration/test_modeldocs_site_cli.py -q --basetemp .pytest_tmp` verde; `uv run --locked python -m pipelines.cli.dbt_docs_site --root .data` gera `.data/dbt-docs/index.html` com os 25 modelos e a aresta de `dim_municipality`; a verificação visual do T027 feita.

**Checkpoint**: o autor navega o lineage no dbt.

**Registro da Fase**:

- Status: Concluída (2026-11-24): gate visual feito pelo autor no navegador (T027/R-002)
- Feito: `link_sources_to_models` e `lake_catalog_json` em `pipelines/modeldocs/site.py` (T020, T021; `lake_catalog_json` ganhou o parâmetro opcional `base` para herdar o `metadata` do catálogo vazio do dbt); `pipelines/cli/dbt_docs_site.py` (T022) com `dbt docs generate --empty-catalog`, aresta fonte→modelo no manifest, catálogo do lake e `--serve` só em `127.0.0.1`; seção do site no runbook (T024). Com o lake real: `.data/dbt-docs/` com `index.html`, 25 modelos, `child_map` de `dim_municipality` e `dim_parish` contendo as fontes `caop_silver.*`, e 25 nós em `catalog.json`; `.data/ci` ficou sem nenhum arquivo.
- Contrato: sem contrato nesta fase (os 5 contratos seguem 5/5 verdes; trava íntegra).
- Testes executados: `uv run --locked python -m pytest tests/unit/test_modeldocs_site.py tests/integration/test_modeldocs_site_cli.py -q --basetemp .pytest_tmp` → 11/11 verdes (6 unitários, 5 de CLI com o dbt real: aresta no manifest, catálogo só do que existe no lake, lake com hash idêntico antes e depois, sem lake, sem `dbt` → exit 2, `--serve` só em 127.0.0.1); ruff limpo. Uma iteração a mais: o `DBT_TARGET_PATH` relativo era resolvido a partir de `analytics/dbt/`; a CLI agora usa caminho absoluto, e o resíduo criado em `analytics/dbt/.data/dbt-docs` foi removido.
- Pendências: **conferir no navegador o grafo de `dim_municipality`** (o navegador embutido da sessão não abre `localhost` subido por ela, então o autor faz o passo 4 do `quickstart.md`); se a aresta não aparecer, vale o fallback do R-002 (anotar o modelo produtor na descrição da fonte).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T025 Atualizar `README.md` (links para o documento e para o runbook, três comandos em uma tabela curta), `.docs/fontes_de_dados.md` se necessário e gravar uma nota em `.planning/memory/` (`modelo-de-dados-010-execucao.md`) com os achados duráveis (por exemplo: `dbt parse` sem banco, fonte do dbt não liga ao modelo, manifest com barra invertida no Windows, `''` em descrição, CRLF)
- [X] T026 Revalidar: `uv run --locked ruff check pipelines tests`, suíte completa, `uv run --locked python -m pipelines.cli.model_docs --check`, `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados`, `dbt build` de cada domínio sobre os fixtures (como no CI) e o CI remoto do PR verde (incluindo gitleaks)
- [X] T027 Rodar o `quickstart.md` de ponta a ponta no lake real e conferir no navegador a aresta de `dim_municipality` no grafo (R-002); registrar o resultado

**Registro do Polish (2026-11-22)**: T025 feito (README com tabela de comandos, nota `.planning/memory/modelo-de-dados-010-execucao.md`, links em `.docs/fontes_de_dados.md`). T026 só parcial: `ruff check pipelines tests` limpo, suíte completa **773 passed**, `model_docs --check` exit 0, trava íntegra e `dbt build` de cada domínio sobre os fixtures (réplica local dos passos do CI: caop, observations, climate, crosswalk, idealista e censos com `ERROR=0 SKIP=0`, mais Wikipedia e mobilidade promovidos) sem nenhum erro; **falta o CI remoto do PR (incluindo gitleaks)**, que exige commit e push. T027 **não feito**: falta o passo manual no navegador (grafo de `dim_municipality`) e o `quickstart.md` de ponta a ponta pelo autor. Fase 4 e Fase 5 seguem com os respectivos gates humanos (revisão dos textos, conferência visual).

**Revalidação (2026-11-24)**, na branch `feature/010-visibilidade-modelo-dados`, ainda sem commit: `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados` → trava íntegra; `uv run --locked ruff check pipelines tests` → limpo; `uv run --locked python -m pipelines.cli.model_docs --check` → exit 0; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → **775 passed** (10 min 29 s). Pendências inalteradas: CI remoto (exige commit e push), T027 no navegador e revisão dos textos (R-007).

**Fechamento de T026 e T027 (2026-11-24)**: o autor fez commit (`71f81aa`), push e abriu o PR #12, que já está mergeado. CI remoto `Python quality`: execução `45395460346` (push), `quality` = success; execução `45398644435` (pull_request), `quality` = success e `secrets` (gitleaks) = success. T027: o autor conferiu no navegador a aresta `dim_municipality` → `caop_silver.dim_municipality` no grafo do dbt docs (informado pelo autor na sessão), o que fecha R-002 sem precisar do plano B.

### Checklist de Release

- [X] Fase 1 (Foundational) concluída
- [X] Fase 2 (US1 documento) concluída
- [X] Fase 3 (US2 catálogo DuckDB) concluída
- [X] Fase 4 (US3 descrições) concluída e revisada pelo autor
- [X] Fase 5 (US4 dbt docs) concluída
- [X] Testes de contrato todos verdes na suíte completa e `check-contract-tests.ps1` íntegro
- [X] `ruff check pipelines tests` limpo e suíte completa verde
- [X] `model_docs --check` verde e documento commitado igual ao gerado (exit 0; o commit ainda não foi feito, a pedido do autor)
- [X] Nenhum arquivo em `raw/` ou `lake/` alterado pelos três comandos
- [X] Constitution I (segredos) e VI (nenhum valor de dado no documento versionado) conferidos; gitleaks verde
- [X] `quickstart.md` executado com sucesso

---

## Dependencies & Execution Order

- **Fase 1** bloqueia todas as outras. T001 antes de T002; T003 independente.
- **Fase 2 (US1)**: T004 depende de T001 e T003; T005 depende de T004; T006 e T007 depois de T005.
- **Fase 3 (US2)**: depende da Fase 1; T008 antes de T009 e T010; T011 e T012 depois.
- **Fase 4 (US3)**: T013 a T018 só dependem de T008 e T010 (para listar colunas reais) e podem rodar em paralelo, cada
  uma em arquivos yml diferentes; T019 depois de todas.
- **Fase 5 (US4)**: depende da Fase 1 e, para o `catalog.json`, de T008; T020 e T021 antes de T022.
- **Polish**: depois de todas as stories desejadas.
- As Fases 3 e 5 não dependem da Fase 2. O MVP é a Fase 2.

## Implementation Strategy

1. Fase 1 → Fase 2: o autor já enxerga tabelas e relacionamentos (MVP).
2. Fase 3 → Fase 4: catálogo para consultar os dados reais e dicionário com significado.
3. Fase 5: grafo no dbt.
4. Cada fase termina com o checkpoint do `sdd-execute`; commits curtos, em inglês, por grupo coerente.

## Notes

- `[P]` = arquivos diferentes, sem dependência
- Em Windows o `dbt` pode ser chamado como `dbt` ou `uv run --locked dbt`; dentro de `uv run` o `shutil.which("dbt")` basta
- Se o pytest recusar o `%TEMP%` padrão por permissão, use `--basetemp .pytest_tmp`

<!-- sdd-converge anexa "## Phase N: Convergence" abaixo desta linha -->

## Phase 7: Convergence

**Origem**: `sdd-converge` de 2026-11-24 (achados C-001 a C-004). Contratos 5/5 verdes e trava íntegra no momento da auditoria.

- [X] T028 [US4] (C-001, MEDIUM; origem US4-AC2, FR-020, SC-006) Conferir no site (`uv run --locked python -m pipelines.cli.dbt_docs_site --root .data --serve`) se o grafo liga `stg_municipality_pole_distance` a `dim_municipality`. Hoje essa ligação existe só pelo teste `relationships` (`analytics/dbt/models/mobility/schema.yml:77`): o modelo lê o parquet por `env_var` e o `parent_map` dele no manifest do site está vazio. Abra o lineage de `stg_municipality_pole_distance` com os nós de teste visíveis e registre o resultado. Se a ligação não aparecer, pare e leve a decisão ao autor: (a) emendar o exemplo da spec para um caso de linhagem real (por exemplo, `rpt_climate_coverage` depende de `caop_silver.dim_municipality`); ou (b) `link_sources_to_models` passa a criar também a aresta modelo→modelo a partir de cada `relationships` declarado, só na cópia do site. A escolha vira um `R-012` em `plan.md`.
- [X] T029 [US4] (C-002, LOW; origem FR-018, US4-AC1) Decidir com o autor se o site do dbt pode mostrar o aviso padrão do dbt para descrição ausente, ou se a cópia do manifest do site deve receber "sem descrição" nas tabelas e colunas sem texto. Registrar a decisão em `plan.md` (`R-013`); se for preencher, implementar em `pipelines/modeldocs/site.py`, com teste em `tests/unit/test_modeldocs_site.py`, sem alterar os `schema.yml`.
- [X] T030 (C-004, LOW; origem plan: R-011) Levar ao autor a emenda do contrato 1 (`".data" not in document` → `".data/" not in document`). Se aprovada: editar só essa asserção em `tests/contracts/test_modeldocs_contract.py`, regravar a trava com `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados -Write` e marcar R-011 como `Resolvido:`. Se recusada: registrar o motivo em R-011.
- [X] T031 (C-003, LOW) Registrar em `plan.md` (`## Arquivos Principais` e `## Execution Notes`) a entrega a mais `.docs/sql/catalogo_tabelas.sql`, já citada em `.docs/runbooks/modelo_de_dados.md`.

**Critério de Conclusão**: T028 com o resultado da conferência registrado (e a decisão do autor, se houver); T029 e T030 com decisão registrada em `plan.md`; contratos 5/5 verdes e trava íntegra; `model_docs --check` com exit 0.

**Registro da Fase**:

- Status: Concluída (2026-11-24)
- Feito: decisões do autor em 2026-11-24 (opções recomendadas nas três). T028 → opção (b): `link_relationships(manifest, model)` em `pipelines/modeldocs/site.py` cria, só na cópia do manifest do site, a aresta `to_table` → `from_table` para cada `relationships` declarado (sem duplicar, sem autorreferência); a CLI `dbt_docs_site` aplica depois de `link_sources_to_models`. No site real, `stg_municipality_pole_distance` passou a ter como pais `dim_municipality` e `dim_mobility_pole`, e `dim_municipality` tem 8 modelos filhos mais a fonte; nenhum ciclo entre os 27 nós de modelo e fonte (R-012). T029 → aceito o aviso padrão do dbt para descrição ausente no site; nenhum código (R-013). T030 → emenda aprovada: a asserção do contrato 1 passou de `".data" not in document` para `".data/" not in document`, trava regravada com `-Write` (R-011 resolvido). T031 → `.docs/sql/catalogo_tabelas.sql` registrado no `plan.md`. Docs: `logic/site.md` (seção `link_relationships`) e a seção do site no runbook.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes (na leva abaixo); `check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados -Write` → trava regravada com a emenda aprovada; conferência seguinte → trava íntegra.
- Testes executados: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py tests/unit/test_modeldocs_site.py tests/integration/test_modeldocs_site_cli.py tests/unit/test_modeldocs_model.py tests/unit/test_modeldocs_render.py tests/unit/test_modeldocs_catalog.py tests/integration/test_modeldocs_catalog_cli.py tests/unit/test_modeldocs_principal_described.py -q --basetemp .pytest_tmp` → 68 passed (2 unitários novos de `link_relationships` e 1 de integração com o dbt real para a aresta de `stg_municipality_pole_distance`); `uv run --locked ruff check pipelines tests` → limpo depois de `--fix` em dois blocos de import; `uv run --locked python -m pipelines.cli.model_docs --check` → exit 0; `uv run --locked python -m pipelines.cli.dbt_docs_site --root .data` → exit 0.
- Pendências: suíte completa e CI remoto ainda não rodados com esta fase (as mudanças estão sem commit); conferir no navegador o grafo de `stg_municipality_pole_distance` é opcional (a aresta está no manifest pelo mesmo mecanismo já validado no R-002).
