---
description: "Lista de tasks da spec 011 — marts de indicadores e criteria_catalog"
---

# Tasks: Marts de indicadores e criteria_catalog versionado

**Input**: Documentos de design de `.sdd/specs/011-marts-indicadores-catalogo/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/criteria-catalog.md, logic/*.md

**Organization**: Tasks agrupadas por user story pra permitir implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta task pertence (ex: US1, US2)
- Incluir caminhos de arquivo exatos nas descrições

## Path Conventions

- Lógica em funções puras: `pipelines/gold/<módulo>.py` (DataFrame entra, DataFrame sai, sem I/O).
- Leitura do lake e escrita do candidato: `pipelines/gold/prepare.py`. Orquestração, dbt e promoção:
  `pipelines/cli/build_gold.py` (modelo: `pipelines/cli/build_mobility.py`).
- Modelos dbt: `analytics/dbt/models/gold/*.sql` + `analytics/dbt/models/gold/schema.yml`; testes singulares
  em `analytics/dbt/tests/gold_*.sql`; tag `gold` em `analytics/dbt/dbt_project.yml`.
- Catálogo: `config/criteria.yml`.
- Testes: `tests/unit/test_gold_*.py`, `tests/integration/test_gold_build.py`; fixture offline
  `tests/fixtures/gold/ci_seed.py`; contrato TRAVADO `tests/contracts/test_gold_indicators_contract.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Estrutura do build Gold, camada `gold` na documentação do modelo e um lake mínimo de teste.

- [X] T001 Adicionar `gold: +tags: ['gold']` em `analytics/dbt/dbt_project.yml` e criar `analytics/dbt/models/gold/` com um `schema.yml` contendo a fonte `caop_silver` (`dim_municipality`, `dim_parish`, `external_location` via `GOLD_SILVER_DIR`, como em `models/mobility/schema.yml`)
- [X] T002 [P] Reconhecer a camada `gold` no `modeldocs`: `LAYERS` e `create schema gold` em `pipelines/modeldocs/catalog.py`, `LAYER_PATTERN` em `pipelines/modeldocs/model.py`, `LAYERS` em `pipelines/modeldocs/render.py` e em `pipelines/modeldocs/site.py`, sem mudar a saída para bronze/silver (o contrato travado da 010 tem de continuar verde)
- [X] T003 [P] Criar `tests/fixtures/gold/ci_seed.py` (`seed(root) -> dict` e `python -m tests.fixtures.gold.ci_seed --root <dir>`). Ele grava um lake mínimo offline com `dim_municipality` (4 municípios, 1 deles na Madeira), `dim_parish`, `stg_observation`, `stg_climate_daily` (1 mês), `stg_municipality_pole_distance`, `dim_mobility_pole`, `idealista_listings` e `census_parish_observation`, e também um `criteria.yml` pequeno, válido e com um critério de cada `kind`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Códigos fechados, o catálogo real e a sua validação; tudo o que as stories usam.

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase terminar.

- [X] T004 Criar `pipelines/gold/common.py` com os códigos fechados de `data-model.md` (`status`, `value_status`, `origin`, `sample_status`, `rent_coverage`, tipologias, `missing_reason`), a normalização de espaços dos filtros (NBSP, R-008) e a lista de colunas da linha de indicador
- [X] T005 Escrever `config/criteria.yml` com o catálogo inicial de `contracts/criteria-catalog.md` §3: 12 categorias e todos os critérios, rótulos PT/EN e `methodology_pt` (fórmula, tabela Pordata/INE, regra do `-`, adaptação do clima, FR-017). `distancia_sede_distrito_km` entra como `fonte_pendente`
- [X] T006 Implementar `load_criteria` em `pipelines/gold/criteria.py`, com todas as validações de `contracts/criteria-catalog.md` §1.1 e o id citado entre aspas na mensagem; a função `_validate(criteria)` é compartilhada com `catalog_tables`

### Testes da Fase

- [X] T007 [P] `tests/unit/test_gold_criteria.py`: `config/criteria.yml` carrega sem erro; cada regra do §1.1 tem um caso que levanta `CriteriaError`; os pesos `> 0` de cada categoria somam 1

**Critério de Conclusão**: `uv run python -m pytest tests/unit/test_gold_criteria.py -q` verde; o contrato travado da 010 (`tests/contracts/test_modeldocs_contract.py`) continua verde depois do T002.

**Checkpoint**: Fundação pronta - user stories podem começar.

**Registro da Fase** (Setup + Foundational):

- Status: concluída (2026-11-24).
- Feito: tag `gold` no `dbt_project.yml`; camada `gold` no `modeldocs` (aparece no resumo só quando há tabela gold, então o
  documento atual não muda); `pipelines/gold/common.py`; `config/criteria.yml` com 60 critérios em 12 categorias
  (`distancia_sede_distrito_km` pendente); `load_criteria` + `_validate`; fixture `tests/fixtures/gold/ci_seed.py`.
  Desvio do T001: a fonte `caop_silver` não foi redeclarada (o dbt recusa a mesma fonte em dois arquivos); a Gold
  reusa a de `models/bronze/schema.yml`, lida por `OBS_SILVER_DIR` (R-012).
- Contrato: sem contrato nesta fase.
- Testes executados: `uv run python -m pytest tests/unit/test_gold_criteria.py tests/contracts/test_modeldocs_contract.py tests/unit -k "gold_criteria or modeldocs" -q --basetemp .pytest_tmp` → 84 passed (contrato travado da 010 verde).
- Pendências: nenhuma.

---

## Phase 3: User Story 1 - Perfil municipal de indicadores e catálogo de critérios (Priority: P1) 🎯 MVP

**Objetivo**: Indicadores municipais de todas as categorias, aluguel e clima no lake Gold, com o catálogo versionado e os parâmetros de normalização.

**Independent Test**: `build_gold` sobre o fixture e sobre o lake real; todo critério disponível tem 308 linhas, todo valor tem fonte, período e licença, e o catálogo tem P5/P95 para cada critério disponível.

### Contrato da Fase

- `test_us1_ac1_ac4_fr001_fr003_fr004_fr005_latest_period_per_municipality_same_year_population_and_dash_rule` — US1-AC1/AC4, FR-001, FR-003–FR-005
- `test_us1_ac2_ac3_fr020_fr021_fr022_fr024_catalog_fails_on_available_without_data_and_versions_every_change` — US1-AC2/AC3, FR-020–FR-022, FR-024
- `test_us1_ac6_fr015_fr016_fr018_tci_bands_and_extreme_days_follow_the_legacy_rules` — US1-AC6, FR-015, FR-016, FR-018
- `test_us1_fr009_fr010_fr011_fr012_rent_marks_iqr_outliers_without_deleting_and_needs_ten_listings` — FR-009–FR-012
- `test_us1_ac5_fr007_fr008_mobility_uses_ok_pairs_only_and_carries_google_attribution` — US1-AC5, FR-007, FR-008
- Comando: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp`

### Implementation

- [X] T008 [P] [US1] Implementar `municipal_indicators` em `pipelines/gold/observations.py`, conforme `logic/indicadores.md` §1 (período por município, `-` → 0 só com `dash_is_zero`, `per_population`, `share`, `presence`, motivo de ausência) → contrato: `test_us1_ac1_ac4_..._dash_rule`
- [X] T009 [P] [US1] Implementar `rent_indicators(stats, municipalities, criteria)` em `pipelines/gold/rent.py`, que transforma `rent_stats` nas linhas de `custo_aluguel_mediana` e `custo_aluguel_m2` (`logic/aluguel.md` §5)
- [X] T010 [P] [US1] Implementar `rent_stats` em `pipelines/gold/rent.py`, conforme `logic/aluguel.md` §1–§3 (IQR por município × tipologia, n ≥ 10, €/m² com área 10–1 000, `rent_coverage`) → contrato: `test_us1_fr009_..._needs_ten_listings`
- [X] T011 [US1] Implementar `catalog_tables` em `pipelines/gold/criteria.py`: validação, falha de critério disponível sem dado, normalização linear e `catalog_version` por hash (`contracts/criteria-catalog.md` §2) → contrato: `test_us1_ac2_ac3_..._versions_every_change`
- [X] T012 [P] [US1] Implementar `mobility_indicators` em `pipelines/gold/mobility.py`, conforme `logic/indicadores.md` §2 (polo fixo, mais próximo, `par_falha`, atribuição do par escolhido) → contrato: `test_us1_ac5_..._google_attribution`
- [X] T013 [P] [US1] Implementar `climate_monthly` em `pipelines/gold/climate.py`, conforme `logic/clima.md` §2–§3 (pivot das 10 variáveis, extremos, TCI e componentes, mínimo de 20 dias) → contrato: `test_us1_ac6_..._legacy_rules`
- [X] T014 [US1] Implementar `climate_indicators` em `pipelines/gold/climate.py`, conforme `logic/clima.md` §4 (métricas anuais, período `início/fim`, proveniência do Open-Meteo)
- [X] T015 [US1] Criar `pipelines/gold/prepare.py` com `prepare_gold(root, output_dir, *, criteria_path, processed_at_utc) -> dict`. Ele lê as tabelas de entrada do lake (falhando com o nome da que faltar, R-010), chama T008–T014, junta o perfil municipal, chama `catalog_tables` e grava em `output_dir` `municipality_indicator.parquet`, `rent_municipality.parquet`, `climate_monthly.parquet`, `criteria_catalog.parquet` e `criteria_normalization.parquet`, com `catalog_version` e `processed_at_utc` em todas as linhas
- [X] T016 [US1] Criar em `analytics/dbt/models/gold/` os modelos `gold_municipality_indicator.sql`, `gold_rent_by_municipality_typology.sql`, `gold_municipality_climate_monthly.sql`, `gold_criteria_catalog.sql` e `gold_criteria_normalization.sql`. Todos são `external` em `GOLD_BUILD_DIR/lake/gold/<modelo>/data.parquet`, com `cast` de cada coluna lida de `GOLD_PREPARED_DIR`. O `schema.yml` declara todas as colunas (descrição, `data_type`, `meta.source_ids`), `not_null`, `accepted_values` nos códigos e `relationships` com `dim_municipality` (FR-031, FR-033)
- [X] T017 [US1] Criar os testes singulares `analytics/dbt/tests/gold_key_unique.sql` (grão de cada tabela), `gold_municipality_coverage.sql` (308 por critério × variante), `gold_available_criteria_have_values.sql`, `gold_absence_has_reason.sql`, `gold_rent_min_sample.sql` (nada com n < 10), `gold_value_ranges.sql` (aluguel 100–10 000, percentuais 0–100, TCI 0–100) e `gold_google_attribution.sql`
- [X] T018 [US1] Criar `pipelines/cli/build_gold.py` (`build_gold(root, *, criteria_path=None) -> dict`, `GoldBuildError` e `main` com `--local`, `--root` e `--criteria`). Ele monta o candidato em `.data/.build/gold/<uuid>`, chama `prepare_gold`, roda `dbt build --select tag:gold` com `GOLD_BUILD_DIR`, `GOLD_PREPARED_DIR`, `GOLD_SILVER_DIR` e `CAOP_DUCKDB_PATH`, promove só as `lake/gold/<tabela>` (`_promote.promote_paths`) e imprime o resumo (disponíveis, pendentes, versão, caminho)
- [X] T019 [US1] Acrescentar em `.github/workflows/python.yml` os passos "Prepare Gold fixture" (`python -m tests.fixtures.gold.ci_seed --root .data/ci-gold`) e "Build Gold offline with dbt" (`python -m pipelines.cli.build_gold --local --root .data/ci-gold --criteria .data/ci-gold/criteria.yml`)

### Testes da Fase

- [X] T020 [P] [US1] `tests/unit/test_gold_observations.py`: `presence` (ensino superior com `-`), `share` no mesmo dataset, filtro com NBSP casando com o rótulo normalizado, critério `fonte_pendente` ignorado, `source_symbol` com `r`/`Pro`
- [X] T021 [P] [US1] `tests/unit/test_gold_climate.py`: `climate_indicators` (verão JJA, inverno DJF, precipitação anualizada, `tci_anual` = média dos meses, mês com < 20 dias sem TCI, município sem dados → `sem_dados_clima`)
- [X] T022 [P] [US1] `tests/unit/test_gold_catalog.py`: distribuição degenerada (`is_degenerate`), critério de peso 0 só de faixa, opções categóricas no catálogo como JSON, `reference_periods` e licenças distintas
- [X] T023 [US1] `tests/integration/test_gold_build.py`, sobre `tests/fixtures/gold/ci_seed.py`:
  - o build completo com dbt gera as 5 tabelas da US1;
  - um segundo build dá o mesmo conteúdo (sem `processed_at_utc`);
  - um dbt que falha (monkeypatch de `_run_dbt`) preserva `lake/gold/` e remove o candidato;
  - um critério disponível sem dado falha com o id na mensagem e não promove nada;
  - uma entrada ausente falha com o nome da tabela.

**Critério de Conclusão**: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes, e `check-contract-tests.ps1 -Slug 011-marts-indicadores-catalogo` íntegro. Os testes T020–T023 também passam. O `build_gold` sobre o lake real termina sem erro, com 308 linhas por critério disponível × variante.

**Checkpoint**: User Story 1 funcional e testável isoladamente.

**Registro da Fase**:

- Status: concluída (2026-11-24).
- Feito: `observations.py`, `rent.py` (`rent_stats`, `rent_indicators`; `parish_rent_stats` já escrito, marcado na
  US3), `mobility.py`, `climate.py`, `criteria.catalog_tables`, `prepare.py`, os 5 modelos `gold_*` + `schema.yml`,
  7 testes singulares, `pipelines/cli/build_gold.py` e os passos do CI. Build real: catálogo `c528890b92fa`,
  59 disponíveis + 1 pendente, 19 712 linhas no perfil (64 critério × variante × 308).
- Contrato: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes, trava íntegra (`check-contract-tests.ps1`).
- Testes executados: contrato + `tests/unit/test_gold_{criteria,observations,climate,catalog}.py` + `tests/integration/test_gold_build.py` → 48 passed; `uv run ruff check pipelines tests` limpo; fixture (`ci_seed` + `build_gold --criteria .data/ci-gold/criteria.yml`) e build real `build_gold --local --root .data` verdes com dbt. Uma iteração no contrato do clima: o vento usa limite estrito (`W < 15`), e a precipitação usa `<=`.
- Pendências: nenhuma.

---

## Phase 4: User Story 2 - Qualidade e cobertura dos indicadores (Priority: P2)

**Objetivo**: `gold_data_quality` com cobertura, período, zeros por convenção, `stale`, outliers e pendências por critério × nível × variante.

**Independent Test**: com a US1 pronta, o mart lista todos os critérios do catálogo, e as contagens batem com o perfil.

### Implementation

- [X] T024 [US2] Criar `pipelines/gold/quality.py` com `data_quality(catalog, indicators_by_level, rent_by_level) -> DataFrame`, nas colunas de `data-model.md` (`gold_data_quality`). Os pendentes saem com cobertura 0 e `pending_reason`
- [X] T025 [US2] Chamar `data_quality` em `pipelines/gold/prepare.py` (grava `data_quality.parquet`) e criar `analytics/dbt/models/gold/gold_data_quality.sql`, com as colunas declaradas em `schema.yml` e `accepted_values` em `status`/`level`
- [X] T026 [US2] Criar o teste singular `analytics/dbt/tests/gold_quality_consistency.sql`: `with_value + missing = territories_expected`, uma linha por critério do catálogo × nível declarado, e contagens iguais às de `gold_municipality_indicator`
- [X] T027 [US2] Imprimir no `build_gold` a cobertura por categoria e a lista de critérios pendentes, a partir de `gold_data_quality`

### Testes da Fase

- [X] T028 [P] [US2] `tests/unit/test_gold_quality.py`: pendente com cobertura 0 e motivo; `older_period`, `zero_by_convention`, `stale` e `outliers` contados a partir de linhas sintéticas
- [X] T029 [US2] Estender `tests/integration/test_gold_build.py`: `gold_data_quality` existe e as contagens batem com `gold_municipality_indicator` (SC-008)

**Critério de Conclusão**: T028 e T029 verdes; o build real mostra `distancia_sede_distrito_km` como pendente e a cobertura de `emprego_desemprego_100` (278/308); o contrato continua 5/5.

**Checkpoint**: User Stories 1 e 2 funcionam de forma independente.

**Registro da Fase**:

- Status: concluída (2026-11-24).
- Feito: `pipelines/gold/quality.py` (`data_quality`), `gold_data_quality` (modelo, colunas no `schema.yml`, teste
  singular `gold_quality_consistency.sql`), `build_gold` imprime a cobertura por categoria × nível e os pendentes a
  partir do mart. Build real: 65 linhas de qualidade; `emprego_desemprego_100` 278/308; `distancia_sede_distrito_km`
  pendente; `educacao_ensino_superior` com 245 zeros por convenção.
- Contrato: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes, trava íntegra.
- Testes executados: `uv run python -m pytest tests/unit/test_gold_quality.py tests/integration/test_gold_build.py tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp` → 13 passed; build real `build_gold --local --root .data` verde.
- Pendências: nenhuma.

---

## Phase 5: User Story 3 - Indicadores por freguesia com origem sinalizada (Priority: P3)

**Objetivo**: `gold_parish_indicator` e `gold_rent_by_parish_typology`, com origem `proprio`/`herdado`/`ausente`; normalização e qualidade no nível freguesia.

**Independent Test**: todas as 3 259 freguesias aparecem; cada herdado é igual ao município; a população dos Censos é `proprio` com `territorial_inheritance` preservado.

### Implementation

- [X] T030 [P] [US3] Implementar `parish_rent_stats` em `pipelines/gold/rent.py`, conforme `logic/aluguel.md` §4 (grupo `dicofre` × tipologia, marca de outlier do grupo municipal)
- [X] T031 [US3] Criar `pipelines/gold/parish.py` com `parish_indicators(parishes, census, municipal_indicators, parish_rent, criteria) -> DataFrame`, conforme `data-model.md` (`gold_parish_indicator`): `compute_parish` `census` (`residentes`, `pct_25_39`, `pct_65_mais`, `densidade` = população ÷ `area_km2`) e `rent`; os demais critérios ficam herdados (cópia exata) ou ausentes
- [X] T032 [US3] Ligar a freguesia em `pipelines/gold/prepare.py`: grava `parish_indicator.parquet` e `rent_parish.parquet`, passa `{"municipio", "freguesia"}` a `catalog_tables` (normaliza só `proprio`) e a `data_quality`
- [X] T033 [US3] Criar `analytics/dbt/models/gold/gold_parish_indicator.sql` e `gold_rent_by_parish_typology.sql`, com as colunas no `schema.yml`, `relationships` com `dim_parish` e `dim_municipality` e `accepted_values` em `origin`; e o teste singular `analytics/dbt/tests/gold_parish_inherited_equals_municipality.sql` (SC-007), mais a cobertura de 3 259 freguesias por critério × variante

### Testes da Fase

- [X] T034 [P] [US3] `tests/unit/test_gold_parish.py`:
  - freguesia com Censos `inherited` continua `proprio`, com `territorial_inheritance = inherited`;
  - aluguel próprio com n ≥ 10, herdado com n < 10, e ausente quando o município também não tem;
  - clima e mobilidade sempre herdados;
  - a normalização da freguesia ignora os herdados.
- [X] T035 [US3] Estender `tests/integration/test_gold_build.py`: as duas tabelas de freguesia existem, e todas as freguesias do fixture aparecem

**Critério de Conclusão**: T034 e T035 verdes; o build real tem 3 259 freguesias × critério × variante, com zero divergência entre herdado e município; o contrato continua 5/5.

**Checkpoint**: Todas as user stories funcionam de forma independente.

**Registro da Fase**:

- Status: concluída (2026-11-24).
- Feito: `parish_rent_stats` (marca de outlier do grupo municipal), `pipelines/gold/parish.py` (`parish_indicators`:
  Censos e aluguel próprios, demais herdados como cópia exata ou ausentes), freguesia ligada no `prepare`
  (normalização e qualidade no nível `freguesia`), modelos `gold_parish_indicator` e `gold_rent_by_parish_typology`
  com colunas no `schema.yml`, teste singular `gold_parish_inherited_equals_municipality.sql` (SC-007, cobertura de
  todas as freguesias, n ≥ 10) e as duas tabelas no `gold_key_unique.sql`. Build real: catálogo `d738fdca5257`,
  208 576 linhas de freguesia (3 259 × 64), 135 freguesias com aluguel próprio (ALL), população própria nas 3 259.
  Proveniência dos Censos: `source_id = censos`, `dataset_id = census_parish_observation` (R-013).
- Contrato: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes, trava íntegra.
- Testes executados: `uv run python -m pytest tests/unit/test_gold_parish.py tests/integration/test_gold_build.py tests/contracts/test_gold_indicators_contract.py tests/unit/test_gold_quality.py -q --basetemp .pytest_tmp` → 19 passed; build real verde; quickstart §3 sem divergência (SC-002 0 linhas, SC-006 0, SC-007 0, SC-008 true, carro só com "Tempos de viagem: Google").
- Pendências: A1 do Analyze segue como implementado no plano (mediana `ALL` própria na freguesia com n ≥ 10); confirmar com o autor.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Build real, documentação, memória e backlog.

- [X] T036 Rodar `uv run python -m pipelines.cli.build_gold --local --root .data` e as consultas do `quickstart.md` §3. Registrar no `plan.md` (Execution Notes) os números reais: critérios disponíveis/pendentes, `catalog_version`, coberturas e municípios com aluguel próprio
- [X] T037 [P] Regenerar `.docs/modelo_de_dados.md` (`uv run python -m pipelines.cli.model_docs`) e o catálogo do lake (`uv run python -m pipelines.cli.lake_catalog`), e conferir as 9 tabelas Gold com as colunas descritas (FR-033)
- [X] T038 [P] Acrescentar a seção "Build Gold (indicadores e catálogo)" em `.docs/runbooks/coletas.md`: comando, entradas exigidas, como mudar um critério e o que significa um `fonte_pendente`
- [X] T039 [P] Atualizar `README.md`, se ele listar comandos ou camadas do lake, com `build_gold` e `lake/gold/`
- [X] T040 [P] Registrar em `.planning/memory/` (`marts-gold-011-execucao.md`) os achados duráveis do execute
- [X] T041 Atualizar `.planning/backlog.md` → `## Ideias Futuras`: sede de distrito (R-002) e revisão dos pesos e faixas antes da Fase 4 (R-003)
- [X] T042 Executar `quickstart.md` por inteiro
- [X] T043 (ad hoc, descoberta no gate da suíte completa do T042) Atualizar os testes unitários da spec 010 que fotografam o projeto real: `tests/unit/test_modeldocs_model.py` passa a esperar as camadas `{bronze, silver, gold}`, e `tests/unit/test_modeldocs_principal_described.py` compara a lista fixa só com as principais de bronze e silver, mantendo a decisão da 010 de não cobrar modelos novos (R-014)

**Registro da Fase** (Polish):

- Status: concluída (2026-11-24).
- Feito:
  - T036: build real com catálogo `d738fdca5257` e quickstart §3 sem divergência.
  - T037: `.docs/modelo_de_dados.md` regenerado; o catálogo DuckDB tem as 8 tabelas no schema `gold`, todas `ok` e
    com todas as colunas descritas. São 8 tabelas Gold, não 9: o `data-model.md` lista 8.
  - T038: runbook.
  - T039: README.
  - T040: memória `marts-gold-011-execucao.md`.
  - T041: backlog (R-002, R-003 e A1).
  - T042: quickstart completo; no §4, a versão muda e volta, e o dataset inválido falha sem tocar em `lake/gold`.
  - T043: ajuste ad hoc dos testes da 010 (R-014).
- Contrato: 5/5 verdes na suíte completa; trava da 011 e as 11 travas do repositório íntegras.
- Testes executados:
  - `uv run python -m pytest -q --basetemp .pytest_tmp`: a primeira execução deu 834 passed e 2 failed (testes da
    010, corrigidos no T043); a segunda deu 836 passed.
  - `uv run ruff check pipelines tests`: limpo.
  - `uv run python -m pipelines.cli.model_docs --check`: verde.
  - O fixture e o build real com dbt também ficaram verdes.
- Pendências: A1 (mediana `ALL` própria na freguesia) a confirmar com o autor; R-002 e R-003 no backlog.

### Checklist de Release

- [X] Fase 2 (Foundational) concluída
- [X] Fase 3 (User Story 1) concluída
- [X] Fase 4 (User Story 2) concluída
- [X] Fase 5 (User Story 3) concluída
- [X] Testes de contrato todos verdes na suíte completa e `check-contract-tests.ps1 -Slug 011-marts-indicadores-catalogo` íntegro
- [X] Contratos travados de outras features verdes (em especial `test_modeldocs_contract.py`, que o T002 toca)
- [X] `uv run ruff check pipelines tests` limpo
- [X] `uv run python -m pytest -q --basetemp .pytest_tmp` verde
- [X] `uv run python -m pipelines.cli.model_docs --check` verde
- [X] Build Gold do fixture verde (passo do CI) e build real sem erro
- [X] Nenhuma linha por anúncio em `lake/gold/`; carro com "Tempos de viagem: Google" (constitution III, IV e VI)
- [X] `quickstart.md` executado com sucesso

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA todas as user stories
- **US1 (Phase 3)**: depende do Foundational. T015 depende de T008–T014; T016/T017 dependem de T015; T018 depende de T016; T019 depende de T018 e T003
- **US2 (Phase 4)**: depende da US1 (lê o perfil e o catálogo)
- **US3 (Phase 5)**: depende da US1 (herda do perfil municipal); independe da US2, mas T032 chama `data_quality` se ela já existir
- **Polish (fase final)**: depende das stories desejadas

### Parallel Opportunities

- T002 e T003 em paralelo com T001
- Na US1: T008, T010, T012 e T013 (módulos diferentes) em paralelo; T009 depois de T010; T014 depois de T013
- Testes T020–T022 em paralelo

---

## Parallel Example: User Story 1

```bash
Task: "T008 [P] [US1] municipal_indicators em pipelines/gold/observations.py"
Task: "T010 [P] [US1] rent_stats em pipelines/gold/rent.py"
Task: "T012 [P] [US1] mobility_indicators em pipelines/gold/mobility.py"
Task: "T013 [P] [US1] climate_monthly em pipelines/gold/climate.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (bloqueia todas as stories)
3. Completar Fase 3: User Story 1
4. **PARAR E VALIDAR**: contrato 5/5 e build real

### Incremental Delivery

1. Setup + Foundational → fundação pronta
2. User Story 1 → testar isoladamente → considerar entrega (MVP; base do "v0 sem Idealista")
3. US2 (qualidade) → US3 (freguesia), sempre sem quebrar as anteriores

## Notes

- `[P]` = arquivos diferentes, sem dependência
- `[Story]` mapeia a task pra uma user story específica
- Commitar após cada task ou grupo lógico coerente (mensagens curtas em inglês, constitution)
- Parar em qualquer checkpoint pra validar a story isoladamente

<!-- sdd-converge anexa "## Phase N: Convergence" abaixo desta linha -->

## Phase 7: Convergence

**Purpose**: Fechar as lacunas achadas pelo `sdd-converge` de 2026-11-24 (só LOW; nenhum CRITICAL ou HIGH).

- [X] T044 [US1] Acrescentar as métricas anuais `temp_max_anual` (média de `temperature_2m_max` nos dias válidos da janela) e `temp_min_anual` (média de `temperature_2m_min`) a `pipelines/gold/climate.py` (`CLIMATE_METRICS` em `pipelines/gold/criteria.py` e `logic/clima.md` §4), com os critérios `clima_temp_max_anual` e `clima_temp_min_anual` (peso 0, modo `faixa`) em `config/criteria.yml` e um caso em `tests/unit/test_gold_climate.py` (origem: FR-014)
- [X] T045 [US3] Estender `analytics/dbt/tests/gold_value_ranges.sql` às tabelas de freguesia: `rent_median` de `gold_rent_by_parish_typology` entre 100 e 10 000, e percentuais e `clima_tci_anual` de `gold_parish_indicator` entre 0 e 100 (origem: FR-031)
- [X] T046 Rodar de novo o build do fixture e o build real, `model_docs --check` (regenerar `.docs/modelo_de_dados.md` se mudar) e a suíte completa; registrar a nova `catalog_version` no `plan.md`

**Fora desta fase**: FR-007 segue parcial por decisão (a sede de distrito depende de recoleta, fora do escopo; R-002, já no backlog).

**Registro da Fase**:

- Status: concluída (2026-11-24).
- Feito:
  - T044: `clima_temp_max_anual` e `clima_temp_min_anual` (peso 0, FR-014), com teste unitário.
  - T045: `gold_value_ranges.sql` cobre também `gold_rent_by_parish_typology` e `gold_parish_indicator` (FR-031).
  - T046: build real com catálogo `160da2ce8218`: 61 disponíveis e 1 pendente; 20 328 linhas municipais e 215 094 de freguesia.
- Contrato: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes na suíte completa, trava íntegra.
- Testes executados:
  - `uv run python -m pytest -q --basetemp .pytest_tmp`: 836 passed.
  - `uv run ruff check pipelines tests`: limpo.
  - `uv run python -m pipelines.cli.model_docs --check`: verde.
  - Os builds do fixture e real passaram com o dbt.
  - As consultas do quickstart §3 não tiveram divergência.
- Pendências: nenhuma; FR-007 (sede de distrito) segue fora do escopo (R-002, backlog).
