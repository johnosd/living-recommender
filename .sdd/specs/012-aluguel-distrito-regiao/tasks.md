# Tasks: Aluguel por distrito e por região na Gold, com herança marcada

**Input**: Documentos de design de `.sdd/specs/012-aluguel-distrito-regiao/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, logic/heranca.md

**Organization**: Tasks agrupadas por user story pra permitir implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta task pertence (ex: US1, US2)

## Path Conventions

- Regras em `pipelines/gold/`; orquestração em `pipelines/cli/build_gold.py`.
- Modelos em `analytics/dbt/models/gold/`; testes singulares em `analytics/dbt/tests/gold_*.sql`; seeds em
  `analytics/dbt/seeds/`.
- Testes em `tests/{contracts,unit,integration}/`; fixture em `tests/fixtures/gold/ci_seed.py`.

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Acrescentar à fixture `tests/fixtures/gold/ci_seed.py`: `district_or_island` nos municípios (Aveiro,
  Aveiro, Lisboa, Ilha da Madeira); `source_subregion` em todos os anúncios (nos das ilhas, `Madeira (Ilha)`); e
  pelo menos 10 anúncios só distritais de Aveiro (região `Centro`), para 0102 herdar. Manter `0101 × T2` próprio,
  a freguesia própria `010101`, o único outlier do `T2` municipal e os municípios, freguesias e critérios atuais

**Registro da Fase**:

- Status: Concluída (2026-11-26).
- Feito: a fixture ganhou `district_or_island`, `source_subregion` e 10 anúncios `T2` só distritais de Aveiro (800
  a 890 €, valores diferentes dos de 0101, para a herança ser distinguível). Lisboa fica sem anúncios (distrito sem
  região, R-001) e a Madeira fica com 2 anúncios só regionais.
- Contrato: sem contrato nesta fase; trava da 012 íntegra.
- Testes executados: `uv run --locked ruff check pipelines tests` (limpo) e
  `uv run --locked python -m pytest tests/contracts/test_gold_indicators_contract.py tests/integration/test_gold_build.py -q --basetemp .pytest_tmp`
  → 11 passaram.
- Pendências: nenhuma.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase terminar.

- [X] T002 Generalizar `_outliers(listings, key="dico")` em `pipelines/gold/rent.py`, sem mudar o comportamento
  padrão (`logic/heranca.md` §1) → contrato da 011 continua verde
- [X] T003 [P] Em `pipelines/gold/prepare.py`, ler `district_or_island` em `load_inputs` e incluir
  `source_subregion` em `LISTING_COLUMNS`
- [X] T004 [P] Criar a seed `analytics/dbt/seeds/idealista_island_aliases.csv` (`logic/heranca.md` §2) e, em
  `pipelines/gold/common.py`, `ORIGIN_LEVELS` e `ORIGIN_COLUMNS = ("origin", "origin_level")` (sem mexer em
  `INDICATOR_COLUMNS`)

### Testes da Fase

- Rodar `uv run --locked python -m pytest tests/contracts/test_gold_indicators_contract.py tests/integration/test_gold_build.py -q --basetemp .pytest_tmp`

**Critério de Conclusão**: contrato e integração da 011 verdes com a fixture nova.

**Registro da Fase**:

- Status: Concluída (2026-11-26).
- Feito: `rent._outliers` aceita a coluna do território (`key`, padrão `dico`); `prepare` lê `district_or_island` e `source_subregion`; criada a seed `idealista_island_aliases.csv` e as constantes `ORIGIN_LEVELS` e `ORIGIN_COLUMNS`.
- Contrato: sem contrato da 012 nesta fase; o da 011 verde (5/5) e a trava da 012 íntegra.
- Testes executados: `ruff` limpo; contrato e integração da 011 mais `tests/unit/test_gold_*.py` → 58 passaram.
- Pendências: nenhuma.

---

## Phase 3: User Story 1 - Aluguel por distrito e por região na Gold (Priority: P1) 🎯 MVP

**Objetivo**: duas tabelas Gold com a mediana de aluguel por distrito e por região, consultáveis e testadas.

**Independent Test**: build sobre a fixture e conferir uma linha por área com anúncios × tipologia, sem mediana
abaixo de 10.

### Contrato da Fase

- `test_us1_ac1_ac4_fr001_fr004_fr006_district_and_region_use_every_listing_of_the_area_with_their_own_iqr` —
  US1-AC1–AC4, FR-001–FR-004, FR-006
- `test_fr003_fr005_hierarchy_has_one_region_per_municipality_and_rejects_unknown_or_ambiguous_areas` — FR-003,
  FR-005
- Comando: `uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp -k "us1 or fr003"`

### Implementation

- [X] T005 [US1] Implementar a colocação dos anúncios e `territory_hierarchy` em `pipelines/gold/areas.py`
  (`logic/heranca.md` §2 e §3) → contrato: `test_fr003_fr005_...`
- [X] T006 [US1] Implementar `district_rent_stats` e `region_rent_stats` em `pipelines/gold/areas.py` (§4, FR-001,
  FR-002) → contrato: `test_us1_ac1_ac4_...`
- [X] T007 [P] [US1] Criar `analytics/dbt/models/gold/gold_rent_by_district_typology.sql` e
  `gold_rent_by_region_typology.sql`, lendo `rent_district.parquet` e `rent_region.parquet` (`data-model.md`)
- [X] T008 [US1] Declarar as duas tabelas em `analytics/dbt/models/gold/schema.yml`, com **todas** as colunas
  descritas, `meta.source_ids: [idealista]`, `not_null` nas chaves, `accepted_values` de `typology`,
  `sample_status` e `source_region` (as 7 regiões) (FR-015)
- [X] T009 [US1] Testes de dados em `analytics/dbt/tests/`: novo `gold_rent_area_matches_caop.sql` (todo
  `district_or_island` existe em `dim_municipality`; toda `source_region` distrital existe na tabela regional) —
  **sem** `relationships` genérico (research.md); ampliar `gold_key_unique.sql`, `gold_rent_min_sample.sql` e
  `gold_value_ranges.sql` (faixa 100–10 000) (FR-015)
- [X] T010 [US1] Em `pipelines/gold/prepare.py`, calcular as duas tabelas e gravar `rent_district` e `rent_region`;
  em `pipelines/cli/build_gold.py`, acrescentar as duas a `GOLD_TABLES`

### Testes da Fase

- [X] T011 [P] [US1] Criar `tests/unit/test_gold_areas.py`: paridade com `rent_stats` quando o distrito tem um só
  município (SC-005); `source_region` vazia; anúncio sem distrito conta só na região; `dico` desconhecido falha;
  snapshot vazio devolve tabelas vazias com colunas
- [X] T012 [US1] Ampliar `tests/integration/test_gold_build.py`: as 10 tabelas existem, sem `listing_id`, e um
  segundo build repete o conteúdo

**Critério de Conclusão**: o comando do contrato com `-k "us1 or fr003"` → 2/2 verdes e
`check-contract-tests.ps1 -Slug 012-aluguel-distrito-regiao` íntegro; build da fixture com os testes dbt verdes.

**Checkpoint**: User Story 1 funcional e testável isoladamente.

**Registro da Fase**:

- Status: Concluída (2026-11-26).
- Feito: `areas.py` com a colocação dos anúncios, `territory_hierarchy`, `district_rent_stats` e `region_rent_stats`; `rent._frame` aceita as colunas; modelos `gold_rent_by_district_typology` e `gold_rent_by_region_typology` declarados no `schema.yml`; teste singular `gold_rent_area_matches_caop` e os testes de chave, amostra e faixa ampliados; `prepare` e `build_gold` gravam e promovem as duas tabelas.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp -k "us1 or fr003"` → 2/2 verdes; trava íntegra.
- Testes executados: `ruff` limpo; contratos da fase, `tests/unit/test_gold_areas.py` (6), contrato e integração da 011 com o caso novo → todos verdes. Uma iteração: uma asserção minha no teste de paridade contava errado os outliers do dado sintético; corrigido o dado.
- Pendências: nenhuma.

---

## Phase 4: User Story 2 - Município herda o aluguel do distrito ou da região, marcado (Priority: P1)

**Objetivo**: todo município com referência na área tem aluguel, marcado com a origem e o nível.

**Independent Test**: no build da fixture, 0101 é `proprio`, 0102 herda do distrito e a normalização não muda.

### Contrato da Fase

- `test_us2_ac1_ac4_fr007_fr010_municipality_inherits_per_variant_from_the_finest_area_and_marks_it` — US2-AC1–AC4,
  FR-007–FR-010
- `test_us2_ac5_fr011_sc004_normalization_uses_only_own_municipal_values` — US2-AC5, FR-011
- Comando: `uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp -k "us1 or fr003 or us2"`

### Implementation

- [X] T013 [US2] Implementar a cadeia de referência e `reference_levels` em `pipelines/gold/areas.py`
  (`logic/heranca.md` §5 e §6, FR-010)
- [X] T014 [US2] Implementar `apply_rent_inheritance` em `pipelines/gold/areas.py` (§7, FR-007–FR-009) →
  contrato: `test_us2_ac1_ac4_...`
- [X] T015 [US2] Em `pipelines/gold/criteria.py`, `_values` filtra `origin == "proprio"` em qualquer nível que
  tenha a coluna (§9, FR-011) → contrato: `test_us2_ac5_...`
- [X] T016 [US2] Ajustar `tests/unit/test_gold_parish.py::test_parish_normalization_ignores_inherited_values`: o
  perfil municipal falso descarta `origin` (e `origin_level`) antes do `catalog_tables` (§9)
- [X] T017 [US2] Em `pipelines/gold/prepare.py`, aplicar a herança **antes** da freguesia, do catálogo e da
  qualidade; gravar `origin` e `origin_level` no perfil municipal e as 4 colunas de `reference_levels` na tabela
  municipal de aluguel (D9)
- [X] T018 [US2] Atualizar `gold_municipality_indicator.sql`, `gold_rent_by_municipality_typology.sql` e
  `schema.yml` (colunas novas descritas; `accepted_values` de `origin`, `origin_level` e `reference_level`)
- [X] T019 [US2] Criar `analytics/dbt/tests/gold_rent_inherited_equals_source.sql` (FR-016): todo `distrito` ou
  `regiao` é igual em valor, período, licença e atribuição à linha de origem (`custo_aluguel_mediana` →
  `rent_median`; `custo_aluguel_m2` → `eur_m2_median`) e falha se outro critério usar esses níveis. Ampliar
  `gold_absence_has_reason.sql` com a coerência de `origin` e `origin_level` (D6)
- [X] T020 [US2] Atualizar `methodology_pt` de `custo_aluguel_mediana` e `custo_aluguel_m2` em
  `config/criteria.yml` com a cadeia de herança e a região da fonte, não NUTS (FR-017, R-003); não mexer em pesos.
  Usar `>-` (texto com `": "` quebra o YAML)

### Testes da Fase

- [X] T021 [P] [US2] Em `tests/unit/test_gold_areas.py`: `reference_levels`; ilha `regional_only` que herda e
  mantém `rent_coverage`; variante sem próprio fica sem linha de normalização; critério sem nenhum próprio levanta
  `CriteriaError` (R-004)
- [X] T022 [US2] Em `tests/integration/test_gold_build.py`: 0102 herda o distrito; o P5/P95 usa só próprios; as
  linhas não-aluguel saem `proprio` ou `ausente`

**Critério de Conclusão**: o comando do contrato da fase → 4/4 verdes e trava íntegra; build da fixture com
`gold_rent_inherited_equals_source` verde; `tests/unit/test_gold_*.py` verdes.

**Checkpoint**: User Stories 1 e 2 funcionam; o ranker já teria aluguel nos municípios com referência.

**Registro da Fase**:

- Status: Concluída (2026-11-26).
- Feito: `reference_levels` e `apply_rent_inheritance` com uma única resolução da cadeia; a normalização usa só `origin = proprio` em qualquer nível (a mensagem do `CriteriaError` passou a dizer "nenhum valor próprio"); o `prepare` aplica a herança antes da freguesia, do catálogo e da qualidade; colunas novas nos modelos municipais e no `schema.yml`; teste `gold_rent_inherited_equals_source` (que também reprova herança com amostra própria) e coerência de `origin` em `gold_absence_has_reason`; metodologia dos dois critérios de aluguel atualizada, sem mexer em pesos.
- Contrato: `... -k "us1 or fr003 or us2"` → 4/4 verdes; trava íntegra.
- Testes executados: todos os `tests/unit/test_gold_*.py`, contrato e integração da 011 e contratos da fase → 73 passaram (o da US3 desmarcado); `ruff` limpo após descartar uma variável não usada num teste novo.
- Pendências: nenhuma. O ajuste previsto em `test_gold_parish.py` (T016) foi necessário.

---

## Phase 5: User Story 3 - Freguesia herda em cadeia e a qualidade mostra a origem (Priority: P2)

**Objetivo**: a freguesia diz de que nível veio cada número, e a qualidade conta próprios e herdados por nível.

**Independent Test**: no build da fixture, cada freguesia tem `origin_level` coerente e a qualidade fecha as contas.

### Contrato da Fase

- `test_us3_ac1_ac2_fr012_fr014_parish_chain_keeps_the_source_level_and_quality_counts_it` — US3-AC1/AC2,
  FR-012–FR-014
- Comando: `uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp`

### Implementation

- [X] T023 [US3] Em `pipelines/gold/parish.py`, preencher `origin_level` (`logic/heranca.md` §8, FR-012, FR-013) →
  contrato: `test_us3_...`
- [X] T024 [US3] Em `pipelines/gold/quality.py`, contar próprios nos dois níveis e herdados por nível (§10, FR-014)
  → contrato: `test_us3_...`
- [X] T025 [US3] Atualizar `gold_parish_indicator.sql`, `gold_data_quality.sql` e `schema.yml` (colunas novas e as
  descrições de `origin`, `with_value`, `missing` e `inherited`, conforme `data-model.md`)
- [X] T026 [US3] Atualizar `analytics/dbt/tests/gold_quality_consistency.sql` (contagens do perfil municipal só com
  `origin = 'proprio'`; `inherited` por nível igual ao perfil) e
  `gold_parish_inherited_equals_municipality.sql` (`origin_level` do herdado igual ao do município; próprio =
  `freguesia`; ausente nulo)

### Testes da Fase

- [X] T027 [US3] Atualizar `tests/integration/test_gold_build.py::test_quality_mart_lists_the_whole_catalog_and_matches_the_profile`
  (`with_value` compara só os próprios) e conferir os herdados por nível no município e na freguesia

**Critério de Conclusão**: o comando do contrato → 5/5 verdes e trava íntegra; build da fixture com todos os testes
dbt verdes.

**Checkpoint**: as três stories funcionam.

**Registro da Fase**:

- Status: Concluída (2026-11-26).
- Feito: `origin_level` na freguesia (o herdado leva o nível de onde o município tirou o valor); a qualidade conta cobertura só com valor próprio nos dois níveis e separa os herdados em `inherited_municipio`, `inherited_distrito` e `inherited_regiao`; modelos e `schema.yml` atualizados; `gold_quality_consistency` passou a conferir também a freguesia; `gold_parish_inherited_equals_municipality` confere `origin_level`.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp` → 5/5 verdes; trava íntegra.
- Testes executados: contratos da 012 e da 011, integração Gold com o caso novo e `tests/unit/test_gold_*.py` → 75 passaram; `ruff` limpo após ordenar um bloco de import em `parish.py`.
- Pendências: nenhuma.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T028 [P] Atualizar `analytics/notebooks/explorar_gold.ipynb` para ler as duas tabelas novas e as colunas de
  origem, sem o SQL do protótipo (`aluguel_regional`) nem a leitura de `idealista_listings`; salvar **sem saídas**
  (FR-018). Atualizar `.planning/memory/duckdb-2-api-e-notebook.md`
- [X] T029 [P] Regenerar `.docs/modelo_de_dados.md` com `uv run --locked python -m pipelines.cli.model_docs` (FR-018)
- [X] T030 [P] Atualizar `.docs/runbooks/coletas.md` (tabelas novas, cadeia, região da fonte), `README.md` e a linha
  "Custo" do §8.3 em `.docs/plano_plataforma_recomendacao_portugal.md` ("senão herda do município" → cadeia)
- [X] T031 Rodar o `quickstart.md` no lake real (guardar a normalização **antes**), registrar os números e a nova
  `catalog_version` (SC-001–SC-006)
- [X] T032 Registrar nota em `.planning/memory/` e levar R-005, R-006 e R-007 ao `.planning/backlog.md`
- [X] T033 Suíte completa, `ruff` e travas das specs 011 e 012

### Checklist de Release

- [X] Fase 1 e Fase 2 concluídas
- [X] Fase 3 (User Story 1) concluída
- [X] Fase 4 (User Story 2) concluída
- [X] Fase 5 (User Story 3) concluída
- [X] Testes de contrato todos verdes na suíte completa e `check-contract-tests.ps1` íntegro (012 e 011)
- [X] `uv run --locked ruff check pipelines tests` e `uv run --locked python -m pytest -q --basetemp .pytest_tmp`
  verdes
- [X] Build da fixture (`ci_seed` + `build_gold`) e `model_docs --check` verdes
- [X] Nenhuma linha por anúncio na Gold e notebook sem saídas (constitution IV e VI)
- [X] Nenhum segredo nos arquivos novos (constitution I)
- [X] `quickstart.md` executado com sucesso no lake real

---

**Registro da Fase**:

- Status: Concluída (2026-11-26).
- Feito: notebook lendo da Gold o aluguel por área e a origem, sem saídas; dicionário regenerado (35 tabelas, 10 na
  Gold); runbook, README e §8 do plano do projeto; build real com catálogo `6917af159e07`; notas de memória e backlog
  (R-005, R-006, R-007).
- Contrato: na suíte completa, 012 e 011 verdes; as duas travas íntegras.
- Testes executados: `uv run --locked ruff check pipelines tests` limpo;
  `uv run --locked python -m pytest -q --basetemp .pytest_tmp` → 853 passaram (13 min); `ci_seed` + `build_gold` em
  pasta nova e `model_docs --check` verdes; notebook executado com `nbconvert`, sem erros. Quickstart no lake real:
  SC-001 150/25 e 42/7, nenhuma mediana com n < 10; SC-002 42/254/12/0; SC-003 0 divergências em 1 915 herdados
  municipais e 199 143 de freguesia; SC-004 normalização idêntica à anterior; SC-005 por teste unitário e pelas
  colunas antigas da tabela municipal idênticas; SC-006 build verde. Contra a Gold anterior, nenhum valor existente
  mudou ou sumiu.
- Pendências: nenhuma de implementação. A abertura manual do notebook na interface (quickstart §4) não foi feita;
  R-010 fica para o ranker.

## Dependencies & Execution Order

- Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6.
- A US2 depende da US1 (sem as tabelas não há o que herdar). A US3 depende da US2.
- T015 e T016 andam juntas (o teste antigo quebra assim que o filtro muda).
- T007 e T010 precisam estar no mesmo estado antes de rodar o build (modelo sem arquivo preparado falha).

## Parallel Opportunities

- T003 e T004; T007 enquanto T005–T006; T028–T030.

## Implementation Strategy

MVP: Fases 1–3 (tabelas por distrito e região). Entrega pedida pelo autor: até a Fase 4. Parar e validar em cada
checkpoint.

<!-- sdd-converge anexa "## Phase N: Convergence" abaixo desta linha -->
