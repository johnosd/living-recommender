---
description: "Lista de tasks da ingestão de clima Open-Meteo (spec 003)"
---

# Tasks: Ingestão de clima Open-Meteo — coleta diária por município e staging

**Input**: Documentos de design de `sdd/specs/003-ingestao-clima-open-meteo/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/clima-cli.md, logic/coleta-clima.md, quickstart.md

**Organization**: Tasks agrupadas por user story para implementação e teste independentes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: a user story da task (US1 a US4)
- Os caminhos são reais; `+` marca arquivo novo, `~` arquivo existente alterado

## Path Conventions

- Código da coleta: `pipelines/collectors/open_meteo/` (stubs já criados pelo plan: `handler.py`, `fetch.py`, `validate.py`, `fingerprint.py`, `transform.py`); comum em `pipelines/collectors/_shared/`.
- CLIs: `pipelines/cli/collect_open_meteo.py` e `pipelines/cli/build_climate.py` (padrão `collect_*`/`build_*`).
- dbt: `analytics/dbt/models/climate/` (tag `climate`) e `analytics/dbt/tests/climate_*.sql`.
- Testes: `tests/unit/`, `tests/integration/`, `tests/fixtures/climate/`; **contratos travados** em `tests/contracts/test_climate_collection_contract.py` e o helper `tests/fixtures/open_meteo/responses.py`: **não editar**.
- Dados locais em `.data/` (ignorado pelo Git). Caminhos S3 usam o mesmo prefixo relativo.
- Comandos: `uv run --locked ruff check pipelines tests` · `uv run --locked python -m pytest -q --basetemp .pytest_tmp`.
- **Gate em toda fase:** `check-contract-tests.ps1 -Slug 001-ingestao-caop`, `-Slug 002-ingestao-pordata-ine` e `-Slug 003-ingestao-clima-open-meteo` íntegros, e a suíte existente (140 testes) verde.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: registrar a fonte no catálogo e validá-la antes de qualquer rede (constitution IV).

- [X] T001 Acrescentar `open_meteo` a `config/sources.yml` exatamente como em `data-model.md` §1 (modelo `era5`, janela 2024-11-01 a 2026-10-31, 13 variáveis com unidade, `limits`, `point_divergence_km`, `usage_restriction`, atribuição) (FR-001, FR-022)
- [X] T002 ~ `pipelines/collectors/_shared/catalog.py`: `validate_climate_source`, `get_climate_source(catalog, "open_meteo", strict_metadata=False)` e o ramo de `load_catalog` para fontes com a chave `window`, seguindo a tabela de regras de `data-model.md` §1; fonte não cadastrada ou incompleta → `CatalogError` (FR-001, FR-002). Teste unitário em `tests/unit/test_climate_catalog.py`: catálogo real carrega; janela invertida, variável repetida, `api_url` HTTP, `expected_municipalities` ≤ 0 e fonte ausente reprovam; as fontes `caop`, `pordata` e `ine` continuam válidas.

**Checkpoint**: `load_catalog()` valida as quatro fontes.

---

**Registro da Fase**:

- Status: concluída
- Feito: Catálogo climático validado; fontes anteriores preservadas
- Contrato: três travas íntegras (001, 002, 003); contratos futuros permanecem vermelhos por stubs.
- Testes executados: pytest completo: 146 verdes e 5 contratos vermelhos por NotImplementedError; ruff limpo; 3 travas íntegras
- Pendências: Implementar núcleo compartilhado; contratos 003 ainda são stubs


## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: a extensão compartilhada (`collect_items`, `pending`, parada limpa, estado atual) de que as quatro stories dependem. **Mudança em código das specs anteriores: o gate é não regredir nada.**

**⚠️ CRITICAL**: nenhuma user story começa antes desta fase terminar.

- [X] T003 ~ `pipelines/collectors/_shared/datasets.py`: extrair `collect_items` de `collect_datasets` conforme `logic/coleta-clima.md` §1 (parâmetros `state_is_current`, `skip_current`, `max_items`; retorno com `skipped_current`, `remaining`, `quota_exhausted`, `interrupted`, `up_to_date`; `StopCollection`/`KeyboardInterrupt` marcam o item corrente e os seguintes como `pending`; `_collect_one` apaga o bruto do item e repropaga; `meta["entry_extra"]` entra no topo da entrada). `collect_datasets` vira invólucro e devolve **só** as quatro chaves de hoje. `StopCollection` e `QuotaExhausted` já existem (criadas pelo plan). → contrato: `test_us2_ac1_ac2_ac4_fr012_fr013_fr015_quota_stop_marks_pending_and_resume_fetches_only_pending` (fecha na Fase 4)
- [X] T004 ~ `pipelines/collectors/_shared/dataset_manifest.py`: `pending` em `DATASET_STATUSES`; `validate_entry` trata `pending` como `failed`; `run_status` conforme D3 do plano. `latest_dataset_states` **não muda** (FR-006, FR-012)
- [X] T005 [P] Testes do núcleo em `tests/unit/test_collect_items.py`: `pending` por `QuotaExhausted` e por `KeyboardInterrupt` simulado (o bruto do item interrompido é apagado e o manifest é gravado); `skip_current` com `state_is_current`; `max_items` e `remaining`; `up_to_date` sem manifest e sem consumir `run_id`; `entry_extra` presente em `changed` e `unchanged`; `pending` nunca vira estado; `collect_datasets` devolve as 4 chaves. Rodar **toda** a suíte e as três travas.

- [X] T006 Linha de base e registro: antes de mexer em `datasets.py`, rodar a suíte completa e as três travas e anotar em Execution Notes (esperado: 140 verdes + os 5 contratos vermelhos por `NotImplementedError`); repetir ao fim da fase para provar que nada regrediu

**Checkpoint**: suíte existente (140) + `test_collect_items.py` verdes; contratos 001 e 002 íntegros.

---

**Registro da Fase**:

- Status: concluída
- Feito: collect_items extraído com pending, limite e parada limpa; invólucro 002 preservado
- Contrato: três travas íntegras (001, 002, 003); contratos futuros permanecem vermelhos por stubs.
- Testes executados: pytest completo: 149 verdes + 5 stubs vermelhos; núcleo: 5/5; ruff limpo; três travas íntegras
- Pendências: Implementar US1; baseline antes da refatoração: 146 verdes e 5 stubs


## Phase 3: User Story 1 - Coletar o clima diário dos 308 municípios com rastreabilidade (Priority: P1) 🎯 MVP

**Objetivo**: um comando coleta o clima de cada município como bruto imutável, com manifest por município, `unchanged` por impressão digital e tolerância a falha.

**Independent Test**: com o fetcher offline e a dimensão sintética, rodar a CLI num destino vazio e conferir os 308 brutos e o manifest; repetir com `--recollect` e conferir `unchanged`; fazer um município falhar e conferir os outros 307.

### Contrato da Fase

- `test_us1_ac1_ac2_fr005_fr006_fr007_each_municipality_is_stored_and_recollecting_is_unchanged` — US1/AC1–2, FR-005/006/007
- `test_us1_ac4_ac5_fr007_fr008_invalid_responses_fail_per_municipality_without_partial_raw_nor_state` — US1/AC4–5, FR-007/008, FR-013
- Comando: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py -k "us1" --basetemp .pytest_tmp`

### Implementation

- [X] T007 [P] [US1] `+ pipelines/collectors/open_meteo/municipalities.py`: `load_climate_municipalities(silver_dir)` lê `dim_municipality/data.parquet` (`dico`, `official_name`, `representative_lat`, `representative_lon`) e devolve `[{"dico","name","latitude","longitude"}]`; `check_municipalities(towns, expected)` recusa total diferente, `dico` repetido e coordenada ausente ou fora de Portugal (lat 29–43, lon −32 a −6) com mensagem que diz qual (FR-004; `data-model.md` §2)
- [X] T008 [P] [US1] `pipelines/collectors/open_meteo/validate.py`: `validate_open_meteo_response(item, path)` com as 9 verificações e mensagens de `logic/coleta-clima.md` §4 (FR-008, FR-009) → contrato: `test_us1_ac4_ac5_…`
- [X] T009 [P] [US1] `pipelines/collectors/open_meteo/fingerprint.py`: `fingerprint_open_meteo_response(path)` conforme `logic/coleta-clima.md` §3 (FR-006) → contrato: `test_us1_ac1_ac2_…`
- [X] T010 [US1] `pipelines/collectors/open_meteo/handler.py`: `collect_open_meteo` conforme `logic/coleta-clima.md` §6 (itens ordenados por `dico`, `is_current`, `entry_extra` com `model`, `requested_*`, `returned_*`, `elevation_m`, `timezone`, `reference_period`, `skip_current=not recollect`, `max_items`) (FR-002, FR-004, FR-005, FR-006, FR-013, FR-022) → contratos: `test_us1_ac1_ac2_…`, `test_us1_ac4_ac5_…`
- [X] T011 [P] [US1] `pipelines/collectors/open_meteo/fetch.py`: `make_open_meteo_fetcher` sem a classificação de cota: monta a requisição (`logic/coleta-clima.md` §5), `User-Agent` e `RateLimiter(limits.min_interval_seconds)` do projeto, timeout 60 s, 3 tentativas com espera crescente em erro de rede e 5xx/408, `DownloadError` em 4xx, `json_content_check` e gravação atômica em `destination` (FR-003)
- [X] T012 [US1] `+ pipelines/cli/collect_open_meteo.py`: `--local`/`--s3`/`--bucket`/`--prefix`/`--root`/`--catalog`/`--silver`, usando `pipelines/cli/_common.py`; carrega a dimensão (T007), monta o fetcher (T011) e chama `collect_open_meteo`; saída e códigos `0`/`1` conforme `contracts/clima-cli.md` (a parte do código `2` e das opções de cota é T018) (FR-010, FR-011)

### Testes da Fase

- [X] T013 [P] [US1] `tests/unit/test_open_meteo_validate.py`: cada uma das 9 verificações com a fixture `open_meteo_response` (dias a menos e a mais, variável ausente, unidade trocada, texto no lugar de número, variável toda nula reprova, nulos esparsos **não** reprovam, `error: true`, JSON de lista, arquivo vazio)
- [X] T014 [P] [US1] `tests/unit/test_open_meteo_fingerprint.py`: `generationtime_ms` diferente → igual; valor ou `elevation` diferente → diferente; ordem das chaves irrelevante
- [X] T015 [US1] `tests/integration/test_open_meteo_cli_local.py`: `collect_open_meteo.main` com fetcher offline, dimensão sintética de 308 municípios e catálogo de janela curta; 308 brutos, manifest, `--recollect` → todos `unchanged`, falha de 1 município → código `1` e 307 gravados, dimensão com 307 municípios → recusa antes de qualquer chamada
- [X] T016 [P] [US1] `tests/integration/test_open_meteo_s3.py` (moto): mesmo cenário no S3 simulado; mesmo conjunto de chaves e manifest equivalente ao local (SC-006)

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py -k "us1" --basetemp .pytest_tmp` → 2/2 verdes e `check-contract-tests.ps1` íntegro (003, 002 e 001); T013 a T016 verdes; `ruff` limpo; a CLI coleta, repete como `unchanged` com `--recollect` e isola a falha de um município.

**Checkpoint**: User Story 1 funcional e testável isoladamente.

**Registro da Fase**:

- Status: concluída
- Feito: Coleta 308 municípios local e S3 simulado; validação e impressão digital implementadas
- Contrato: três travas íntegras (001, 002, 003); contratos futuros permanecem vermelhos por stubs.
- Testes executados: pytest completo: 175 verdes e 2 contratos futuros vermelhos; US1 2/2; ruff limpo; 3 travas íntegras
- Pendências: US2 retomada já verde pelo núcleo; faltam HTTP429 e transformação. S3 teve 2 iterações por filtro do snapshot


---

## Phase 4: User Story 2 - Retomar a coleta respeitando a cota gratuita (Priority: P2)

**Objetivo**: quando a cota se esgota, a execução para limpa, registra os `pending` e a seguinte continua só deles.

**Independent Test**: com um servidor simulado que passa a recusar depois de N municípios, rodar a CLI e conferir N gravados e o resto `pending` (código `2`); rodar de novo e conferir que só os pendentes foram consultados.

### Contrato da Fase

- `test_us2_ac1_ac2_ac4_fr012_fr013_fr015_quota_stop_marks_pending_and_resume_fetches_only_pending` — US2/AC1–2/4, FR-012/013/015
- `test_us2_ac3_fr003_fr012_minute_limit_waits_and_daily_limit_stops_without_waiting` — US2/AC3, FR-003, FR-012
- Comando: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py -k "us2" --basetemp .pytest_tmp`

### Implementation

- [X] T017 [US2] `pipelines/collectors/open_meteo/fetch.py`: classificação do 429 (`classify_limit` por palavra-chave, desconhecido = `hour`), `WAIT_SECONDS`/`MAX_WAITS`, `wait_on_limits`, `QuotaExhausted` sem deixar arquivo (`logic/coleta-clima.md` §5; research R4) (FR-003, FR-012) → contrato: `test_us2_ac3_fr003_fr012_…`
- [X] T018 [US2] `pipelines/cli/collect_open_meteo.py`: opções `--max-municipalities`, `--recollect`, `--no-wait`; código de saída `2` só para pendentes sem falhas (`1` vence); mensagem de continuação; resumo com gravados/inalterados/falhas/pendentes/atuais/restantes; Ctrl+C grava o manifest e sai com `2`; "nada a coletar" sem manifest (`contracts/clima-cli.md`) (FR-011, FR-012, FR-014, FR-015) → contrato: `test_us2_ac1_ac2_ac4_…`

### Testes da Fase

- [X] T019 [P] [US2] `tests/unit/test_open_meteo_fetch.py` (`httpx.MockTransport`): 429 horário espera 3.605 s uma vez e, persistindo, vira `QuotaExhausted`; minuto esgotado após 5 esperas vira `QuotaExhausted`; 429 sem palavra reconhecida = hora; 5xx e timeout têm 3 tentativas e depois `DownloadError`; 400 com `reason` vira `DownloadError` com o texto; corpo HTML reprovado; `destination` nunca fica parcial; a taxa mínima é respeitada (relógio e `sleep` injetados)
- [X] T020 [US2] `tests/integration/test_open_meteo_cli_quota.py`: cota diária após N → código `2`, N gravados, manifest `partial`; segunda execução só pendentes; `--max-municipalities 2` consulta 2 e não cria `pending`; `--no-wait` com 429 de minuto → `pending` e código `2`; `KeyboardInterrupt` do fetcher → manifest gravado e código `2`; falha **e** pendência juntas → código `1`

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py -k "us2" --basetemp .pytest_tmp` → 2/2 verdes e `check-contract-tests.ps1` íntegro; T019 e T020 verdes; suíte completa verde.

**Checkpoint**: User Stories 1 e 2 funcionam; a coleta real é viável em ~3 execuções.

**Registro da Fase**:

- Status: concluída
- Feito: Coleta retomável com limites minuto/hora/dia, Ctrl+C, lotes e códigos 0/1/2
- Contrato: três travas íntegras (001, 002, 003); contratos futuros permanecem vermelhos por stubs.
- Testes executados: pytest completo: 190 verdes e 1 stub US3 vermelho; focados: 18 verdes; ruff e 3 travas íntegros
- Pendências: Transformação e build US3


---

## Phase 5: User Story 3 - Staging diário por município com o código oficial (Priority: P2)

**Objetivo**: transformar o estado vigente em `stg_climate_daily` (formato longo, dia local, ausência preservada, proveniência), testado pelo dbt e promovido por caminho.

**Independent Test**: com brutos de fixture e a Silver sintética, rodar `build_climate` e conferir `dico` na dimensão, chave única, dias por município, faixas físicas e nulos preservados; um bruto adulterado ou um teste dbt reprovado mantém o staging anterior.

### Contrato da Fase

- `test_us3_ac2_ac4_ac5_fr016_fr017_staging_keeps_nulls_local_dates_and_source_units` — US3/AC2/4/5, FR-016/017, Constitution III
- Comando: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py -k "us3" --basetemp .pytest_tmp`

### Implementation

- [X] T021 [US3] ~ `analytics/dbt/dbt_project.yml` (tag `climate` em `models.caop_territory.climate`) e `+ analytics/dbt/models/climate/schema.yml` com os testes de coluna de `data-model.md` §5, reusando `source('caop_silver','dim_municipality')` já declarado em `models/bronze/schema.yml` (não redeclarar) (FR-019)
- [X] T022 [US3] `+ analytics/dbt/models/climate/stg_climate_daily.sql`: lê `climate_daily.parquet` de `CLIMATE_PREPARED_DIR` e materializa em `CLIMATE_BUILD_DIR/lake/bronze/stg_climate_daily/data.parquet` com os tipos fixados (`date`, `double`, `varchar`), no estilo de `stg_observation.sql` (FR-016, FR-021)
- [X] T023 [P] [US3] `+ analytics/dbt/tests/climate_key_unique.sql`, `climate_days_per_municipality.sql`, `climate_value_ranges.sql`, `climate_tmin_le_tmax.sql` (cada um devolve as linhas que violam, como `observations_key_unique.sql`), com as faixas de `data-model.md` §5 (FR-018, FR-019)
- [X] T024 [US3] `pipelines/collectors/open_meteo/transform.py`: `read_climate_response(path)` conforme `logic/coleta-clima.md` §7 (`date.fromisoformat` sem fuso, `NaN` sem `fillna`, unidade literal) (FR-016, FR-017) → contrato: `test_us3_ac2_ac4_ac5_…`
- [X] T025 [US3] `+ pipelines/cli/build_climate.py`: `prepare_climate` (estado atual por município, conferência de `sha256`/tamanho, `ParquetWriter` em fluxo, `climate_meta.parquet`, `not_collected`), `_run_dbt` (`--select tag:climate`; define `CLIMATE_BUILD_DIR`, `CLIMATE_PREPARED_DIR`, `OBS_SILVER_DIR`, `CAOP_DUCKDB_PATH` em área isolada), `promote_paths` dos três caminhos Bronze e `main`; erros e códigos de `contracts/clima-cli.md` (FR-012…FR-017, FR-021). Os relatórios `rpt_*` e `climate_points.parquet` entram na Fase 6.
- [X] T026 [P] [US3] `+ tests/fixtures/climate/__init__.py` e `ci_seed.py`: Silver sintética de 308 municípios com `representative_lat/lon`, coleta dos brutos pelo próprio `collect_open_meteo` com fetcher offline (janela curta 2025-01-01 a 2025-01-31 no catálogo da fixture, opção `--days` para o volume cheio) e `prepare_climate`; `python -m tests.fixtures.climate.ci_seed --root .data/ci-climate`, no padrão de `tests/fixtures/observations/ci_seed.py`

### Testes da Fase

- [X] T027 [P] [US3] `tests/unit/test_open_meteo_transform.py`: série completa → 13 × dias linhas; zero legítimo continua `0` e `null` continua nulo; todas as variáveis nulas num dia; dia 29 de fevereiro e virada de ano; `unit` por `daily_units`
- [X] T028 [US3] `tests/integration/test_climate_build.py`: `build_climate` sobre a fixture (dbt real, janela curta): linhas = 308 × 13 × dias; `dico` na dimensão; staging **parcial** (municípios sem estado atual) é válido; bruto adulterado → falha `checksum ou tamanho alterado` e o staging anterior fica intacto; teste dbt forçado a falhar (umidade 120) → nada promovido; estado de janela antiga não entra; a CAOP e `stg_observation` ficam intactos byte a byte (SC-004, SC-005)

**Critério de Conclusão**: `uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py --basetemp .pytest_tmp` → 5/5 verdes e `check-contract-tests.ps1` íntegro (003, 002, 001); T027 e T028 verdes; `dbt build --select tag:climate` verde sobre a fixture; `dbt build --select tag:caop` e `--select tag:observations` seguem verdes.

**Checkpoint**: User Stories 1 a 3 funcionam; existe staging promovido.

**Registro da Fase**:

- Status: concluída
- Feito: Staging diário em fluxo, checksum e dbt isolado; promoção preserva outros lakes
- Contrato: três travas íntegras (001, 002, 003); 5/5 contratos verdes na suíte completa
- Testes executados: pytest completo 197/197; contratos 5/5; integração build 4/4; dbt climate 14/14; ruff e 3 travas íntegros
- Pendências: Relatórios US4; catálogo explícito das fixtures documentado em R-011


---

## Phase 6: User Story 4 - Relatório de cobertura climática (Priority: P3)

**Objetivo**: dizer por variável quantos municípios têm a série completa, quais têm lacunas, quais não foram coletados e quais têm ponto divergente.

**Independent Test**: com a fixture em que alguns municípios têm dias nulos, outros não foram coletados e um tem o ponto devolvido a 40 km, rodar `build_climate` e conferir as contagens e as listas.

### Implementation

- [X] T029 [P] [US4] `+ pipelines/collectors/open_meteo/points.py`: `haversine_km` (raio 6371,0088 km) e `build_points(states, source)` → `climate_points.parquet` (colunas de `data-model.md` §4, `diverged = distance_km > point_divergence_km`); `prepare_climate` (T025) passa a gravá-lo (FR-020)
- [X] T030 [US4] `+ analytics/dbt/models/climate/rpt_climate_coverage.sql` e `rpt_climate_points.sql` (definições de `logic/coleta-clima.md` §8 e `data-model.md` §5) + testes em `schema.yml` (`variable` único e não nulo; contagens consistentes: completos + com lacuna + não coletados = 308) e `tests/climate_coverage_consistency.sql` (FR-019, FR-020)
- [X] T031 [US4] ~ `pipelines/cli/build_climate.py`: `write_coverage` (`climate_coverage.csv` e `climate_points.csv`, `;` e `utf-8-sig`, ausentes com nome) e `format_coverage` (tabela legível com janela, modelo, divergentes e elevação 0 m), no estilo de `build_observations.py` (FR-020; US4/AC2)
- [X] T032 [P] [US4] ~ `.github/workflows/python.yml`: passos "Prepare climate fixture" e "Build dbt climate from fixture" (`OBS_SILVER_DIR=.data/ci-climate/lake/silver`, `--select tag:climate`), com `hashFiles` como os da spec 002 (SC-007)

### Testes da Fase

- [X] T033 [P] [US4] `tests/unit/test_climate_points.py`: haversine contra valores conhecidos (Lisboa–Porto ≈ 274 km), `diverged` no limite de 25 km, elevação 0 preservada
- [X] T034 [US4] `tests/integration/test_climate_coverage.py`: fixture com 300 completos, 3 com lacuna, 5 não coletados e 1 ponto a 40 km → contagens, listas e CSV conforme US4/AC1; variável sem nenhum dado aparece com cobertura 0; relatório preservado junto da saída (US4/AC1–3)

- [X] T034+1 [US4] Descoberta na revisão de T034: persistir assinatura de variáveis/unidades e comparar configuração antes de deduplicar; modelo novo com JSON idêntico deve virar estado `changed` (decisão explícita do autor, R-012); testes em `test_open_meteo_state.py`.
- [X] T034+2 [US4] Descoberta na revisão de T031: promover os dois CSV e as três tabelas com rollback conjunto; testar destino bloqueado em cada caminho (`test_climate_promotion.py`, R-013).
- [X] T034+3 [US4] Descoberta na revisão de T034: ignorar extras antes da transformação; testar variável extra malformada tolerada pelo validador (R-014).

**Critério de Conclusão**: T033 e T034 verdes; `dbt build --select tag:climate` verde na fixture, local e no CI; `climate_coverage.csv` e `climate_points.csv` legíveis; contratos 5/5 e três travas íntegras.

**Checkpoint**: todas as user stories funcionam.

**Registro da Fase**:

- Status: concluída
- Feito: Relatórios e CSV com rollback conjunto; estado por janela/modelo/variáveis; revisão corrigida
- Contrato: três travas íntegras (001, 002, 003); 5/5 contratos verdes na suíte completa
- Testes executados: uv run --locked python -m pytest -q --basetemp .pytest_tmp: 210/210; contratos 5/5; dbt tag:climate 23/23; ruff limpo; três travas íntegras
- Pendências: Polish, volume, smoke real e CI remoto; regressões da revisão: 32 testes focados verdes


---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: documentação, volume e verificação real.

- [X] T035 [P] Atualizar `.docs/fontes_de_dados.md` (§3.3 `open_meteo`: implementada pela spec 003, `era5`, janela de 24 meses, layout `dataset=<dico>`, cota e retomada, estado "implementada"; §3.4 estrutura; §4 a decisão do modelo; corrigir a linha que dizia "30 anos" e "Lambda"), `docs/runbooks/coletas.md` (coleta em 3 dias, códigos de saída, `--max-municipalities`, `--recollect`, órfãos, dados preliminares) e `README.md` (Quality Gate 6)
- [X] T036 Teste de volume: `python -m tests.fixtures.climate.ci_seed --root .data/ci-full --days 730` e `build_climate --root .data/ci-full`; conferir 2.922.920 linhas, tempo e memória (alvo: sem passar de ~1 GB) e registrar em Execution Notes (R-010)
- [X] T036+1 Descoberta em T036: limitar memória do DuckDB no target exclusivo `climate`, mantendo o target `local` anterior intacto; repetir volume e medir árvore de processos (R-015).
- [X] T037 **Coleta real e medição (manual, SC-008):** seguir `quickstart.md` §4: smoke de 5 municípios, repetir por dia até 308/308, `build_climate`; registrar execuções, chamadas por município, texto real do 429 (emendar a fixture se diferir, R-002), lacunas, pontos divergentes, elevação 0 m e o tamanho do bruto; atualizar `research.md` (R3, R4)
- [X] T038 Rodar a validação de `quickstart.md` (§2 e §3)
- [X] T038+1 Descoberta em T037 e solicitada pelo autor: modo `--continuous` com supervisor, checkpoints a cada 10 municípios e antes da espera por cota, respeito a `Retry-After`/`X-RateLimit-Reset`, backoff exponencial com jitter para falhas temporárias, Ctrl+C e erros permanentes encerrando a execução. Preservar os contratos e o comportamento dos modos existentes.

### Checklist de Release

- [X] Fase 1 (Setup) concluída
- [X] Fase 2 (Foundational) concluída, sem regressão nas specs 001 e 002
- [X] Fase 3 (User Story 1) concluída
- [X] Fase 4 (User Story 2) concluída
- [X] Fase 5 (User Story 3) concluída
- [X] Fase 6 (User Story 4) concluída
- [X] Testes de contrato 5/5 verdes na suíte completa e `check-contract-tests.ps1` íntegro para 001, 002 e 003
- [X] `uv run --locked ruff check pipelines tests` limpo
- [X] `uv run --locked python -m pytest -q --basetemp .pytest_tmp` verde, sem rede
- [X] `dbt build --select tag:caop`, `tag:observations` e `tag:climate` verdes isoladamente
- [X] CI verde, incluindo o passo do dbt do clima e o `gitleaks`
- [X] `config/sources.yml`, `.docs/fontes_de_dados.md`, `docs/runbooks/coletas.md` e `README.md` atualizados (Quality Gate 6)
- [X] Atribuição Open-Meteo/ERA5 e restrição de uso não comercial presentes no catálogo, no manifest e no staging (R-001)
- [X] Nenhum segredo, bruto real ou resposta real no Git; nenhum recurso AWS criado
- [X] Coleta real registrada (T037) ou a pendência declarada
- [X] `quickstart.md` executado com sucesso
---

**Registro da Fase**:

- Status: concluída — coleta e build reais completos; CI remoto registrado somente para afa0903
- Feito: fonte real 308/308, 2.922.920 linhas completas nas 13 variáveis, nenhuma lacuna, 17.821.354 bytes de bruto; CLI confirma 308/308 atuais sem novas consultas. Build final recuperado via uv após o supervisor não encontrar dbt no PATH. Sete arquivos de outras fontes preservados; Sesimbra sinalizada a 30,06 km e três elevações 0 m. T038+1 implementada e verificada no commit 7811147. PR #3 continua em rascunho
- Contrato: três travas íntegras (001, 002, 003); 5/5 contratos verdes na suíte completa
- Testes executados: `uv run --locked python -m pytest -q --basetemp .data/pytest-continuous-final`: 225/225; `uv run --locked ruff check pipelines tests`: limpo; 3 travas íntegras. Build real parcial: 2.078.310 linhas e dbt climate aprovado. Evidência anterior: dbt 31/31 CAOP, 17/17 observations, 23/23 climate; volume 555,90 MiB; CI remoto em afa0903 com 209 passed e 1 skipped específico do Windows; gitleaks sem achados ([run 43107887816](https://github.com/johnosd/living-recommender/actions/runs/43107887816))
- Pendências: nenhuma task de implementação. Conferência final de T037 em 2026-11-12 UTC: build real passou, medição final e preservação de 7 arquivos passaram, 5/5 contratos do clima verdes e trava íntegra. O CI remoto citado não cobre 7811147 nem este fechamento documental; publicação e merge não fazem parte desta prova local


## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sem dependências.
- **Foundational (Fase 2)**: depende de T001–T002; BLOQUEIA todas as stories.
- **US1 (Fase 3)**: depende da Fase 2. **US2 (Fase 4)**: depende de T010/T011/T012 (US1). **US3 (Fase 5)**: depende de T003/T004 e do estado vigente (US1); pode andar em paralelo com a US2 depois da US1. **US4 (Fase 6)**: depende de T025 (US3).
- **Polish (Fase 7)**: depende de todas.

### Parallel Opportunities

- T007, T008, T009 e T011 (arquivos diferentes, sem dependência entre si); T013, T014 e T016 (testes).
- T023 e T026 na Fase 5; T029, T032 e T033 na Fase 6.
- T005 em paralelo com a preparação dos testes da Fase 3.

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Fases 1 e 2 (fundação, sem regredir 001/002).
2. Fase 3 (US1): a coleta rastreável já entrega valor com poucos municípios ou uma cota suficiente.
3. **PARAR E VALIDAR**: contratos `us1` verdes, suíte verde, trava íntegra.

### Incremental Delivery

1. US1 → US2 (retomada: torna os 308 alcançáveis na cota gratuita) → US3 (staging) → US4 (cobertura).
2. A cada fase: contratos, suíte completa, `ruff` e as três travas; nunca editar os arquivos travados.

## Notes

- `[P]` = arquivos diferentes, sem dependência.
- Commits curtos, em inglês (Quality Gate 7), após cada task ou grupo coerente.
- Os 5 contratos e o helper `tests/fixtures/open_meteo/responses.py` são **somente leitura** para o executor.

---

## Rastreabilidade (FR/SC → tasks)

| Requisito | Tasks | Requisito | Tasks |
| --- | --- | --- | --- |
| FR-001 | T001, T002 | SC-001 | T015, T020, T037 |
| FR-002 | T002, T010 | SC-002 | T015, T013 (+ contrato 2) |
| FR-003 | T011, T017, T019 | SC-003 | T020 (+ contrato 3) |
| FR-004 | T007, T010, T015 | SC-004 | T027, T028, T023 |
| FR-005 | T003, T010 | SC-005 | T023, T028, T036 |
| FR-006 | T003, T004, T009, T010 | SC-006 | T016 |
| FR-007 | T003, T009, T010 | SC-007 | T032, T038 |
| FR-008 | T008, T013 | SC-008 | T037 |
| FR-009 | T008, T013 | FR-017 | T024, T027 |
| FR-010 | T012, T016 | FR-018 | T023, T024 |
| FR-011 | T012, T018 | FR-019 | T021, T023, T028, T030 |
| FR-012 | T003, T004, T017, T018, T020 | FR-020 | T029, T030, T031, T034 |
| FR-013 | T003, T010, T018 | FR-021 | T022, T025 |
| FR-014 | T018, T020 | FR-022 | T001, T010, T025 |
| FR-015 | T018, T025, T029 | FR-023 | todas as fases (testes sem rede) |
| FR-016 | T022, T024, T025 | | |

## Phase 8: Convergence

Auditoria de 2026-11-12 UTC sobre `3844685`, após T037/T038+1. Código-fonte e fases anteriores preservados. Contratos do clima íntegros e verdes; 21 testes focados (contratos, estado, retry, S3 simulado e cobertura) passaram, assim como ruff. Fonte real conferida: 308 estados atuais, 308 checksums, 17.821.354 bytes e 2.922.920 linhas; fonte/modelo/licença/atribuição/restrição consistentes. Sesimbra e as elevações 0 m são alertas previstos, não achados novos. O CI remoto permanece em `afa0903` no PR #3.

- [X] T039 [HIGH] **CF-001 — Coerência do catálogo durante execução contínua** (origem: FR-006, FR-013; plan: D4/D6 e adendo operacional). Em `pipelines/cli/collect_open_meteo.py:59–68`, cada lote relê o catálogo, mas o fetcher fica vinculado à configuração do primeiro lote (`pipelines/collectors/open_meteo/fetch.py:65–70`), enquanto o handler registra a configuração nova (`handler.py:43`). Reprodução sem rede com o cliente HTTP real sobre MockTransport: troca de modelo entre lotes, 21 requisições com `models=era5`, estados finais com `model=another_model` e saída 0. Corrigir a coerência entre configuração usada na requisição, validação, assinatura e manifest: adotar um snapshot consistente por sessão ou atualizar o fetcher de forma coordenada, preservando o limitador entre lotes. Cobrir troca de modelo/janela/variáveis entre checkpoints e garantir que nunca haja sucesso com proveniência divergente; manter os contratos travados intactos. A auditoria não encontrou divergência nos dados reais já coletados.
- [ ] T040 [HIGH] **CF-002 — CI da versão corrigida** (origem: SC-007; Constitution Quality Gate 1; Checklist de Release). O head remoto do PR #3 é `afa0903f24d5c289071ce449fc04a6e22cd843ea`, com run verde `43107887816`; o código de `7811147` e o fechamento local `3844685` ainda não estão cobertos. Após T039, validar no CI o commit que contém a correção, com pytest/ruff, dbt CAOP/observations/climate e secrets/gitleaks do PR; registrar SHA, run e resultados. Não usar o run anterior como prova do código posterior nem confundir essa validação com merge ou deploy.
- [ ] T041 [MEDIUM] **CF-003 — Consolidação da medição real de cota** (origem: SC-008; T037; research R3/R4). A pesquisa registra os lotes e `X-RateLimit-Cost: 67.78571`, mas falta um fechamento com o número de execuções e o consumo total. A auditoria contou 17 manifests, 308 entradas changed, 3 unchanged e 816 pending; pending não corresponde a chamada HTTP. Consolidar execuções, consultas bem-sucedidas, recoletas, sondagens e retentativas a partir dos manifests/logs existentes, separando chamadas HTTP de unidades ponderadas e valores medidos de estimativas. Parte inicial não foi instrumentada: declarar limites e totais não recuperáveis, sem inventar contagem exata; se o total exigido por SC-008 não puder ser demonstrado, alinhar explicitamente o critério com o autor. Registrar também que os limites horários foram observados e o diário não. Não consumir nova cota apenas para reconstruir uma medição histórica.

**Registro da Fase**:

- Status: em execução — T039 concluída; T040/T041 pendentes.
- Feito: snapshot independente do catálogo por invocação, compartilhado por todos os lotes e pelo fetcher/limitador; configuração alterada entra na próxima sessão. Modelo, janela e variáveis cobertos por regressões com HTTPX MockTransport e armazenamento em memória, incluindo parâmetros HTTP, manifests, assinaturas e preservação dos brutos antigos. Reconciliação histórica pronta em research.md, com valores medidos, estimativas e limites separados.
- Contrato: 5/5 contratos do clima verdes; três travas íntegras, sem emenda de teste travado.
- Testes executados: regressões novas primeiro vermelhas (3/3), depois verdes (3/3); regressões + contratos: 8/8. `uv run --locked python -m pytest -q --basetemp .data/pytest-convergence-execute-final`: 228/228 em 258,55 s. `uv run --locked ruff check pipelines tests`: limpo. Revisão independente: sem achados críticos/importantes.
- Pendências: T040 aguarda publicação do commit corrigido e CI remoto; T041 aguarda decisão explícita do autor sobre a proposta de SC-008, pois o total histórico exato não é recuperável. Nenhuma nova chamada real feita para esta fase.
