# Tasks: Ingestão Pordata e INE

**Input**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/ingestao-cli.md`, `logic/ingestao-datasets.md`.

**Prerequisites**: `spec.md` e `plan.md`; testes de contrato travados em `contract-tests.lock`; spec 001 convergida (usa a Silver `dim_municipality`, `names.py`, `LocalStorage`/`S3Storage`).

**Organization**: setup → fundação → US1 (P1) → US2 (P2) → US3 (P2) → US4 (P3) → US5 (P3) → Polish. IDs `T001`–`T036` estáveis. `[P]` = arquivos independentes. Contratos travados não são editados pelo executor.

## Path Conventions

- Código em `pipelines/collectors/_shared/` (comum), `pipelines/collectors/pordata/` e `pipelines/collectors/ine/` (por fonte), CLIs em `pipelines/cli/`.
- dbt em `analytics/dbt/` (`models/bronze/`, `seeds/`, `tests/`). Catálogo em `config/sources.yml`.
- Testes em `tests/{contracts,unit,integration,fixtures}/`; fixtures novas em `tests/fixtures/pordata/`, `tests/fixtures/ine/` e `tests/fixtures/observations/`.
- Dados locais em `.data/` e temporários do pytest em `.pytest_tmp/`, ambos ignorados pelo Git. Nenhum bruto real no Git.
- **Não editar** `pipelines/collectors/caop/*`, `pipelines/collectors/_shared/manifest.py` nem `tests/contracts/test_caop_collection_contract.py`; a CAOP só muda onde uma task disser (T005).

## Phase 1: Setup (Shared Infrastructure)

**Objetivo**: instalar a única dependência nova.

### Implementation

- [X] T001 Adicionar `openpyxl` às dependências de `pyproject.toml` e regravar `uv.lock` (`uv lock`, depois `uv sync --locked`), sem alterar as versões das demais (R-005, FR-023).

**Critério de Conclusão**: `uv sync --locked` instala; `uv run --locked python -c "import openpyxl"` funciona; `uv run --locked ruff check pipelines tests` limpo.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T001).
- Feito: `openpyxl` adicionado a `pyproject.toml` como `openpyxl>=3.1,<4` (o `uv add` escreveu `>=3.1.5`; alinhado ao padrão de teto de versão das demais dependências) e `uv.lock` regravado (91 pacotes; instalados `openpyxl 3.1.5` e `et-xmlfile 2.0.0`, sem mudar as demais versões).
- Contrato: sem contrato nesta fase; `check-contract-tests.ps1` das specs 001 e 002 → PASS, trava íntegra. Os 5 contratos da 002 seguem vermelhos nos stubs.
- Testes executados: `uv lock` → 91 pacotes resolvidos; `uv sync --locked` → sincronizado; `uv run --locked python -c "import openpyxl"` → 3.1.5; `uv run --locked ruff check pipelines tests` → All checks passed.
- Pendências: nenhuma.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Objetivo**: catálogo de datasets, download genérico, manifest v2 e isolamento do dbt da CAOP.

### Implementation

- [X] T002 [P] Estender `pipelines/collectors/_shared/catalog.py` com `get_dataset_source(catalog, source_id)` (exige `datasets` não vazio, `id` único, `license_id` e `collection_method`; não exige `urls` por região) e adicionar `pordata` (16 datasets `http_download` + `poder_compra_per_capita_xlsx` `manual_upload`) e `ine` (3 indicadores) a `config/sources.yml`, conforme `data-model.md`. O caminho da CAOP (`get_source`) e `load_catalog` continuam validando a CAOP como hoje (FR-001, FR-002, FR-022).
- [X] T003 [P] Em `pipelines/collectors/_shared/http.py`, parametrizar a checagem do primeiro bloco de `HttpDownloader` (`content_check`), mantendo o ZIP como padrão para a CAOP; oferecer checagens de CSV (não HTML, não vazio) e de JSON (começa com `[` ou `{`); aceitar `timeout` por instância e devolver os cabeçalhos `ETag`/`Last-Modified` da última resposta (FR-003, R-002).
- [X] T004 [P] Criar `pipelines/collectors/_shared/dataset_manifest.py`: construir e validar o manifest v2, codificá-lo em JSON estável e implementar `latest_dataset_states(storage, source_id)` (entrada `changed` mais recente por `dataset_id`, por horário e depois `run_id`; `failed` nunca é estado; `unchanged` herda `key`/`sha256`), conforme `data-model.md` e `logic/ingestao-datasets.md` §1 (FR-005, FR-006).
- [X] T005 Isolar o dbt da CAOP: marcar com a tag `caop` os modelos `stg_caop_*`, `dim_*` e o teste `analytics/dbt/tests/caop_quality.sql` (em `dbt_project.yml` ou `schema.yml`) e fazer `build_caop._run_dbt` e o passo de `dbt build` de `.github/workflows/python.yml` usarem `--select tag:caop`. **Deve ser a primeira task a tocar o dbt**: os modelos novos só entram depois (R-007).

### Testes da Fase

- [X] T006 [P] Testes unitários em `tests/unit/test_dataset_catalog_and_manifest.py` e `tests/unit/test_http_content_checks.py`: catálogo de datasets (ids duplicados, dataset sem `id`, fonte ausente), manifest v2 (status da execução; `partial` conta como estado dos datasets bem-sucedidos; `failed` e `unchanged` nunca são estado; desempate por `run_id`), `content_check` (CSV aceito, HTML recusado, ZIP continua o padrão). Rodar também `tests/integration/test_caop_build.py` para provar que a CAOP segue verde com `--select tag:caop`.

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/unit tests/integration/test_caop_build.py --basetemp .pytest_tmp` verde; `uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:caop` com 31/31 passos após `python -m tests.fixtures.caop.ci_seed --root .data/ci`; `check-contract-tests.ps1` íntegro para as duas specs.

**Checkpoint**: fundação pronta; a CAOP intacta.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T002–T006).
- Feito: T002: `catalog.py` ganhou `get_dataset_source`/`validate_dataset_source` (fonte e datasets validados antes da rede, ids únicos, HTTPS para `http_download`, `indicator` para `api_json`, `manual_upload` sem origem) com padrões herdados da fonte (`expected_labels`, `name_column`, `api_url`); `load_catalog` valida as fontes com `datasets` no modo estrito e a CAOP como antes; `config/sources.yml` com `pordata` (16 CSV + `poder_compra_per_capita_xlsx` manual, `license_id: not_granted_by_source`, R-001) e `ine` (`0014698`, `0008074` com `Dim3=T,1,2,3,4,5,6` e `0014580`). T003: `http.py` com `content_check` configurável (`zip_content_check` continua o padrão da CAOP; `csv_content_check` e `json_content_check` novos) e `last_headers` com `ETag`/`Last-Modified` da última resposta. T004: `dataset_manifest.py` (manifest v2, `run_status`, validação de entradas, `latest_dataset_states`). T005: tags `caop` nos modelos `staging`/`marts` e no teste singular, e `--select tag:caop` em `build_caop._run_dbt` e no job `quality` do CI. T006: testes unitários. Desvio de design: `expected_labels`/`name_column` ficam no nível da fonte (herdados), e não repetidos em cada dataset; `data-model.md` atualizado.
- Contrato: `check-contract-tests.ps1` das specs 001 e 002 → PASS, trava íntegra; `tests/contracts/test_caop_collection_contract.py` → 5/5 verdes; os 5 contratos da 002 seguem vermelhos nos stubs (esperado até as Fases 3 a 5).
- Testes executados: `uv run --locked ruff check --fix pipelines tests` → limpo (1 reordenação de imports em teste novo); `uv run --locked python -m pytest -q tests/unit tests/integration/test_caop_build.py tests/contracts/test_caop_collection_contract.py --basetemp .pytest_tmp` → 54 passed; `uv run --locked python -m tests.fixtures.caop.ci_seed --root .data/ci` + `uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:caop` → PASS=31 (4 modelos + 27 testes, incluindo o singular `caop_quality`), idêntico à linha de base. Carga real do catálogo: 3 fontes, 17 datasets do Pordata (16 HTTP + 1 manual) e 3 do INE.
- Pendências: nenhuma. Observação: o CI remoto ainda não rodou com `--select tag:caop`; fica para a T036.

---

## Phase 3: User Story 1 - Coletar o Pordata com rastreabilidade (Priority: P1) 🎯 MVP

**Objetivo**: um comando coleta os 16 CSV do Pordata, cada um com estado próprio, e uma falha não bloqueia os demais.

**Independent Test**: com fetcher simulado, coletar num destino local vazio, repetir (`unchanged`), alterar um dataset (só ele grava) e forçar falhas (parcial, código 1).

### Contrato da Fase

- `test_us1_ac1_fr004_fr005_every_dataset_is_stored_with_its_own_manifest_entry`
- `test_us1_ac2_ac3_fr006_unchanged_is_per_dataset_and_only_the_changed_one_writes_raw`
- `test_us1_ac4_ac5_fr007_fr008_failures_do_not_block_the_others_nor_become_state`
- Comando: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp -k "us1"`

### Implementation

- [X] T007 Implementar `collect_datasets` em `pipelines/collectors/_shared/datasets.py` conforme `logic/ingestao-datasets.md` §1: pré-checagens (catálogo, `run_id`, `preflight`, `list_keys()` uma vez), loop sequencial por dataset (fetch → validação → impressão digital → comparar com o estado → gravar só se mudou), `failed` por dataset com limpeza da chave nova, status da execução e manifest sempre gravado; aceitar `fetcher` que devolve um `dict` opcional (cabeçalhos HTTP) → contratos: os três de US1 (FR-002, FR-004 a FR-008).
- [X] T008 [P] [US1] Criar `pipelines/collectors/pordata/validate.py` com o validador do CSV pelo rótulo (remover o prefixo numérico `^\s*(Max\. )?\d+\.\s*`, UTF-8, não HTML, ≥ 1 linha `Município`), conforme `logic/ingestao-datasets.md` §3 (FR-008, D4).
- [X] T009 [US1] Criar `pipelines/collectors/pordata/handler.py` (monta o fetcher com `HttpDownloader` e `rate_limiter` de 1 s, o validador e `collect_datasets` para os datasets `http_download`) e `pipelines/cli/collect_pordata.py` (`--local`/`--s3 --bucket [--prefix]`, `--root`, resumo por dataset, código 1 para `partial`/`failed`), conforme `contracts/ingestao-cli.md` (FR-003, FR-009 a FR-011).
- [X] T010 [P] [US1] Criar fixtures sintéticas em `tests/fixtures/pordata/`: CSV mínimos nos três layouts reais (9 colunas com `Escala` antes de `Símbolo`; 10 colunas com `Nome País`; dataset 4 com `Max. 08. Escala`), com linhas de agregação, símbolos `r`, `x`, `-`, `...` e valores vazios.

### Testes da Fase

- [X] T011 [P] [US1] `tests/unit/test_pordata_validate.py`: os três layouts passam; HTML, arquivo vazio, rótulo ausente e ausência de linha `Município` reprovam com mensagem que cita o rótulo.
- [X] T012 [US1] `tests/integration/test_collect_pordata_local.py`: CLI com fetcher offline: primeira coleta `changed`, segunda `unchanged` sem raw novo, um dataset alterado grava só ele, fonte ou dataset fora do catálogo é recusado antes da rede, um dataset com HTML devolve `partial` com código 1 e os demais gravados.
- [X] T013 [P] [US1] `tests/integration/test_collect_pordata_s3.py` com moto: paridade de chaves e manifest com o modo local, e escrita negada falhando antes de qualquer download.

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp -k "us1"` → 3/3 verdes e `check-contract-tests.ps1 -Slug 002-ingestao-pordata-ine` íntegro; testes adicionais verdes; CLI local sem credenciais.

**Checkpoint**: User Story 1 funcional e testável isoladamente.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T007–T013).
- Feito: T007: `collect_datasets` em `_shared/datasets.py` (pré-checagens antes da rede, estado vigente por dataset lido uma vez, loop sequencial fetch → validação → impressão digital → comparação → gravação, `failed` por dataset com limpeza best effort, manifest v2 sempre gravado e raw removido se o manifest falhar); aceita `dataset_ids` opcional (para a CLI separar HTTP e manual) e um `fetcher` que pode devolver `etag`/`last_modified`/`reference_period`/`source_release_date`. T008: `pordata/validate.py` valida e indexa o CSV pelo rótulo limpo (`clean_label`, `label_index`). T009: `pordata/handler.py` (`collect_pordata`, só datasets `http_download`), `cli/collect_pordata.py` e `cli/_common.py` (destino local/S3, `run_id`, resumo por dataset e código de saída 0/1, compartilhado com as CLIs seguintes). T010: `tests/fixtures/pordata/layouts.py` com os três layouts reais, agregação, símbolos e downloader offline. T011–T013: testes unitários, de CLI local (incluindo falha parcial, fonte fora do catálogo e execução concorrente, que cobre o achado A-002 do Analyze) e de S3 simulado (paridade de chaves e manifest com o local, escrita negada antes de qualquer download).
- Contrato: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp -k "us1"` → 3/3 verdes; `check-contract-tests.ps1` das specs 002 e 001 → PASS, trava íntegra. Os outros 2 contratos da 002 seguem vermelhos nos stubs (Fases 4 e 5).
- Testes executados: `uv run --locked ruff check pipelines tests` → All checks passed; suíte completa sem os 2 contratos pendentes (`--deselect` por nome) → 87 passed; Fase 3 isolada → 20 passed na primeira execução. Duas correções de lint durante a fase (`try/except/pass` virou `contextlib.suppress`; `open()` virou `Path.read_text`).
- Pendências: Nenhuma. Observação: o `HttpDownloader` real (timeout 120 s, 1 s entre pedidos) só será exercitado contra o Pordata na T035.

---

## Phase 4: User Story 2 - Coletar rendas, criminalidade e poder de compra do INE (Priority: P2)

**Objetivo**: um comando consulta a API do INE para os 3 indicadores com a mesma garantia de estado e de falha, sem falsos `changed`.

**Independent Test**: com respostas gravadas, coletar, repetir com outro `DataExtracao` (`unchanged`), mudar um valor (`changed`) e simular a API fora do ar (`failed`).

### Contrato da Fase

- `test_fr006_ine_response_is_unchanged_when_only_the_extraction_time_differs`
- Comando: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp -k "ine"`

### Implementation

- [X] T014 Implementar `fingerprint_ine_response` em `pipelines/collectors/ine/fingerprint.py` conforme `logic/ingestao-datasets.md` §2 (remover só `DataExtracao`, JSON canônico, `sha256`; a lista de chaves ignoradas num único lugar) → contrato: `test_fr006_ine_response_is_unchanged_when_only_the_extraction_time_differs` (FR-006, R-008).
- [X] T015 [P] [US2] Criar `pipelines/collectors/ine/validate.py` (`Sucesso`/`Msg == "OK"`, `IndicadorCod` igual ao pedido, `Dados` não vazio, ao menos um `geocod` de 7 caracteres) e `pipelines/collectors/ine/fetch.py` (monta `https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=<cod>&lang=PT` com `params` do catálogo; `HttpDownloader` com `content_check` de JSON, timeout de 90 s, 3 tentativas e espera crescente) (FR-008, FR-009, R-002).
- [X] T016 [US2] Criar `pipelines/collectors/ine/handler.py` e `pipelines/cli/collect_ine.py` (mesma superfície de `collect_pordata`; `fingerprint=fingerprint_ine_response`) (FR-003, FR-010, FR-011).
- [X] T017 [P] [US2] Criar fixtures em `tests/fixtures/ine/`: JSON sintético no formato real (período, `geocod` de 7 caracteres, `valor`, `ind_string`, `sinal_conv`, `dim_3`) com ausências, e um gerador que muda só o `DataExtracao`.

### Testes da Fase

- [X] T018 [P] [US2] `tests/unit/test_ine_validate_and_fetch.py`: URL montada para os 3 indicadores (incluindo `Dim3=T,1,2,3,4,5,6`), JSON válido e inválidos (`Sucesso` ausente, `Dados` vazio, código trocado), retentativa após timeout simulado.
- [X] T019 [US2] `tests/integration/test_collect_ine_local.py`: CLI com fetcher offline: `changed`, `unchanged` com outro `DataExtracao`, `changed` com valor alterado, um indicador falho devolve `partial` com código 1.

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp -k "ine"` → 1/1 verde e trava íntegra; testes adicionais verdes.

**Checkpoint**: US1 e US2 funcionais; as duas fontes coletam de forma independente.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T014–T019).
- Feito: T014: `ine/fingerprint.py` — SHA-256 do JSON canônico sem `DataExtracao`; as chaves voláteis ficam numa só constante (`VOLATILE_KEYS`, R-008). T015: `ine/validate.py` (erro da API, indicador trocado, `Dados` vazio, sem código municipal de 7 caracteres, JSON inválido) e `ine/fetch.py` (`build_url` com os parâmetros do catálogo, incluindo `Dim2=lvl@5` e `Dim3=T,1,2,3,4,5,6`; `make_ine_fetcher` devolve `reference_period` = `UltimoPref` e `source_release_date` = `DataUltimoAtualizacao` lidos da própria resposta). T016: `ine/handler.py` (`collect_ine`) e `cli/collect_ine.py` (timeout de 90 s, 3 tentativas, espera de 2 s e 2 s entre pedidos, via `HttpDownloader` com `json_content_check`). T017: `tests/fixtures/ine/responses.py` (JSON no formato real, com ausência por `sinal_conv` e categorias de crime). T018–T019: testes unitários e de CLI local; a paridade local×S3 do INE foi acrescentada a `test_collect_pordata_s3.py` (achado A-003 do Analyze).
- Contrato: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp -k "ine"` → 1/1 verde; no arquivo inteiro, 4/5 verdes (US1: 3, INE: 1) e 1 vermelho no stub (resolução de município, Fase 5); `check-contract-tests.ps1` das specs 002 e 001 → PASS, trava íntegra.
- Testes executados: `uv run --locked ruff check --fix pipelines tests` → All checks passed; suíte completa sem o contrato pendente (`--deselect` por nome) → 101 passed. Uma iteração a mais: o teste de falha parcial do INE falhou na primeira execução por erro da asserção (a chave do raw contém o id do dataset duas vezes), corrigido no teste; o código estava correto.
- Pendências: Nenhuma. O `HttpDownloader` do INE (90 s, 3 tentativas) e o `unchanged` da impressão digital contra a API real serão confirmados na T035 (R-008).

---

## Phase 5: User Story 3 - Staging por município com o código oficial (Priority: P2)

**Objetivo**: do estado vigente de cada dataset, produzir `stg_observation` com `dico` resolvido, testado e promovido sem tocar a CAOP.

**Independent Test**: com brutos de fixture e uma Silver sintética, rodar `build_observations` e conferir chaves, relação com `dim_municipality`, falha por nome sem correspondência e a CAOP intacta.

### Contrato da Fase

- `test_us3_ac2_ac3_fr013_fr014_homonyms_use_explicit_rules_and_unresolved_names_fail`
- Comando: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp -k "us3"`

### Implementation

- [X] T020 Implementar `resolve_municipality_names` em `pipelines/collectors/_shared/municipality.py` conforme `logic/ingestao-datasets.md` §5, reutilizando `normalize_name` de `pipelines/collectors/caop/names.py` (sem segunda implementação) → contrato: `test_us3_ac2_ac3_fr013_fr014_homonyms_use_explicit_rules_and_unresolved_names_fail` (FR-013, FR-014, FR-020).
- [X] T021 [US3] Criar `pipelines/collectors/_shared/observations.py` (esquema do Parquet longo e escritor), `pipelines/collectors/pordata/transform.py` (CSV → longo pelos rótulos, só `Município`, contagem de agregação, `value` vazio → nulo, unidade sem espaços) e `pipelines/collectors/ine/transform.py` (JSON → longo, `dico = geocod[-4:]`, `symbol = sinal_conv`, categoria em `filter_1`), conforme `logic/ingestao-datasets.md` §4 (FR-012, FR-015, FR-016, FR-017).
- [X] T022 [US3] Criar o dbt das observações com a tag `observations`: `analytics/dbt/models/bronze/sources.yml` (source da Silver `dim_municipality` por `external_location`), `analytics/dbt/seeds/municipality_synonyms.csv` (5 linhas do `research.md` R4), `models/bronze/stg_observation.sql` (materialização `external`, `options: {partition_by: [source_id, dataset_id]}`, resolução pelo seed e pelo sufixo do INE), `schema.yml` e os testes singulares `analytics/dbt/tests/observations_*.sql` (nome sem correspondência, chave única, `dico` na dimensão, `value` nulo exige `symbol`) (FR-012, FR-013, FR-018, FR-022).
- [X] T023 [US3] Criar `pipelines/cli/build_observations.py` (`--local --root`): exigir a Silver da CAOP, escolher o estado vigente de cada dataset e verificar o `sha256` do bruto, preparar o Parquet, rodar `dbt build --select tag:observations` em área temporária e promover **só** `lake/bronze/stg_observation` e `lake/bronze/rpt_observation_coverage` (com backup e desfazer em falha; **não** reutilizar `_promote` da CAOP, R-006); descrever em `contracts/ingestao-cli.md`.
- [X] T024 [P] [US3] Criar `tests/fixtures/observations/ci_seed.py` (Silver sintética de 308 municípios incluindo os homônimos, brutos sintéticos de Pordata e INE em um `LocalStorage`) e o passo correspondente no job `quality` de `.github/workflows/python.yml` (`dbt build --select tag:observations`).

### Testes da Fase

- [X] T025 [P] [US3] `tests/unit/test_observation_transforms.py`: os três layouts de CSV, símbolos preservados, vazio → nulo (nunca 0), agregação contada, JSON do INE (ausência por `sinal_conv`, categorias de crime), período como inteiro.
- [X] T026 [US3] `tests/integration/test_build_observations.py`: build completo sobre as fixtures; chave única e `dico` ∈ Silver; nome sem correspondência reprova, lista os nomes e mantém o staging anterior; **o `lake/bronze/stg_caop_*` e o `lake/silver/*` ficam byte a byte iguais**; `build_caop` continua verde depois.

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp` → 5/5 verdes e `check-contract-tests.ps1` íntegro para as duas specs; `dbt build --select tag:observations` verde sobre a fixture; CAOP intacta.

**Checkpoint**: US1 a US3 funcionais; as 5 provas de contrato verdes.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T020–T026).
- Feito: T020: `resolve_municipality_names` em `_shared/municipality.py` (sinônimo por grafia exata; senão nome normalizado **único**; ambiguidade ou ausência reprova com a lista ordenada), reutilizando `normalize_name` da CAOP. T021: `_shared/observations.py` (esquema e `finalize` com a proveniência), `pordata/transform.py` (CSV lido pelo rótulo com pandas: só `Município`, agregação contada, vazio → nulo, símbolo preservado) e `ine/transform.py` (categoria em `filter_1`, códigos não municipais excluídos). T022: dbt das observações com a tag `observations` — `models/bronze/stg_observation.sql` (externa, casts explícitos), `schema.yml` (source `caop_silver` por `external_location`, `not_null` e `relationships` com a Silver), testes singulares `observations_key_unique` e `observations_null_needs_symbol`, e o seed `municipality_synonyms.csv` (5 linhas). T023: `cli/build_observations.py` (estado vigente de cada dataset com conferência de `sha256`, resolução, Parquet longo, `dbt build --select tag:observations` em área temporária, promoção) e `cli/_promote.py` (`promote_paths`, por tabela, com backup e desfazer); o `build_caop` passou a usar a mesma promoção por tabela. T024: `tests/fixtures/observations/ci_seed.py` (Silver sintética com os homônimos e brutos coletados pelos próprios coletores) e os passos de observações no job `quality` do CI. T025–T026: testes unitários das transformações e do `promote_paths`, e de integração do build.
- Contrato: `uv run --locked python -m pytest -q tests/contracts --basetemp .pytest_tmp` → 10/10 verdes (5 da 002 e 5 da CAOP); `check-contract-tests.ps1` das specs 002 e 001 → PASS, trava íntegra. **Os 5 contratos da 002 estão verdes.**
- Testes executados: `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 118 passed; `dbt build --select tag:caop` (após `ci_seed` da CAOP) → PASS=31; `dbt build --select tag:observations` (após `ci_seed` de observações) → PASS=11 (1 modelo + 10 testes). As transformações foram validadas contra os 16 CSV e as respostas do INE **reais** baixados na pesquisa: 1.137.444 observações municipais no Pordata, 308 nomes por dataset, 0 valores nulos sem símbolo; INE rendas 1.848 linhas (438 nulos) e criminalidade 25.872 (308 × 12 × 7). Iterações: 1 asserção minha errada na validação ad hoc (o símbolo `r` convive com valor presente), corrigida; os 16 testes da fase passaram na primeira execução.
- Pendências: Nenhuma da fase. O modelo `rpt_observation_coverage` (US4) e o dataset manual (US5) entram nas Fases 6 e 7; `_reader` já prevê `read_pordata_xlsx`, que ainda não existe e só é chamado quando houver estado do dataset manual.

---

## Phase 6: User Story 4 - Relatório de cobertura por dataset (Priority: P3)

**Objetivo**: tornar a ausência visível por dataset, sem imputar nada.

**Independent Test**: com fixtures em que alguns municípios não têm valor, conferir contagens e a lista de ausentes.

### Implementation

- [X] T027 [US4] Criar `analytics/dbt/models/bronze/rpt_observation_coverage.sql` (tag `observations`; definição do `data-model.md`: município com ≥ 1 valor não nulo no último período; `missing_dico`; agregação excluída) e fazer `build_observations` imprimir a tabela e gravar `<root>/lake/bronze/coverage.csv` com a lista de ausentes (FR-019).

### Testes da Fase

- [X] T028 [US4] `tests/integration/test_observation_coverage.py`: 290 de 308 com valor → 18 ausentes listados; dataset sem dado no período recente informa cobertura zero e o último período com dados; ausência nunca vira 0 no staging.

**Critério de Conclusão**: testes verdes; `coverage.csv` legível por pessoa; nenhuma regressão nas fases anteriores.

**Checkpoint**: US4 funcional.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T027–T028).
- Feito: T027: `analytics/dbt/models/bronze/rpt_observation_coverage.sql` (tag `observations`): por dataset, `latest_period`, `latest_period_with_data`, `municipalities_expected` (lido da Silver), `municipalities_with_value` (≥ 1 valor não nulo no último período), `municipalities_without_value`, `missing_dico` e `aggregate_rows_excluded` (vindo de `dataset_stats.parquet`); testes `not_null`/`unique` no `schema.yml` e o singular `observations_coverage_consistency` (com + sem = esperado; a lista de ausentes tem o tamanho de "sem valor"). `build_observations` ganhou `write_coverage` (grava `lake/bronze/coverage.csv`, separador `;`, UTF-8 com BOM, com cada ausente por código e nome), `format_coverage` (tabela no terminal, incluindo os datasets ainda não coletados) e o retorno com `coverage` e `not_collected`. A fixture de observações ganhou `rendas_latest_empty` e o diretório de saída do novo modelo é pré-criado (o DuckDB não o cria). T028: `tests/integration/test_observation_coverage.py` (5 testes, 4 deles compartilham um único build por módulo).
- Contrato: sem contrato novo nesta fase; `uv run --locked python -m pytest -q tests/contracts --basetemp .pytest_tmp` → 10/10 verdes; `check-contract-tests.ps1` das specs 002 e 001 → PASS, trava íntegra.
- Testes executados: `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 123 passed; `uv run --locked dbt build --select tag:observations` → PASS=17 (2 modelos + 15 testes); `--select tag:caop` segue 31. Uma iteração a mais: o primeiro build com o modelo de cobertura falhou porque o diretório de saída `rpt_observation_coverage` não existia, corrigido pré-criando todos os diretórios de `PROMOTED`. A suíte de cobertura levou 90 s antes de compartilhar o build e 19 s depois.
- Pendências: Nenhuma. A cobertura real (308 por dataset, rendas do INE em ~247) será conferida na T035.

---

## Phase 7: User Story 5 - Carregar a planilha do Pordata à mão (Priority: P3)

**Objetivo**: entregar a planilha de poder de compra como bruto rastreável e tratá-la no staging.

**Independent Test**: com uma planilha sintética no layout real, carregar, repetir (`unchanged`), entregar uma inválida (`failed`) e construir o staging.

### Implementation

- [X] T029 [US5] Criar `pipelines/collectors/pordata/xlsx.py`: validação com `openpyxl` somente leitura (abas `Quadro` e `Metainformação`, linha de cabeçalho com `Anos` e colunas de ano, exatamente 308 linhas `Município`) e a leitura para o formato longo (cada coluna de ano vira uma observação; célula vazia → nulo; `unit = "Número índice (Portugal = 100)"`), integrada a `pordata/transform.py` (FR-023, D9).
- [X] T030 [US5] Criar `pipelines/cli/load_pordata_manual.py` conforme `contracts/ingestao-cli.md`: chama `collect_datasets` com um fetcher que copia o arquivo do operador para o temporário, validador de planilha e destino `--local`/`--s3`; código 1 para planilha inválida (FR-023).
- [X] T031 [P] [US5] Criar `tests/fixtures/pordata/xlsx.py`: gerador, com `openpyxl`, de uma planilha sintética no layout real (abas, cabeçalho na linha 12, 308 municípios, linhas `NUTS`, rodapé de símbolos).

### Testes da Fase

- [X] T032 [P] [US5] `tests/unit/test_pordata_xlsx.py`: planilha válida; aba ausente, sem cabeçalho de anos e com menos de 308 municípios reprovam; leitura para o formato longo.
- [X] T033 [US5] `tests/integration/test_load_pordata_manual.py`: carga `changed`, repetição `unchanged`, arquivo inválido `failed` sem bruto, e `build_observations` incluindo o dataset com `dico` resolvido pela seed.

**Critério de Conclusão**: testes verdes; o arquivo de origem do operador nunca é alterado; nenhuma planilha real no Git.

**Checkpoint**: US5 funcional.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T029–T033).
- Feito: T029: `pordata/xlsx.py` (`parse_pordata_xlsx`/`validate_pordata_xlsx` com `openpyxl` somente leitura: arquivo que não é planilha, abas `Quadro` e `Metainformação`, cabeçalho `Âmbito Geográfico | Anos`, exatamente 308 linhas `Município`) e `read_pordata_xlsx` em `pordata/transform.py` (uma observação por município e ano; agregações NUTS contadas; célula vazia → nulo com o símbolo `vazio`; texto no lugar do número → nulo com esse símbolo; nunca zero); a unidade do dataset passou a ficar no catálogo. T030: `pordata/manual.py` (`load_pordata_manual`, que só lê o arquivo do operador e recusa dataset que não é de carga manual) e `cli/load_pordata_manual.py` (`--file`, `--dataset`, destino local/S3, recusa arquivo inexistente sem escrever manifest, código 1 para planilha inválida). T031: `tests/fixtures/pordata/xlsx.py` (planilha sintética no layout real, com opções para fabricar planilhas inválidas). T032–T033: testes unitários da planilha e de integração da carga manual (changed → unchanged → changed, arquivo do operador intacto, falha sem bruto, e o dataset entrando no staging com `Lagoa` e `Lagoa [R.A.A.]` resolvidos pela seed). A paridade local×S3 da carga manual foi acrescentada a `test_collect_pordata_s3.py` (A-003 do Analyze, agora cobrindo as três CLIs).
- Contrato: sem contrato novo nesta fase; `uv run --locked python -m pytest -q tests/contracts --basetemp .pytest_tmp` → 10/10 verdes (5 da 002 e 5 da CAOP); `check-contract-tests.ps1` das specs 002 e 001 → PASS, trava íntegra.
- Testes executados: `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 135 passed; `dbt build --select tag:observations` → PASS=17; `--select tag:caop` → PASS=31. **Validação com a planilha real do autor** (somente leitura, `sha256` do arquivo idêntico antes e depois): 308 municípios × 11 anos (1993–2021) = 3.388 observações, 45 linhas NUTS excluídas, nenhum valor nulo, unidade correta.
- Pendências: Nenhuma da fase. A carga real pela CLI e a entrada no staging real ficam para a T035.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Objetivo**: consolidar documentação, verificação real e os gates.

### Implementation

- [X] T034 [P] Atualizar `README.md`, `docs/runbooks/coletas.md` e `.docs/fontes_de_dados.md`: os 4 comandos novos, as atribuições do INE (CC BY 4.0) e do Pordata, o R-001, a correção de que as rendas do INE **não** cobrem os 308 municípios (222 a 247), os URLs reais do Pordata e a decisão de poder de compra (API do INE + carga manual), e como reprocessar (FR-022).
- [X] T035 Executar `quickstart.md` com fixtures e uma coleta real: `collect_pordata` (~82 MB), `collect_ine`, `load_pordata_manual` com a planilha do autor e `build_observations`; registrar status por dataset, o `unchanged` do segundo run do INE (confirma a impressão digital, R-008) e a tabela de cobertura; manter tudo fora do Git (SC-001, SC-007).
- [X] T036 Gate final: `ruff`, `pytest` completo, `dbt build` das duas tags, `check-contract-tests.ps1` das duas specs, `gitleaks` via Docker, CI no GitHub; atualizar `plan.md`, `tasks.md` e `.planning/backlog.md` como o `sdd-execute` prescreve (SC-006).

### Testes da Fase

- [X] Conferir a suíte completa, o S3 simulado, os dois `dbt build` e que nenhum teste automatizado exige rede.

**Critério de Conclusão**: todos os FR/SC rastreados; contratos 5/5 verdes e travas íntegras; lint, dbt, pytest e CI verdes; quickstart executado; documentação e backlog sincronizados.

**Registro da Fase**:

- Status: concluída em 2026-11-11 (T034–T036), com **uma pendência**: o run do CI no GitHub, que exige o envio da branch.
- Feito: T034: `README.md` (status, atribuições do INE e do Pordata, estrutura), `docs/runbooks/coletas.md` (seção nova com `collect_pordata`, `collect_ine`, `load_pordata_manual`, `build_observations`, leitura de `partial` e da cobertura, como exportar a planilha, licenças, layout do raw e o estado da verificação real) e `.docs/fontes_de_dados.md` (licença do Pordata, cobertura das rendas do INE, códigos do INE, layout do raw, `HEAD` descartado, estrutura de código); `plan.md` e `data-model.md` corrigidos nas frases sobre particionamento e resolução no dbt (R-010). T035: coleta real (ver Testes). T036: gate final (ver Testes). **Achado da coleta real (R-008 se materializando):** a API do INE devolve as mesmas linhas da criminalidade em **ordem diferente** entre chamadas (2 de 12 períodos, zero diferença de conteúdo), o que fez `taxa_criminalidade` aparecer como `changed` na 2.ª coleta; a impressão digital passou a ordenar os registros, com teste de regressão (`tests/unit/test_ine_fingerprint.py`, 4 testes) e a correção confirmada nas duas respostas reais. Os estados gravados com o algoritmo anterior foram descartados (só os que eu tinha acabado de criar em `.data`) e a coleta foi refeita.
- Contrato: `uv run --locked python -m pytest -q tests/contracts --basetemp .pytest_tmp` → 10/10 verdes (5 da 002 e 5 da CAOP); `check-contract-tests.ps1` das specs 002 e 001 → PASS, trava íntegra. Nenhum arquivo de contrato foi editado.
- Testes executados: **Coleta real (T035, `--root .data`):** `collect_pordata` → 16 datasets `changed` em 43 s, tamanhos idênticos aos da pesquisa; `collect_ine` → 3 `changed` e, repetido duas vezes, 3 `unchanged` (após a correção da impressão digital); `load_pordata_manual` com a planilha do autor → `changed`, e de novo `unchanged`, com o `sha256` do arquivo idêntico antes e depois; `build_observations` contra a Silver real → **1.168.860 observações de 20 datasets em 15 s**, todos os 308 municípios resolvidos pelas 5 grafias do seed, 0 `dico` nulo, 121.642 nulos todos com símbolo, nenhum dado em `lake/gold` ou `published`, e `lake/silver` e `stg_caop_*` com o `sha256` idêntico antes e depois. Cobertura real: rendas do INE 247/308 em 2025; `ensino_nao_superior` 0/308 em 2024 (último período com dados: 2023); `ensino_superior` 63/308 em 2025; `desemprego_registado` 278/308; os demais 308/308. **Gate local (T036):** `uv run --locked ruff check pipelines tests` → All checks passed; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 139 passed; `dbt build --select tag:caop` (após `ci_seed` da CAOP) → PASS=31; `--select tag:observations` (após `ci_seed` de observações) → PASS=17. **`gitleaks` v8.30.1 via Docker:** modo `dir` sobre 327 arquivos atuais (inclui o código novo ainda não commitado) → no leaks; modo `git` sobre 7 commits (como no CI) → no leaks. **Reprodução do job `quality` em container Linux** (Python 3.12.12, a partir dos arquivos atuais, com os passos novos): ruff limpo, 138 passed e 1 skipped (o teste do prefixo de caminho do Windows, esperado), `dbt build` 31 e 17 passos. `git status` sem dado real, planilha ou credencial; `.data` e `.pytest_tmp` ignorados. Iterações: a fixture de cobertura precisou do diretório de saída do novo modelo pré-criado; um helper inútil (`nl_join`) foi removido; um `try/except/pass` virou `contextlib.suppress`.
- Pendências: (1) **CI no GitHub:** a branch ainda não foi enviada com estas mudanças, então o workflow `Python quality` (jobs `quality` e `secrets`) não rodou para elas; por isso o item "CI e `gitleaks` verdes" do Checklist de Release fica **aberto**. A evidência local (`gitleaks` e reprodução em Linux) é forte, mas não substitui o run real. (2) R-001 (licença do Pordata) e R-004 (rendas do INE em ~80% dos municípios) seguem como riscos conhecidos do dado, não da implementação. (3) O dataset Pordata 845 continua sem URL (fora do escopo).

### Checklist de Release

- [X] Fase 1 (setup) concluída.
- [X] Fase 2 (fundação) concluída.
- [X] Fase 3 (US1) concluída.
- [X] Fase 4 (US2) concluída.
- [X] Fase 5 (US3) concluída.
- [X] Fase 6 (US4) concluída.
- [X] Fase 7 (US5) concluída.
- [X] Cinco contratos verdes no `pytest` completo; `check-contract-tests.ps1` íntegro para 001 e 002.
- [ ] `ruff`, `pytest` e `dbt build` (tags `caop` e `observations`) verdes com fixtures sem rede; CI e `gitleaks` verdes.
- [X] Atribuições do INE e do Pordata e o R-001 documentados; nenhum bruto real nem credencial no Git.
- [X] `quickstart.md` executado; coleta real distinguida da prova automatizada.
- [X] Spec 001 e seu lake inalterados (contrato da CAOP verde, `lake/silver` e `stg_caop_*` intactos).
- [X] Nenhum Silver de indicadores, Gold, `published/` nem deploy AWS introduzido.

---

## Dependencies & Execution Order

- Setup → Foundational (bloqueia tudo; **T005 antes de qualquer modelo dbt novo**) → US1 → US2 → US3 → US4 → US5 → Polish.
- US2 reutiliza `collect_datasets` (T007) e pode ser feita em qualquer ordem depois da US1. US3 depende do bruto da US1/US2 e da Silver da spec 001. US4 estende o dbt da US3. US5 depende da US1 (coleta) e da US3 (staging).
- MVP verificável: terminar até a US1 e parar para conferir os 3 contratos e a CLI local.

## Rastreabilidade

| Requisito | Tasks principais |
| --- | --- |
| FR-001, FR-022 | T002, T034 |
| FR-002 | T007, T012 |
| FR-003 | T003, T009, T016 |
| FR-004, FR-005, FR-006 | T004, T007, T014 |
| FR-007, FR-008 | T007, T008, T015 |
| FR-009 | T015, T016 |
| FR-010, FR-011 | T009, T013, T016 |
| FR-012, FR-013, FR-014 | T020, T021, T022 |
| FR-015, FR-016, FR-017 | T021, T022 |
| FR-018 | T022, T026 |
| FR-019 | T027, T028 |
| FR-020 | T020, T022 |
| FR-021 | T006, T011–T013, T018, T019, T025, T026, T028, T032, T033 |
| FR-023 | T029, T030, T033 |
| SC-001 | T012, T019, T035 |
| SC-002 | T007, T012 |
| SC-003 | T022, T026 |
| SC-004 | T021, T027, T028 |
| SC-005 | T013 |
| SC-006 | T036 |
| SC-007 | T035 |
