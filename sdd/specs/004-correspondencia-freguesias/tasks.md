---
description: "Tasks da feature 004: correspondência de freguesias 2013→2025"
---

# Tasks: Correspondência de freguesias 2013→2025

**Input**: Documentos de design de `sdd/specs/004-correspondencia-freguesias/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/correspondencia-cli.md, logic/derivacao-correspondencia.md

**Organization**: Tasks agrupadas por user story para implementação e teste independentes. Os 5 contratos já existem e estão **travados** em `contract-tests.lock`; o executor só os faz passar, nunca os edita.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story a task pertence (US1, US2, US3)
- Caminhos de arquivo exatos nas descrições

## Path Conventions

- Coletor e regras em `pipelines/collectors/parish_crosswalk/`; CLIs em `pipelines/cli/`; comum em `pipelines/collectors/_shared/` (só `http.py` muda).
- dbt em `analytics/dbt/models/crosswalk/` e `analytics/dbt/tests/`.
- Testes em `tests/unit/`, `tests/integration/`, `tests/fixtures/parish_crosswalk/`; contratos travados em `tests/contracts/`.
- Comando de teste: `uv run --locked python -m pytest -q --basetemp .pytest_tmp <alvo>`; lint: `uv run --locked ruff check pipelines tests`.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: catálogo, downloader e configuração dbt.

- [X] T001 Acrescentar a fonte `ine_parish_crosswalk` em `config/sources.yml` exatamente como em `data-model.md` §1, e um teste em `tests/unit/test_parish_crosswalk_catalog.py`: `load_catalog()` aceita o catálogo real; `get_dataset_source(..., "ine_parish_crosswalk", strict_metadata=True)` devolve os 2 datasets com `format=xlsx`, `sheet`, `role` e `columns`; fonte com `origin` não-HTTPS é recusada antes da rede (FR-001, FR-019)
- [X] T002 [P] Em `pipelines/collectors/_shared/http.py` acrescentar `xlsx_content_check(content_type, first_chunk, url)`: recusa `text/html` e corpo que não comece por `PK\x03\x04`, com mensagem "resposta HTML no lugar de planilha"/"arquivo não é planilha xlsx"; teste em `tests/unit/test_http_content_checks.py` (arquivo existente: só acrescentar casos)
- [X] T003 [P] Em `analytics/dbt/dbt_project.yml` acrescentar `crosswalk: +tags: ['parish_crosswalk']` em `models:`; em `analytics/dbt/models/bronze/schema.yml` acrescentar a tabela `dim_parish` ao source **existente** `caop_silver` (não criar outro source; R-008). Não alterar mais nada nesses arquivos

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: a leitura da planilha, compartilhada por validação e transformação.

**⚠️ CRITICAL**: US1, US2 e US3 dependem de `layout.py`.

- [X] T004 Criar `pipelines/collectors/parish_crosswalk/layout.py` com `normalize_code`, `normalize_label` e `load_rows(dataset, path)` exatamente como em `logic/derivacao-correspondencia.md` §1. A exceção é `CrosswalkSchemaError` (definida em `validate.py`; importar de lá). A mensagem de código inválido SEMPRE traz o valor ofensivo
- [X] T005 [P] Testes em `tests/unit/test_parish_crosswalk_layout.py`: `normalize_code` (texto com espaços, `int` de 6 dígitos, `int` de 5 e de 7 dígitos, `float` inteiro, `float` com decimal, `bool`, minúscula, tamanho errado, alfanumérico `0308FC`); `load_rows` (rótulo da tabela B com dois espaços casando com o catálogo de um espaço, aba ausente, coluna ausente, legenda vs linha inválida, linha vazia pulada sem contar, planilha com 36 colunas vazias além das mapeadas)

**Checkpoint**: leitura pronta; as stories podem começar.

---

## Phase 3: User Story 1 - Coletar as duas tabelas do INE com rastreabilidade (Priority: P1) 🎯 MVP

**Objetivo**: baixar, validar e guardar as duas planilhas como bruto imutável, com manifest, `unchanged` e falha isolada por tabela.

**Independent Test**: com o downloader offline da fixture, rodar a coleta num destino vazio e conferir 2 brutos + manifest; repetir e conferir `unchanged` sem bruto novo; trocar uma resposta por HTML e conferir a falha explícita sem arquivo parcial.

### Contrato da Fase

- `test_us1_ac1_ac2_ac3_fr002_fr003_fr004_both_tables_are_stored_untouched_and_state_is_per_table` (US1/AC1-AC3)
- `test_us1_ac4_ac5_fr005_invalid_tables_fail_per_table_without_partial_raw_and_recover_next_run` (US1/AC4-AC5)
- `test_fr005_fr006_reader_keeps_codes_as_text_normalizes_whole_numeric_cells_and_ignores_legends` (FR-005, FR-006)
- Comando: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py -k "us1 or fr005"`

### Implementation

- [X] T006 [US1] Implementar `validate_crosswalk_table` em `pipelines/collectors/parish_crosswalk/validate.py` sobre `load_rows` (exigir ao menos uma linha de dado; qualquer erro vira `CrosswalkSchemaError` com o motivo) → contrato: `test_us1_ac4_ac5_…`, `test_fr005_fr006_…`
- [X] T007 [US1] Implementar `read_crosswalk_table` em `pipelines/collectors/parish_crosswalk/transform.py`: colunas e estatísticas conforme `data-model.md` §3; `partial_origin` só no papel `pre2013_to_2013` (`logic/` §1); nomes sem espaços nas pontas → contrato: `test_fr005_fr006_…`
- [X] T008 [US1] Implementar `collect_parish_crosswalk` em `pipelines/collectors/parish_crosswalk/handler.py` como em `logic/` §2 (envoltório de `collect_datasets`; **não** alterar `_shared/datasets.py`) → contrato: `test_us1_ac1_ac2_ac3_…`, `test_us1_ac4_ac5_…`
- [X] T009 [US1] Criar `pipelines/cli/collect_parish_crosswalk.py` seguindo `collect_pordata.py` e `contracts/correspondencia-cli.md`: `add_destination_arguments`, `HttpDownloader(content_check=xlsx_content_check, timeout=120.0, rate_limiter=RateLimiter(1.0))`, `print_result("Correspondência INE", …)`, `exit_code`

### Testes da Fase

- [X] T010 [P] [US1] `tests/integration/test_collect_parish_crosswalk_local.py`: CLI com downloader offline injetado: `changed` → `unchanged` sem bruto novo (SC-003) → só a tabela alterada gravada; código de saída 0/1; tabela que falha não impede a outra; `--s3` sem `--bucket` é erro de uso
- [X] T011 [P] [US1] `tests/integration/test_collect_parish_crosswalk_s3.py` (moto, como `test_collect_pordata_s3.py`): mesmas chaves, bytes e manifest que o local; escrita negada falha antes de qualquer download
- [X] T012 [P] [US1] `tests/unit/test_parish_crosswalk_validate.py`: HTML, arquivo vazio, ZIP que não é planilha, aba/coluna ausente, planilha só com cabeçalho, mensagens citam o dataset

**Critério de Conclusão**: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py -k "us1 or fr005"` → 3/3 verdes, `check-contract-tests.ps1 -Slug 004-correspondencia-freguesias` íntegro, e T010 a T012 verdes.

**Checkpoint**: User Story 1 funcional e testável isoladamente.

**Registro da Fase**:

- Status: Concluída em 2026-11-12.
- Feito: `validate_crosswalk_table` (T006), `read_crosswalk_table` (T007), `collect_parish_crosswalk` (T008) e a CLI `collect_parish_crosswalk` (T009), todos sobre `layout.py`; testes T010 a T012. `layout.py` foi endurecido: XML corrompido dentro de um ZIP válido (estoura em `load_workbook`) vira `CrosswalkSchemaError` em vez de exceção solta, achado do teste T012.
- Contrato: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py -k "us1 or fr005"` → 3/3 verdes; `check-contract-tests.ps1` → trava íntegra. Os contratos de US2 e US3 seguem vermelhos por `NotImplementedError` (esperado).
- Testes executados: `ruff check pipelines tests` limpo; `tests/unit` + `tests/contracts` 214 verdes e 2 vermelhos esperados; T010–T012 (18 testes novos: 5 integração local, 2 S3, 11 do validador) verdes, mais os 31 do layout e os 3 do catálogo das fases anteriores. Nenhuma instabilidade observada.
- Pendências: nenhuma. Coleta real contra o INE fica para T026.

---

## Phase 4: User Story 2 - Tabela de correspondência 2013→2025 (Priority: P1)

**Objetivo**: derivar a tabela de pares com a natureza da relação e os sinais, promovê-la com o dbt e disponibilizá-la ao lado da `dim_parish`.

**Independent Test**: com as tabelas da fixture, derivar e conferir os 19 pares; reconstruir e conferir o resultado idêntico; construir o Silver sobre a fixture e conferir o Parquet promovido.

### Contrato da Fase

- `test_us2_ac1_to_ac6_fr007_to_fr011_fr014_pairs_relations_flags_and_determinism` (US2/AC1-AC6)
- Comando: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py -k us2`

### Implementation

- [X] T013 [US2] Implementar `derive_parish_crosswalk` em `pipelines/collectors/parish_crosswalk/derive.py` conforme `logic/` §3 (merge na granularidade da linha da A; sem `drop_duplicates` por `pre_code`; erro se a B tiver `pre_code` ausente da A ou se um código de 2013 tiver duas designações) → contrato: `test_us2_…`
- [X] T014 [US2] Em `pipelines/cli/build_parish_crosswalk.py`, função `prepare_crosswalk(root, output_dir, *, processed_at_utc, catalog=None)`: lê `latest_dataset_states` das duas tabelas (FR-015: exige as duas, bruto no disco, `sha256`/`bytes` conferindo; a mensagem diz qual falta ou está inválida), lê com `read_crosswalk_table`, deriva e grava `prepared/crosswalk.parquet` com as colunas de `data-model.md` §4 (incluindo `source_run_id_*`, `sha256_*`, `license_id`, `attribution`, `collected_at_utc`, `processed_at_utc`); devolve contagens e `codes_2013`
- [X] T015 [US2] Modelo `analytics/dbt/models/crosswalk/xwalk_parish_2013_2025.sql` (materialização `external`, Parquet em `XWALK_BUILD_DIR/lake/silver/xwalk_parish_2013_2025/data.parquet`, entrada em `XWALK_PREPARED_DIR/crosswalk.parquet`, tipos fixados com `cast`, como `stg_observation.sql`) e `analytics/dbt/models/crosswalk/schema.yml` com `not_null` nas chaves e na proveniência, `relationships` de `dicofre_2025` com `source('caop_silver','dim_parish')`, `accepted_values` de `relation`. Teste singular `analytics/dbt/tests/parish_crosswalk_key_unique.sql` (par único) e `parish_crosswalk_relation_consistency.sql` (a natureza e `inherited` conferem com as contagens por par)
- [X] T016 [US2] Em `pipelines/cli/build_parish_crosswalk.py`: `build_parish_crosswalk(root)` (candidato em `.data/.build/parish_crosswalk/<uuid>`, `dbt build --select tag:parish_crosswalk` com as variáveis de `logic/` §5, `promote_paths` dos dois caminhos de `lake/silver`, remoção do candidato no `finally`), `write_review_csv` (`;`, `utf-8-sig`) e `main` (`--local`, `--root`; códigos 0/1; resumo de `contracts/correspondencia-cli.md`)

### Testes da Fase

- [X] T017 [P] [US2] `tests/unit/test_parish_crosswalk_derive.py`: B vazia (tudo um-para-um), pré-2013 duplicado, `pre_code` da B fora da A (erro), duas designações para o mesmo código de 2013 (erro), entrada embaralhada, nomes com espaços/acentos NFC vs NFD (`name_changed`)
- [X] T018 [US2] `tests/integration/test_parish_crosswalk_build.py` (cria `tests/fixtures/parish_crosswalk/ci_seed.py` nesta task, pois precisa da Silver mínima; o T024 só acrescenta o passo do CI): build promove o Parquet com as colunas e tipos certos; **SC-005**: todo `dicofre_2013` da fixture converte para ≥ 1 `dicofre_2025` por um único `merge`, com `inherited` informado; **SC-006**: SHA-256 de `dim_parish` e `dim_municipality` iguais antes e depois; a segunda execução produz a mesma tabela

**Critério de Conclusão**: `… -k us2` → 1/1 verde, `check-contract-tests.ps1` íntegro, `dbt build --select tag:parish_crosswalk` verde sobre a fixture e T017/T018 verdes.

**Checkpoint**: User Story 2 funcional e testável isoladamente.

**Registro da Fase**:

- Status: Concluída em 2026-11-12.
- Feito: `derive_parish_crosswalk` (T013), `prepare_crosswalk` e `build_parish_crosswalk` com `write_review_csv` e `main` (T014, T016), modelo dbt `xwalk_parish_2013_2025` com `schema.yml` e os testes singulares `parish_crosswalk_key_unique` e `parish_crosswalk_relation_consistency` (T015), `tests/fixtures/parish_crosswalk/ci_seed.py` (criado aqui, como o T018 pedia), testes T017 e T018. Validação extra, antes do T026: leitura e derivação sobre as **planilhas reais** do INE reproduziram exatamente os valores de referência (3.260 pares; 2.957/301/0/2; herança 303; origem parcial 8; nome alterado 297; município 0; 51 células numéricas).
- Contrato: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py -k us2` → 1/1 verde; `check-contract-tests.ps1` → trava íntegra. O contrato da US3 segue vermelho por `NotImplementedError` (esperado).
- Testes executados: `ruff check pipelines tests` limpo; `dbt build --select tag:parish_crosswalk` sobre a fixture → 18/18 (1 modelo + 17 testes); `tests/unit`, `tests/contracts` e os builds/coberturas das specs 001–003 (`test_caop_build`, `test_build_observations`, `test_observation_coverage`, `test_climate_build`, `test_climate_coverage`) → 248 verdes e 1 vermelho esperado. T017 (11 testes) e T018 (5 testes) verdes. Nenhuma instabilidade.
- Pendências: o build ainda não aplica o gate de cobertura nem promove o relatório; é a Fase 5 (T019–T021). Coleta e build reais contra o INE ficam para T026.

---

## Phase 5: User Story 3 - Cobertura contra a dimensão territorial, com reprovação (Priority: P2)

**Objetivo**: reprovar a promoção quando a correspondência não cobre a `dim_parish` e publicar o relatório de cobertura.

**Independent Test**: com uma `dim_parish` de fixture, a cobertura total promove; remover uma linha da tabela B (ou acrescentar uma freguesia à dimensão) reprova a promoção com a lista, preservando a tabela anterior.

### Contrato da Fase

- `test_us3_ac2_ac3_ac4_fr012_coverage_gate_lists_every_gap_by_kind` (US3/AC2-AC4)
- Comando: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py -k us3`

### Implementation

- [X] T019 [US3] Implementar `verify_coverage` e `CrosswalkCoverageError` em `pipelines/collectors/parish_crosswalk/coverage.py` conforme `logic/` §4 (as três listas ordenadas, a mensagem imprime cada código) → contrato: `test_us3_…`
- [X] T020 [US3] Em `build_parish_crosswalk.py`: carregar `lake/silver/dim_parish/data.parquet` (erro "execute build_caop primeiro" se ausente), chamar `verify_coverage(crosswalk, dim_codes, set(table_a.code_2013))` **antes** do dbt; no `main`, imprimir os códigos com os nomes da `dim_parish` (formato de `contracts/correspondencia-cli.md`) e sair com 1 sem tocar `lake/silver`
- [X] T021 [US3] Modelo `analytics/dbt/models/crosswalk/rpt_parish_crosswalk_coverage.sql` (colunas de `data-model.md` §5, linha `all` com `parishes_expected`/`parishes_with_origin` e `caop_version`) e testes: `not_null`/`unique` em `relation` no `schema.yml`; singulares `parish_crosswalk_every_parish_has_origin.sql` (toda `dim_parish` é `dicofre_2025`) e `parish_crosswalk_coverage_consistency.sql` (os totais fecham). Incluir no relatório as linhas e os pares com marcador `(parte)` (R-006)

### Testes da Fase

- [X] T022 [P] [US3] `tests/unit/test_parish_crosswalk_coverage.py`: duplicatas na entrada, listas vazias, `dim_parish_codes` como `set`/`list`/`Series`, ordenação, mensagem com os três tipos
- [X] T023 [US3] `tests/integration/test_parish_crosswalk_coverage_gate.py`: build verde promove e escreve o CSV de revisão com só os pares não um-para-um; build com freguesia sem origem, código de 2013 sem destino e destino fora da dimensão sai com 1, imprime os códigos e deixa `lake/silver/xwalk_parish_2013_2025` byte a byte igual ao anterior; um teste do dbt reprovado também preserva a tabela anterior

**Critério de Conclusão**: `… -k us3` → 1/1 verde, `check-contract-tests.ps1` íntegro, T022/T023 verdes e os três tipos de lacuna reprovando o build.

**Checkpoint**: User Story 3 funcional e testável isoladamente.

**Registro da Fase**:

- Status: Concluída em 2026-11-12.
- Feito: `verify_coverage` e `CrosswalkCoverageError` (T019, com `names` opcional para o build e mensagem limitada a 50 códigos por tipo; os atributos guardam todos); gate no `build_parish_crosswalk` antes do dbt, resumo com a linha "Cobertura" e `PROMOTED` com o relatório (T020); `prepare_crosswalk` passou a gravar `prepared/table_stats.parquet`; modelo `rpt_parish_crosswalk_coverage` e testes dbt `parish_crosswalk_every_parish_has_origin` e `parish_crosswalk_coverage_consistency` (T021); testes T022 e T023. `data-model.md` §5 sincronizado com as colunas `source_*` do relatório.
- Contrato: `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py` → **5/5 verdes** (o `-k us3` passa de primeira); `check-contract-tests.ps1` → trava íntegra.
- Testes executados: `ruff check pipelines tests` limpo; `dbt build --select tag:parish_crosswalk` sobre a fixture → 24/24 (2 modelos + 22 testes); `tests/unit` + `tests/contracts` → 237 verdes; T022 (10 testes), T023 (5 testes) e os 5 do T018 (que passaram a rodar com o gate e o relatório) → 20 verdes. T023 prova que cada lacuna reprova o build com os códigos na mensagem, e que uma falha do dbt (com o gate de Python desligado por monkeypatch) também deixa `xwalk`, relatório e CSV byte a byte iguais. Nenhuma instabilidade.
- Pendências: a lacuna "código de 2013 sem destino" não pode ser fabricada por arquivos (a tabela A produz um destino por construção); fica coberta no contrato e em `test_parish_crosswalk_coverage.py`. Coleta e build reais contra o INE: T026.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: CI, documentação, verificação real e checklist de release.

- [X] T024 Passo no `.github/workflows/python.yml`, já usando o `ci_seed.py` criado no T018 (`python -m tests.fixtures.parish_crosswalk.ci_seed --root .data/ci-xwalk`, que grava a `dim_parish` mínima com os códigos de 2025 do cenário de `tables.py` e o `prepared/crosswalk.parquet` derivado dele) rodando `dbt build --select tag:parish_crosswalk` com `XWALK_BUILD_DIR`, `XWALK_PREPARED_DIR`, `OBS_SILVER_DIR`, `CAOP_DUCKDB_PATH`, no padrão dos passos de observações e clima
- [X] T025 Documentação (Quality Gate 6): `.docs/fontes_de_dados.md` (§3.3: nova linha `ine_parish_crosswalk`; §3.4: pacote, CLIs e modelos; §3.2: contagem das fontes do catálogo), `docs/runbooks/coletas.md` (coletar e construir a correspondência; reprovação de cobertura), `README.md` (comandos). Corrigir a menção "correspondência 2013→2025 ficam para specs futuras" onde ela aparecer
- [X] T026 Verificação real (`quickstart.md` §4): rodar `collect_parish_crosswalk --local` e `build_parish_crosswalk --local` contra o INE; conferir os valores de referência (3.260 pares; 2.957/301/0/2; herança 303; origem parcial 8; nome alterado 297; município alterado 0; bruto 205.543 + 27.382 bytes) e a repetição `unchanged` (SC-001, SC-002, SC-003); registrar o resultado em `research.md`. Divergência exige explicação por mudança na fonte
- [X] T027 Suíte completa e CI: `ruff check pipelines tests`, `python -m pytest -q --basetemp .pytest_tmp` (todas as specs; SC-007) e `dbt build` por tag das quatro features; conferir o CI remoto no PR (**a parte remota fica no Checklist de Release**: exige push/PR, que o autor ainda não autorizou)
- [X] T028 Licença (R-002): consultar os termos do INE para as duas planilhas e a automação do download; atualizar `license_id` em `config/sources.yml` e `data-model.md` §1, ou registrar risco aceito pelo autor
- [X] T029 Rodar a validação de `quickstart.md` e fechar o `plan.md` (Estado Atual, Riscos)

### Checklist de Release

- [X] Fase 3 (User Story 1) concluída
- [X] Fase 4 (User Story 2) concluída
- [X] Fase 5 (User Story 3) concluída
- [X] Testes de contrato todos verdes na suíte completa e `check-contract-tests.ps1 -Slug 004-correspondencia-freguesias` íntegro
- [X] `ruff check pipelines tests` limpo e `python -m pytest -q --basetemp .pytest_tmp` verde
- [X] `dbt build --select tag:parish_crosswalk` verde sobre a fixture e sobre os dados reais
- [X] Contratos das specs 001 a 003 intactos (suíte completa)
- [X] `dim_parish`, `dim_municipality` e demais saídas com SHA-256 inalterado (SC-006)
- [X] `config/sources.yml` e `.docs/fontes_de_dados.md` atualizados (Quality Gate 6)
- [X] Nenhuma planilha real nem `.data/` no Git; `gitleaks` verde no CI (verificado localmente e no CI: [PR #4](https://github.com/johnosd/living-recommender/pull/4), run [43311137501](https://github.com/johnosd/living-recommender/actions/runs/43311137501), commit `e485a4e`, job `secrets` com "Scan Git history for secrets" = success)
- [X] `quickstart.md` executado com sucesso
- [X] Mensagens de commit curtas e em inglês (Quality Gate 7) (commit único `e485a4e`, `feat:feature/004-correspondencia-freguesias`: curto e em inglês, embora pouco descritivo)

---

## Rastreabilidade FR/SC → tasks

| Requisito | Tasks |
| --- | --- |
| FR-001, FR-019 | T001, T015, T025 |
| FR-002, FR-003, FR-004 | T008, T010, T011 (contrato 1) |
| FR-005, FR-006 | T004, T005, T006, T007, T012 (contratos 2 e 3) |
| FR-007 a FR-011, FR-014 | T013, T017 (contrato 4) |
| FR-012 | T019, T020, T021, T023 (contrato 5) |
| FR-013 | T016, T021, T023 |
| FR-015 | T014, T018 |
| FR-016 | T018, T026 |
| FR-017 | T009, T016, T011 |
| FR-018 | fixtures travadas + T024 |
| SC-001 | T020, T026 |
| SC-002 | T026 |
| SC-003 | T010, T026 |
| SC-004 | contrato 2, T012 |
| SC-005 | T018 |
| SC-006 | T018, T026 |
| SC-007 | T027 |

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Fase 1)**: sem dependências (T002 e T003 em paralelo com T001)
- **Foundational (Fase 2)**: depende do Setup; BLOQUEIA as stories
- **US1 (Fase 3)** → **US2 (Fase 4)** → **US3 (Fase 5)**: a US2 lê o estado vigente que a US1 grava; a US3 estende o build da US2
- **Polish (Fase 6)**: depende das três stories; T024 pode começar junto de T015

### Parallel Opportunities

- T002 e T003 (arquivos diferentes); T005 depois de T004; T010, T011 e T012 depois de T009; T017 em paralelo com T014; T022 em paralelo com T021

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Setup e Foundational
2. US1: coleta rastreável (valor sozinho: bruto auditável das duas tabelas)
3. US2: tabela de correspondência promovida
4. **PARAR E VALIDAR** com a coleta real (T026) antes de endurecer a cobertura (US3)

### Incremental Delivery

Cada story deixa o repositório verde e não quebra a anterior. Commits curtos e em inglês, um por task ou grupo coerente.

## Notes

- `[P]` = arquivos diferentes, sem dependência
- Os contratos e `tests/fixtures/parish_crosswalk/tables.py` são **travados**: se parecerem errados, pare e peça emenda ao autor; nunca edite.
- Não alterar `datasets.py`, `manifest.py`, o contrato de qualquer feature anterior nem os lakes de outras fontes.

<!-- sdd-converge anexa "## Phase N: Convergence" abaixo desta linha -->

## Phase 7: Convergence

**Purpose**: fechar as lacunas achadas pelo `sdd-converge` de 2026-11-12. Só os achados acionáveis viram tasks (CF-001 e CF-002); CF-003 a CF-007 são decisões do autor ou verificações externas e estão registrados em `plan.md` → `## Resultado Final` quando a feature convergir.

**Origem**: FR-013 e US3/AC5 (relatório legível, preservado, com data da coleta e versão da CAOP) e FR-019 (atribuição no relatório). Hoje essas informações existem só no Parquet do relatório e no `stdout`.

- [X] T030 [CF-002] [FR-019] Em `analytics/dbt/models/crosswalk/rpt_parish_crosswalk_coverage.sql`, acrescentar a coluna `attribution` (a mesma da tabela `xwalk_parish_2013_2025`, via `max(attribution)` sobre `pairs`), preenchida em todas as linhas; em `analytics/dbt/models/crosswalk/schema.yml`, `not_null` nela. Os testes dbt existentes continuam verdes
- [X] T031 [CF-001] [FR-013, US3/AC5] Em `pipelines/cli/build_parish_crosswalk.py`, `write_report_csv(root)` que lê o relatório promovido e grava `lake/silver/parish_crosswalk_report.csv` (`;`, `utf-8-sig`): uma linha por natureza mais `all`, todas as colunas do relatório, com `caop_version`, `collected_at_utc` e `attribution` repetidos em **todas** as linhas (hoje só a linha `all` os tem). Chamar no `build_parish_crosswalk` logo depois de `write_review_csv`, imprimir o caminho no resumo e acrescentar o arquivo a `TRACKED`/ao que a falha de cobertura deve preservar
- [X] T032 [CF-001, CF-002] Testes em `tests/integration/test_parish_crosswalk_coverage_gate.py`: o CSV do relatório existe, tem 5 linhas (4 naturezas + `all`), `caop_version`, `collected_at_utc` e `attribution` preenchidos em todas as linhas, e é codificável em cp1252 (`test_cli_output_can_be_printed_on_a_windows_console` continua valendo); uma falha de cobertura e uma falha do dbt deixam o CSV do relatório byte a byte igual (acrescentar o caminho a `TRACKED`)
- [X] T033 [CF-001, CF-002] Documentação: `data-model.md` §5 (o CSV do relatório e a coluna `attribution`), `contracts/correspondencia-cli.md` (layout em disco e saída), `docs/runbooks/coletas.md` (lista de arquivos), `.docs/fontes_de_dados.md` (linha da fonte) e `README.md` se citar os arquivos gerados
- [X] T034 Reverificação: `ruff check pipelines tests`; `python -m pytest -q --basetemp .pytest_tmp` (suíte completa); `dbt build --select tag:parish_crosswalk` na fixture; `build_parish_crosswalk --local` contra os dados reais conferindo o CSV do relatório (versão da CAOP `2025`, data da coleta, atribuição, os valores de referência de `quickstart.md` §4) e o SHA-256 de `dim_parish`, `dim_municipality`, `stg_observation` e `stg_climate_daily` inalterado; `check-contract-tests.ps1` íntegro nas quatro features

**Critério de Conclusão**: o relatório da correspondência existe como arquivo legível por pessoa, preservado junto das tabelas, com contagens por natureza, versão da CAOP, data da coleta e atribuição; os contratos seguem 5/5 verdes e as travas das quatro features íntegras; o `sdd-converge` roda de novo sem achado acionável.

**Registro da Fase**:

- Status: Concluída em 2026-11-12.
- Feito: coluna `attribution` no `rpt_parish_crosswalk_coverage` com `not_null` (T030, CF-002); `write_report_csv` e `REPORT_CSV` em `build_parish_crosswalk.py`, que grava `lake/silver/parish_crosswalk_report.csv` com `caop_version`, `collected_at_utc` e `attribution` em todas as linhas, e o caminho no resumo (T031, CF-001); testes novos em `test_parish_crosswalk_coverage_gate.py`, com o CSV do relatório no `TRACKED` das falhas de cobertura e do dbt (T032); `data-model.md`, `contracts/correspondencia-cli.md`, `logic/`, `plan.md`, runbook e `.docs/fontes_de_dados.md` sincronizados (T033); reverificação (T034). Achado e corrigido durante a reverificação: o teste T010 era instável (ver Testes executados e `plan.md` R-012).
- Contrato: `tests/contracts/test_parish_crosswalk_contract.py` → 5/5 verdes na suíte completa; `check-contract-tests.ps1` → trava íntegra nas quatro features (001 a 004). Nenhum arquivo travado foi tocado.
- Testes executados: `ruff check pipelines tests` limpo; suíte completa `python -m pytest -q --basetemp .pytest_tmp` → **319 passed**; dbt por tag: CAOP 31/31, observações 17/17, clima 23/23, correspondência 25/25. Build real contra o INE: 3.260 pares, 3.259 de 3.259 freguesias, valores idênticos à referência; o CSV real tem 5 linhas, `caop_version` 2025, coleta 2026-11-12T19:43:46Z e atribuição do INE em todas, e passa em `.encode("cp1252")`; SHA-256 de `dim_parish`, `dim_municipality`, `stg_observation` e `stg_climate_daily` idênticos antes e depois. **Uma execução da suíte completa teve 1 falha** (`test_changed_then_unchanged_then_only_the_altered_table_is_written`, 318 passed + 1 failed em 14m20s, máquina lenta): causa identificada e corrigida (o helper regerava as duas planilhas e o openpyxl grava a hora de criação com resolução de segundos, então os bytes da tabela A mudavam quando as gerações caíam em segundos diferentes). Reproduzido com um experimento de hash, corrigido reaproveitando os bytes da A e provado forçando 1,2 s entre as gerações; a suíte inteira foi rodada de novo depois, verde.
- Pendências: nenhuma de código. Continuam abertos, por dependerem do autor, os 2 itens do Checklist de Release (CI remoto/`gitleaks` e commits) e os achados CF-003 a CF-007 do converge (decisões, não tasks).
