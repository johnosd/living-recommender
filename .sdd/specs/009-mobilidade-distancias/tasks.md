---
description: "Tasks da spec 009 — mobilidade: distâncias e tempos de viagem até polos fixos"
---

# Tasks: Mobilidade — distâncias e tempos de viagem dos municípios até polos fixos

**Input**: `.sdd/specs/009-mobilidade-distancias/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/mobility-cli.md`, `logic/pares-e-estados.md`, `quickstart.md`, `handoff.md`)

**Prerequisites**: `plan.md` e `spec.md`. Leia `handoff.md` antes de começar.

**Organization**: por user story. Os testes de contrato já existem e estão **travados**: não os escreva nem
edite. **Esta feature não executa a coleta real do Google e não pede chave** (plan D13).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: US1, US2 ou US3

## Path Conventions

- Coletor: `pipelines/collectors/mobility/`; CLIs: `pipelines/cli/`; catálogos: `config/`
- dbt: `analytics/dbt/models/mobility/` e `analytics/dbt/tests/mobility_*.sql`
- Testes: `tests/unit/test_mobility_*.py`, `tests/integration/test_mobility_*.py`, fixtures em `tests/fixtures/mobility/`
- Comandos (copie e cole):
  - Lint: `uv run --locked ruff check pipelines tests`
  - Suíte: `uv run --locked python -m pytest -q --basetemp .pytest_tmp`
  - Contratos: `uv run --locked python -m pytest tests/contracts/test_mobility_contract.py -q --basetemp .data/tmp/mobility-contracts`
  - Trava: `powershell -NoProfile -Command "& .\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 009-mobilidade-distancias"`

---

## Phase 1: Setup

**Purpose**: catálogos antes de qualquer coletor (constitution IV) e linha de base.

- [ ] T001 Acrescentar a entrada `google_distances` em `config/sources.yml` conforme `data-model.md` §1:
  `license_id: not_granted_by_source`, atribuição "Tempos de viagem: Google", risco aceito (ADR-002 D8) e
  substituição, `max_elements_per_run: 2000`, `pricing_verified_on: null`, preço de referência do research R2
  (`driving` 5,0/10000) e `modes` com **só `driving`** (`DRIVE`, `TRAFFIC_UNAWARE`); **sem** `modes.transit`
  (decisão do autor, plan D14). **Sem `window` e sem `datasets`.**
- [ ] T002 [P] Criar `config/poles.yml` (`data-model.md` §2) com os **7 polos iniciais** (decisão do autor):
  cidades Lisboa 1106 e Porto 1312 (`scope: national`); aeroportos LIS, OPO, FAO (`national`), FNC (`island`,
  "Ilha da Madeira") e PDL (`island`, "Ilha de São Miguel"). Nada de sedes de distrito, Faro como cidade nem
  capitais regionais por ora (DICO para ampliar em research R7). Cada aeroporto leva `source_ref` verificada pelo
  executor numa fonte pública (anotar a URL).
- [ ] T003 Linha de base: rodar lint, a suíte e os contratos. Esperado: lint e suíte verdes (exceto os 5
  contratos), contratos vermelhos por `NotImplementedError` e `check-contract-tests.ps1` íntegro.

---

## Phase 2: Foundational (bloqueia as stories)

**Purpose**: entradas validadas, elegibilidade e estado por par.

- [ ] T004 Criar `pipelines/collectors/mobility/municipalities.py` com `load_mobility_municipalities(silver_dir)`:
  lê `dim_municipality/data.parquet` e devolve `{dico, name, latitude, longitude, district_or_island,
  autonomous_region, routing_group}` (`logic/pares-e-estados.md` §1; `NaN` → `None`; região desconhecida é
  erro). Reusar `check_municipalities` do clima para o conjunto de 308 e as caixas de coordenadas.
- [ ] T005 [P] Escrever `tests/unit/test_mobility_catalog.py`: uma rejeição por regra de `data-model.md` §1
  (campo ausente, `api_url` HTTP, modo desconhecido, `transit` sem partida, partida em fim de semana, número ≤ 0,
  presença de `window`), mais o catálogo real de `config/sources.yml` aceito.
- [ ] T006 Implementar `mobility_source` em `pipelines/collectors/mobility/catalog.py` e rotear
  `google_distances` em `load_catalog` (`pipelines/collectors/_shared/catalog.py`, ao lado do ramo `wikipedia`,
  antes dos testes `window`/`datasets`). Garantir que os testes de catálogo existentes seguem verdes.
- [ ] T007 [P] Escrever `tests/unit/test_mobility_poles.py` e `tests/unit/test_mobility_pairs.py`: cada regra de
  rejeição de `resolve_poles` (id duplicado, `dico` inexistente, aeroporto sem coordenadas/`source_ref`,
  coordenada fora da caixa, escopo incoerente, campo desconhecido), a mensagem cita o `pole_id`, e a
  elegibilidade (`national`/`district`/`island`, ilhas sem polo). Um teste lê `config/poles.yml` real contra a
  silver real e confere ~1.404 pares por modo, **ignorado se `.data/lake/silver/dim_municipality` não existir**.
- [ ] T008 Implementar `resolve_poles`, `load_poles` e `poles_catalog_version` em
  `pipelines/collectors/mobility/poles.py` (`data-model.md` §2). Rejeita o catálogo inteiro, antes de qualquer
  cálculo, com o `pole_id` na mensagem (FR-002).
- [ ] T009 Implementar `pair_id` e `route_pairs` em `pipelines/collectors/mobility/pairs.py`
  (`logic/pares-e-estados.md` §2–§4); saída ordenada por `id`.
- [ ] T010 Criar `pipelines/collectors/mobility/state.py` com `pair_signature`, `is_current_state` e
  `latest_attempts(storage)` (última entrada de cada par, de qualquer status, entre os manifests da fonte), mais
  `tests/unit/test_mobility_state.py` (assinatura estável, muda com cada campo de `logic` §4, falha mais nova não
  apaga estado vigente).

**Checkpoint**: catálogo, polos, pares e estado prontos e testados.

---

## Phase 3: User Story 1 — Linha reta dos 308 municípios até os polos (Priority: P1) 🎯 MVP

**Objetivo**: distância em linha reta, sem API, para todo par município × polo, gravada no staging com
proveniência. Entrega valor sozinha.

**Independent Test**: com a dimensão e `config/poles.yml`, `build_mobility` produz `308 × 7` linhas
`straight_line` com `status=ok`, e uma segunda execução gera o mesmo conteúdo.

### Contrato da Fase

- `test_us1_fr001_fr004_fr005_fr006_fr013_fr014_eligible_pairs_and_straight_line_cover_every_municipality`
  — US1-AC1/AC2/AC5, FR-001/004/005/006/013/014.
- Comando: `uv run --locked python -m pytest tests/contracts/test_mobility_contract.py -q -k test_us1 --basetemp .data/tmp/mobility-contracts`

### Implementation

- [ ] T011 [US1] Implementar `straight_line_rows` em `pipelines/collectors/mobility/straight_line.py`, reusando
  `haversine_km` de `pipelines/collectors/open_meteo/points.py` → contrato: `test_us1_...`
- [ ] T012 [US1] Implementar `build_distance_rows` em `pipelines/collectors/mobility/rows.py`: linhas de
  `straight_line` (`logic` §5) e, para `driving`/`transit`, um estado por par esperado (incluindo identidade,
  `stale`, `falha`, `pendente`), lendo os manifests por `latest_dataset_states` e `latest_attempts`. Com o
  storage vazio, todos os pares de rota saem `pendente`.
- [ ] T013 [US1] Criar `pipelines/cli/build_mobility.py` no molde de `pipelines/cli/build_climate.py`: `prepare`
  (Parquet em área temporária; `dim_mobility_pole` e `distances`), `dbt build --select tag:mobility`,
  `promote_paths` para `lake/bronze/{stg_municipality_pole_distance,dim_mobility_pole,rpt_mobility_coverage}`.
  Falha preserva a versão anterior; `dico` do estado sem correspondência na dimensão falha o build (FR-020).
- [ ] T014 [US1] Criar `analytics/dbt/models/mobility/` (`stg_municipality_pole_distance.sql`,
  `dim_mobility_pole.sql`, `schema.yml` com `not_null`, `unique` na chave composta via teste, `relationships` com
  `dim_municipality` e `dim_mobility_pole`, `accepted_values` de `status` e `mode`), a tag `mobility` em
  `analytics/dbt/dbt_project.yml` e `tests/fixtures/mobility/ci_seed.py` (silver mínima sintética, sem rede).

### Testes da Fase

- [ ] T015 [P] [US1] `tests/unit/test_mobility_straight_line.py` (valores conhecidos: 1° de latitude ≈ 111,195 km;
  simetria; antimeridiano não ocorre) e `tests/unit/test_mobility_rows.py` (estados e `stale` por tabela de
  `logic` §5); `tests/integration/test_mobility_build.py` (build completo com dbt sobre o fixture: contagem
  `308 × 7` de linha reta, rodar duas vezes dá o mesmo hash do Parquet, falha do dbt preserva o anterior).

**Critério de Conclusão**: `-k test_us1` → 1/1 verde e `check-contract-tests.ps1` íntegro; lint verde;
`build_mobility --local --root .data/ci-mobility` sobre o fixture passa; as linhas `straight_line` cobrem
100% dos pares, sem nulo (SC-001), e a chave `(dico, pole_id, mode)` é única (SC-002).

**Checkpoint**: US1 funcional e testável isoladamente.

**Registro da Fase**:

- Status:
- Feito:
- Contrato:
- Testes executados:
- Pendências:

---

## Phase 4: User Story 2 — Cálculo único de carro (Priority: P2)

**Objetivo**: CLI que estima, confirma e consulta o Google uma vez, com retomada e sem vazar a chave.

**Independent Test**: com `MockTransport`, estimar (zero chamadas), executar com confirmação, interromper e
retomar consultando só os pendentes.

### Contrato da Fase

- `test_us2_ac1_ac2_ac3_fr008_fr009_fr010_...` — estimativa sem chave/rede, confirmação e teto.
- `test_us2_ac4_ac6_ac7_fr011_fr012_fr016_fr017_fr018_...` — `ok`/`sem_rota`/`falha`/`pendente`, parada em 403.
- `test_us2_ac5_us3_ac1_ac3_fr015_fr024_fr025_...` — retomada, idempotência, `stale` só dos pares do polo alterado.
- `test_constitution_i_fr010_fr028_...` — a chave nunca aparece em storage, saída nem erros.
- Comando: `uv run --locked python -m pytest tests/contracts/test_mobility_contract.py -q --basetemp .data/tmp/mobility-contracts`

### Implementation

- [ ] T016 [US2] Implementar `resolve_api_key` e `redact` em `pipelines/collectors/mobility/secrets.py`
  (variável de `key_env` no `env`, senão `.env` simples `CHAVE=valor` na raiz; nunca imprime valor; `redact`
  troca a chave por `[REDACTED]`) → contrato: `test_constitution_i_...`
- [ ] T017 [US2] Implementar `make_routes_fetcher` em `pipelines/collectors/mobility/fetch.py` no molde de
  `open_meteo/fetch.py`: `POST` conforme `contracts/mobility-cli.md`, `RateLimiter`, retry com backoff, 401/403
  → `AuthorizationStop(StopCollection)` (criar em `pipelines/collectors/mobility/` ao lado do fetch), 429/
  `RESOURCE_EXHAUSTED` → `QuotaExhausted`, gravação atômica do destino, **toda** mensagem de erro (inclusive o
  corpo do servidor e a exceção do `httpx`) passa por `redact` → contrato: `test_us2_ac4_...`,
  `test_constitution_i_...`
- [ ] T018 [US2] Implementar `validate_routes_response` em `pipelines/collectors/mobility/validate.py`
  (`research` R3): lista de um elemento, `originIndex == destinationIndex == 0`, `ROUTE_EXISTS` com
  `distanceMeters` inteiro ≥ 0 e `duration` `"<n>s"`, ou `ROUTE_NOT_FOUND`; `status.code != 0` → `ValueError`
  → contrato: `test_us2_ac4_...`
- [ ] T019 [US2] Implementar `collect_mobility` em `pipelines/collectors/mobility/handler.py`: monta os itens de
  `route_pairs` sem identidade, ordena por `id`, injeta em `entry_extra` o que `data-model.md` §3 lista e usa
  `collect_items(skip_current=True, state_is_current=...)` com `max_items=max_elements`. Sem alterar
  `_shared/datasets.py` → contrato: `test_us2_ac4_...`, `test_us2_ac5_...`
- [ ] T020 [US2] Implementar `estimate_run` em `pipelines/collectors/mobility/estimate.py` (`logic` §7) →
  contrato: `test_us2_ac1_...`, `test_us2_ac5_...`
- [ ] T021 [US2] Implementar `main` em `pipelines/cli/collect_mobility.py` (`contracts/mobility-cli.md`):
  estimativa por padrão, recusas na ordem do contrato, validação da data de partida (futura, ≤ 90 dias, dia
  útil) **só se** `modes.transit` estiver habilitado, aviso de preço com mais de 30 dias, `--poles`, `--silver`, `--max-elements`, saída com códigos 0/1/2 e
  mensagens sem chave → contrato: `test_us2_ac1_...`, `test_constitution_i_...`

### Testes da Fase

- [ ] T022 [P] [US2] `tests/unit/test_mobility_validate.py`, `test_mobility_fetch.py` (retry, backoff, 429 dia
  vs minuto, 401, corpo não JSON, eco da chave), `test_mobility_secrets.py` (ambiente, `.env`, ausência),
  `test_mobility_estimate.py` (teto gratuito, pior caso, `stale` vs novo) e
  `tests/integration/test_mobility_cli.py` (CLI de ponta a ponta sobre `LocalStorage` e S3 simulado com `moto`,
  retomada após `Ctrl+C` simulado, refusals da ordem do contrato).

**Critério de Conclusão**: contratos 5/5 verdes e `check-contract-tests.ps1` íntegro; lint e suíte verdes; a CLI
estima com 0 chamadas de rede e sem chave (SC-004); uma retomada consulta 0 pares já gravados (SC-005); duas
execuções iguais gravam 0 brutos novos (SC-006); nenhuma ocorrência da chave em storage, saída ou erro (SC-007).

**Checkpoint**: US2 funcional; nenhuma chamada real feita.

**Registro da Fase**:

- Status:
- Feito:
- Contrato:
- Testes executados:
- Pendências:

---

## Phase 5: User Story 3 — Auditar cobertura e ausências (Priority: P2)

**Objetivo**: relatório que separa ausência verdadeira de pendência e lista o que ficou desatualizado.

**Independent Test**: sobre um staging com todos os estados, as contagens por modo e polo somam o esperado.

### Contrato da Fase

- Coberta por `test_us2_ac5_us3_ac1_ac3_...` (somas e `stale`) na Fase 4. Esta fase acrescenta o relatório
  publicado; sem contrato novo (o orçamento de 5 casos está usado).

### Implementation

- [ ] T023 [US3] Criar `analytics/dbt/models/mobility/rpt_mobility_coverage.sql` (contagens por `mode` e
  `pole_id`: `ok`, `sem_rota`, `falha`, `pendente`, `stale`, `expected`) e `analytics/dbt/tests/mobility_*.sql`:
  chave única, `km`/`minutes` nulos só fora de `ok` (e `minutes` nulo em `straight_line`), faixas plausíveis
  (`km` de 0 a 3.500; `minutes` de 0 a 3.000), soma dos quatro estados igual a `expected`, atribuição presente
  em toda linha `driving`/`transit` (FR-021, FR-022).
- [ ] T024 [US3] Em `pipelines/cli/build_mobility.py`, gerar `mobility_coverage.csv`, `mobility_no_route.csv`
  (com `expected_absence`), `mobility_pending.csv` e `mobility_stale.csv` em `lake/bronze/` e imprimir a
  cobertura por modo e polo (modelo: `write_coverage`/`format_coverage` do `build_climate`) (FR-023, FR-025).

### Testes da Fase

- [ ] T025 [P] [US3] `tests/integration/test_mobility_coverage.py`: fixture com os quatro estados e polo
  alterado; confere somas, lista de `sem_rota` com motivo, ausência esperada nas ilhas sem polo, `stale` listado e
  nenhum resultado alterado.

**Critério de Conclusão**: lint e suíte verdes; `dbt build --select tag:mobility` passa sobre o fixture; o
relatório reproduz as contagens do teste e diz se cada `sem_rota` é ausência esperada (SC-003, SC-008).

**Checkpoint**: US3 funcional.

**Registro da Fase**:

- Status:
- Feito:
- Contrato:
- Testes executados:
- Pendências:

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T026 Atualizar `.docs/fontes_de_dados.md` (linha `google_distances`: Routes API, um par por requisição,
  elegibilidade, estados, custo, polos; manter o "Risco aceito") e a seção de pendências do §3.3.
- [ ] T027 Acrescentar a seção "Mobilidade (spec 009)" em `.docs/runbooks/coletas.md`: comandos de estimativa,
  execução e build; **checklist do operador** (aprovar `config/poles.yml`, conferir preços e preencher
  `pricing_verified_on`, atualizar `departure_time`, criar a chave com restrição de API e orçamento, `.env`,
  estimativa, confirmar, executar, `build_mobility`); retomada; atribuição "Tempos de viagem: Google".
- [ ] T028 [P] Acrescentar ao `.github/workflows/python.yml` os passos "Prepare mobility fixture" e "Build dbt
  mobility from fixture" no molde dos de clima (`tests/fixtures/mobility/ci_seed.py`, `--select tag:mobility`).
- [ ] T029 Rodar o quickstart offline (`quickstart.md`) e a suíte completa, o lint e o dbt do fixture; conferir
  `check-contract-tests.ps1` e que **nenhuma** chave ou resposta real foi versionada (`git grep` do prefixo `AIza`).
- [ ] T030 Registrar em `.planning/memory/` uma nota `mobilidade-009-execucao.md` com os achados duráveis
  (contagem real de pares, `pricing_verified_on`, divergências A-001/A-002) e atualizar o backlog com
  `update-feature-status.ps1`.

### Checklist de Release

- [ ] Fase 3 (US1) concluída
- [ ] Fase 4 (US2) concluída
- [ ] Fase 5 (US3) concluída
- [ ] Testes de contrato 5/5 verdes na suíte completa e `check-contract-tests.ps1` íntegro
- [ ] `ruff check pipelines tests` limpo e suíte completa verde, sem rede
- [ ] `dbt build --select tag:mobility` verde sobre o fixture
- [ ] Docs: `config/sources.yml`, `.docs/fontes_de_dados.md`, runbook e `config/poles.yml` atualizados (constitution, gate 6)
- [ ] Nenhuma chave, resposta real ou arquivo de `.data/` no Git; scan de segredos passa
- [ ] **Não executado por esta feature (gate do autor)**: aprovação final de `config/poles.yml`, conferência de
  preços, coleta real do Google e `build_mobility` sobre dados reais; registrar como pendência, não como feito
- [ ] `quickstart.md` executado

---

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T010) → US1 (T011–T015) → US2 (T016–T022) → US3 (T023–T025) → Polish.
- Dentro do Foundational: T005 antes de T006; T007 antes de T008/T009; T010 depende de T009.
- US2 depende de T012 (`rows.py`) para os contratos 3 e 4. US3 depende de T013/T014.
- `[P]`: T002, T005, T007, T015, T022, T025, T028.

## Implementation Strategy

1. Setup + Foundational. 2. US1 (MVP: linha reta, entrega valor sozinha). **Pare e valide.** 3. US2.
4. US3. 5. Polish. Os contratos vão ficando verdes na ordem das fases; o vermelho restante é o esperado.

## Notes

- Não editar `tests/contracts/test_mobility_contract.py` nem `tests/fixtures/mobility/responses.py`.
- Não alterar `pipelines/collectors/_shared/datasets.py`; só `_shared/catalog.py` (T006).
- Commits curtos, em inglês. Sem commit/push/PR sem autorização do autor.

<!-- sdd-converge anexa "## Phase N: Convergence" abaixo desta linha -->
