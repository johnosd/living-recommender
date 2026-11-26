# Implementation Plan: Marts de indicadores e criteria_catalog versionado

**Slug**: `011-marts-indicadores-catalogo` | **Date**: 2026-11-24 | **Spec**: `.sdd/specs/011-marts-indicadores-catalogo/spec.md`

**Nota**: Este template é preenchido pelo skill `sdd-plan`; a definição do skill
descreve o fluxo de execução completo.

## Summary

Construir a camada Gold no lake local, sobre as tabelas já promovidas pelas specs 001–009:

- perfil municipal longo (308 municípios × critério × variante), com proveniência, período usado e motivo
  de cada ausência;
- aluguel descritivo do Idealista, com outliers marcados por IQR;
- clima mensal e anual (extremos e TCI do legado, adaptados ao Open-Meteo);
- o `criteria_catalog` versionado (`config/criteria.yml` → `gold_criteria_catalog` e
  `gold_criteria_normalization`), que falha o build quando um critério disponível fica sem dado;
- mart de qualidade (P2) e perfil de freguesia com origem `proprio`/`herdado` (P3).

Abordagem: funções puras em `pipelines/gold/` (pandas), um `prepare` que lê o lake e grava parquet num
candidato, a tag dbt `gold` que tipa e testa, e a CLI `build_gold` que promove tabela a tabela para
`lake/gold/`. É o mesmo padrão de `build_mobility`. Só roda localmente; o S3 depende da Fase 1.

## Technical Context

**Language/Version**: Python 3.12 (`requires-python >=3.12,<3.13`); SQL DuckDB nos modelos dbt.

**Primary Dependencies**: pandas e numpy (transitivas de `geopandas`, já usadas em `build_mobility`), pyarrow,
PyYAML, dbt-core e dbt-duckdb ≥ 1.9, duckdb. Nenhuma dependência nova.

**Storage**: parquet no lake local: lê `.data/lake/{bronze,silver}/<tabela>/data.parquet` e escreve
`.data/lake/gold/<tabela>/data.parquet`. Catálogo versionado em `config/criteria.yml`.

**Testing**: pytest (`tests/contracts`, `tests/unit`, `tests/integration`), testes dbt (`schema.yml` e
`analytics/dbt/tests/gold_*.sql`), e o CI do GitHub Actions (`.github/workflows/python.yml`).

**Target Platform**: CLI local Windows/Linux (`uv run python -m pipelines.cli.build_gold --local`). A tarefa
ECS/MWAA fica para a Fase 1 (ADR-001); o código não depende de S3.

**Performance Goals**: build real em poucos minutos. O clima diário (2,25 M linhas nas 10 variáveis usadas) é
pivotado uma vez; o resto tem menos de 300 mil linhas.

**Constraints**: constitution III (nada imputado, proveniência por linha, n ≥ 10); ADR-002 D8 / ADR-004
(atribuição do Google); seleção dbt sempre por tag (`dbt_project.yml`, R-007 da 002); promoção por caminho
(`_promote.py`), nunca da pasta `gold/` inteira.

**Scale/Scope**: 308 municípios, 3 259 freguesias, cerca de 60 critérios (17 são setores CAE),
`gold_parish_indicator` com cerca de 250 mil linhas.

## Decisões Invariantes

- **D1. Fonte única de verdade dos critérios:** `config/criteria.yml`. Incluir ou mudar um critério é editar o
  YAML; o código só conhece os `kind` de `contracts/criteria-catalog.md` §1.2.
- **D2. Cálculo em Python, tipo e teste em dbt.** As regras ficam nos módulos de `pipelines/gold/`
  (`logic/*.md`); os modelos dbt só fazem `cast` do parquet preparado e carregam os testes. Nenhuma regra é
  reescrita em SQL.
- **D3. Grão longo:** uma linha por território × critério × variante, inclusive as ausências (FR-001). Nenhum
  "wide" no lake.
- **D4. Período:** o mais recente com valor **do município**, com a bandeira `is_older_period` (Clarifications
  de 2026-11-24). O denominador é sempre do mesmo período do numerador.
- **D5. `-` vira 0 só onde o critério declara `dash_is_zero: true`** (datasets de contagem), com
  `value_status = zero_convencao_fonte` (R-001).
- **D6. Outliers:** IQR de Tukey (1,5) por município × tipologia, só com n ≥ 10; a marca não vai ao lake; a
  freguesia reaproveita a marca municipal.
- **D7. Percentis com interpolação linear** em todo lugar.
- **D8. `catalog_version` = hash do conteúdo** (definições + normalização), e não um número manual.
- **D9. Herdado = cópia exata do município** (valor e proveniência), com `origin = herdado`. Só `proprio`
  entra na cobertura própria e na normalização da freguesia.
- **D10. Códigos em português ASCII** (`disponivel`, `fonte_pendente`, `observado`, `proprio`...), como em
  `sem_rota` e `pendente` da spec 009.
- **D11. Build isolado e atômico:** candidato em `.data/.build/gold/<uuid>`; qualquer falha (validação,
  `CriteriaError`, dbt) preserva o `lake/gold/` anterior.

## Constitution Check

*GATE: deve passar antes da Fase 0. Reavaliado após o design da Fase 1.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | ✅ | ✅ | Não lê chave nem `.env`; só parquet local. |
| II. Núcleo estático e sem chave | ✅ | ✅ | O Gold alimenta o futuro `published/vN`; nenhum servidor. |
| III. Dados honestos e rastreáveis | ✅ | ✅ | Ausência com motivo; proveniência por linha; n ≥ 10; junção por DICO/DICOFRE; herdado sinalizado. O `-` → 0 é regra explícita e marcada, decisão do autor (R-001), e não imputação silenciosa. |
| IV. Coleta responsável e licenciada | ✅ | ✅ | Sem coleta. Google com atribuição e restrição (risco aceito, ADR-002 D8). Só agregados do Idealista. |
| V. Bruto imutável e publicação atômica | ✅ | ✅ | Não toca `raw/`; promoção por caminho com rollback (D11). `current.json` fica fora (Fase 4/5). |
| VI. Privacidade por padrão | ✅ | ✅ | Nenhuma linha por anúncio no Gold; a marca de outlier fica em memória. |
| VII. Custo como requisito | ✅ | ✅ | Nenhum recurso com custo; só local. |
| Restrição: dbt + DuckDB em ECS (ADR-001) | ✅ | ✅ | Mesmo dbt-duckdb, que hoje roda local; a tarefa ECS é Fase 1. Não contraria o ADR. |
| Quality gates 3 e 6 | ✅ | ✅ | Testes dbt em todos os modelos novos; `criteria_catalog` versionado; `.docs/modelo_de_dados.md` regenerado. |

Sem violações: o Complexity Tracking fica vazio.

## Project Structure

### Documentation (this feature)

```text
.sdd/specs/011-marts-indicadores-catalogo/
├── spec.md
├── plan.md                 # este arquivo
├── research.md             # medições no lake real e decisões técnicas
├── data-model.md           # tabelas Gold, colunas e códigos
├── contracts/
│   └── criteria-catalog.md # formato de config/criteria.yml, catalog_tables, catálogo inicial
├── logic/
│   ├── indicadores.md      # observações (período, "-", denominador) e mobilidade
│   ├── clima.md            # extremos e TCI
│   └── aluguel.md          # IQR, n >= 10, rent_coverage
├── quickstart.md
├── contract-tests.lock
├── handoff.md
└── tasks.md
```

### Source Code (repository root)

```text
analytics/dbt/
├── dbt_project.yml                  # + pasta gold com tag 'gold'
├── models/gold/                     # NOVO: gold_*.sql + schema.yml (fontes caop_silver, testes)
└── tests/gold_*.sql                 # NOVO: testes singulares
config/
├── sources.yml                      # lido para licença/atribuição (não muda)
├── poles.yml                        # não muda
└── criteria.yml                     # NOVO: catálogo de critérios
pipelines/
├── cli/
│   ├── _promote.py                  # reutilizado
│   ├── build_mobility.py            # modelo de referência do build
│   └── build_gold.py                # NOVO
├── gold/                            # NOVO (stubs criados pelo plan)
│   ├── __init__.py
│   ├── criteria.py                  # load_criteria, catalog_tables, CriteriaError
│   ├── observations.py              # municipal_indicators
│   ├── climate.py                   # climate_monthly, climate_indicators
│   ├── rent.py                      # rent_stats, parish_rent_stats
│   ├── mobility.py                  # mobility_indicators
│   ├── parish.py                    # NOVO no execute: parish_indicators
│   ├── quality.py                   # NOVO no execute: data_quality
│   └── prepare.py                   # NOVO no execute: prepare_gold (lê o lake, grava o candidato)
└── modeldocs/{catalog,model,render,site}.py   # + camada gold
tests/
├── contracts/test_gold_indicators_contract.py # TRAVADO
├── unit/test_gold_*.py                        # NOVOS
├── integration/test_gold_build.py             # NOVO
└── fixtures/gold/ci_seed.py                   # NOVO: lake mínimo offline
.github/workflows/python.yml                   # + passo do build Gold
.docs/modelo_de_dados.md                       # regenerado por model_docs
```

**Structure Decision**: o pacote `pipelines/gold/` segue a separação de `pipelines/collectors/<fonte>/`
(lógica) e `pipelines/cli/build_<x>.py` (orquestração e promoção). Os modelos ficam em
`analytics/dbt/models/gold/`, com tag própria, como cada feature anterior.

## Complexity Tracking

> **Preencher SOMENTE se o Constitution Check tiver violações que precisam ser justificadas**

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → E2E → manual (último recurso).

Comandos-base:

```powershell
uv run ruff check pipelines tests
uv run python -m pytest -q --basetemp .pytest_tmp
uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 011-marts-indicadores-catalogo
uv run python -m tests.fixtures.gold.ci_seed --root .data/ci-gold
uv run python -m pipelines.cli.build_gold --local --root .data/ci-gold --criteria .data/ci-gold/criteria.yml
uv run python -m pipelines.cli.model_docs --check
```

- **Unitário** (`tests/unit/test_gold_*.py`): validação do YAML real e das regras de `load_criteria`;
  `presence`/`share`/NBSP; clima anual (verão, inverno, precipitação anualizada); freguesia
  (próprio/herdado); qualidade.
- **Integração** (`tests/integration/test_gold_build.py`): build completo com dbt sobre o fixture; um segundo
  build dá o mesmo conteúdo; dbt que falha preserva a versão anterior; um critério disponível sem dado falha
  com o id na mensagem; a pasta do candidato é sempre removida.
- **Manual**: build real e consultas do `quickstart.md`.

### Testes de Contrato

Arquivos travados em `contract-tests.lock`: `tests/contracts/test_gold_indicators_contract.py`

Comando: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp`

O script de trava não tem adaptador para pytest (contagem "unknown"). A contagem manual dá **5 funções de
teste**, sem `skip`/`xfail`/`parametrize`.

| Teste | Origem | Fase | Vermelho esperado (antes do execute) |
| --- | --- | --- | --- |
| `test_us1_ac1_ac4_fr001_fr003_fr004_fr005_latest_period_per_municipality_same_year_population_and_dash_rule` | US1-AC1/AC4, FR-001, FR-003–FR-005, Constitution III | Fase 3 | `NotImplementedError: municipal_indicators` |
| `test_us1_ac2_ac3_fr020_fr021_fr022_fr024_catalog_fails_on_available_without_data_and_versions_every_change` | US1-AC2/AC3, FR-020–FR-022, FR-024 | Fase 3 | `NotImplementedError: catalog_tables` |
| `test_us1_ac6_fr015_fr016_fr018_tci_bands_and_extreme_days_follow_the_legacy_rules` | US1-AC6, FR-015, FR-016, FR-018, SC-005 | Fase 3 | `NotImplementedError: climate_monthly` |
| `test_us1_fr009_fr010_fr011_fr012_rent_marks_iqr_outliers_without_deleting_and_needs_ten_listings` | FR-009–FR-012, SC-006, Constitution III | Fase 3 | `NotImplementedError: rent_stats` |
| `test_us1_ac5_fr007_fr008_mobility_uses_ok_pairs_only_and_carries_google_attribution` | US1-AC5, FR-007, FR-008, ADR-002 D8 | Fase 3 | `NotImplementedError: mobility_indicators` |

Vermelho confirmado em 2026-11-24: 5 failed, todos por `NotImplementedError`. A suíte existente
(contratos + unitários) continuou com 614 passed.

Stubs criados pelo plan (ponto de partida do execute, não travados): `pipelines/gold/__init__.py`,
`pipelines/gold/criteria.py`, `pipelines/gold/observations.py`, `pipelines/gold/climate.py`,
`pipelines/gold/rent.py`, `pipelines/gold/mobility.py`.

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. Vazia na criação. -->

| Área | Estado |
| --- | --- |
| Catálogo (`config/criteria.yml`) | 62 critérios, 12 categorias; `distancia_sede_distrito_km` pendente; build real `160da2ce8218` |
| Perfil municipal (US1) | Pronto: 20 328 linhas (66 critério × variante × 308), com as médias anuais da máxima e da mínima |
| Qualidade (US2) | Pronta: `gold_data_quality`, 78 linhas |
| Freguesia (US3) | Pronta: 215 094 linhas (3 259 × 66); SC-007 sem divergência; faixas testadas no dbt |
| Contrato | 5/5 verdes; as 11 travas do repositório íntegras |
| dbt (tag `gold`) | 8 modelos + 8 testes singulares, verdes no fixture e no lake real |
| Documentação | `.docs/modelo_de_dados.md` regenerado (`--check` verde), runbook, README, memória e backlog |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | `-` lido como zero em contagens (decisão do autor, 2026-11-24). O INE define `-` como "nulo ou não aplicável". | Um "não aplicável" pode virar 0. | Resolvido: só onde o critério declara `dash_is_zero`; `value_status = zero_convencao_fonte`; contagem no mart de qualidade; regra no `methodology_pt`. |
| R-002 | Sede de distrito sem polo em `config/poles.yml`. | FR-007 fica parcial: o critério entra como `fonte_pendente`. | Spec futura de mobilidade (recoleta); o catálogo já tem o id. Levado ao backlog em 2026-11-24 (T041). |
| R-003 | Pesos internos, direções e faixas das opções (clima, porte) são provisórios. | O ranking da Fase 4 depende deles. | São dados (`config/criteria.yml`): o autor revisa antes da Fase 4; qualquer mudança gera uma `catalog_version` nova. |
| R-004 | Neve `> 0` conta ruído do ERA5 (124 dias < 0,1 cm). | `clima_dias_neve_pct` é ligeiramente inflado. | Resolvido: regra do legado mantida (FR-015); peso 0 (só filtro); registrado na metodologia. |
| R-005 | Janela de clima de 24 meses, não normais de 30 anos. | Médias sensíveis a um ano atípico. | Resolvido: período explícito em toda linha (`início/fim`); documentado na metodologia. |
| R-006 | Pordata e Google com `not_granted_by_source`. | Restrição de publicação. | Resolvido: licença copiada por linha e no catálogo; a decisão de publicar é da Fase 4/5 (riscos já aceitos nos ADRs). |
| R-007 | Ilhas sem tempo de carro até Lisboa/Porto. | Cobertura ponderada menor no ranker. | Resolvido: ausência com motivo `sem_par_elegivel`; a linha reta existe como alternativa (peso 0). |
| R-008 | Rótulos do Pordata com NBSP (`"A. \xa0Agricultura…"`). | Um filtro que não casa deixa o critério sem dado. | Resolvido: normalização de espaços (`logic/indicadores.md`); os 17 setores CAE têm valor; FR-020 falha o build nesse caso. |
| R-009 | Desemprego registado não é uma taxa oficial. | O indicador é um proxy. | Resolvido: "Por 100 residentes de 15–64 anos", explicado no rótulo e na metodologia. |
| R-010 | A tag `gold` lê tabelas de outras features. | Rodar `--select tag:gold` sem o lake das specs 001–009 falha. | Resolvido: o `build_gold` confere a presença das entradas antes do dbt; o CI usa `tests/fixtures/gold/ci_seed.py`. |
| R-011 | `check-contract-tests.ps1` não conta testes pytest. | O orçamento de 5 não é verificado pelo script. | Resolvido: contagem manual (5) registrada acima e conferida na convergência. |
| R-012 | O dbt recusa a fonte `caop_silver` declarada duas vezes (T001 pedia uma nova, via `GOLD_SILVER_DIR`). | A Gold depende da declaração em `models/bronze/schema.yml`. | Resolvido: a Gold reusa a fonte existente e o `build_gold` passa `OBS_SILVER_DIR = <root>/lake/silver`, como a mobilidade. |
| R-013 | Censos por freguesia não têm `source_id`, e o `dataset_id` muda por lote (`pop_2025_batch_NNN`). | A proveniência da freguesia precisa de um id estável. | Resolvido: na freguesia, `source_id = censos` (id de `config/sources.yml`), `dataset_id = census_parish_observation`. |
| R-014 | Dois testes unitários da 010 (não travados) fotografavam o projeto só com bronze e silver. | A camada gold os quebrou na suíte completa (2 failed, 834 passed). | Resolvido (T043): a 010 espera `{bronze, silver, gold}`, e a lista fixa de principais cobre só bronze e silver, mantendo a decisão da 010 de não cobrar modelos novos. O contrato travado da 010 não mudou e segue verde. |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-24 | Setup + Foundational | Tag `gold`, camada gold no `modeldocs`, `common.py`, `config/criteria.yml` (60 critérios), `load_criteria`, fixture. 84 testes verdes (inclui o contrato da 010). | — |
| 2026-11-24 | US1 | Perfil municipal, aluguel, clima, mobilidade, catálogo e `build_gold`. Contrato 5/5; build real `c528890b92fa`: 59 disponíveis, 1 pendente, 19 712 linhas, desemprego 278/308, renda INE 255/308, aluguel próprio em 42 municípios (ALL). | US2 |

| 2026-11-24 | US2 | `quality.py`, `gold_data_quality` e o teste de consistência; o `build_gold` imprime a cobertura por categoria × nível e os pendentes. Real: desemprego 278/308, sede pendente. | US3 |
| 2026-11-24 | US3 | `parish.py`, `parish_rent_stats`, 2 modelos de freguesia e o teste SC-007. Real: catálogo `d738fdca5257`, 208 576 linhas, 135 freguesias com aluguel próprio (ALL), população própria nas 3 259, 75 linhas de normalização. | Polish |
| 2026-11-24 | Polish | Quickstart §3 sem divergência; §4: pesos trocados → `01dc08866ff8`, desfeitos → `d738fdca5257`; dataset inválido falha citando `'cultura_cinemas_10k'` e mantém os mesmos bytes em `lake/gold`. Docs regenerados, runbook, README, memória e backlog. São 8 tabelas Gold (o "9" do quickstart e do T037 era erro de contagem; o `data-model.md` lista 8). | Converge; A1 com o autor |

| 2026-11-24 | Convergence (fase 7) | C1: `clima_temp_max_anual` e `clima_temp_min_anual` (peso 0, FR-014); C2: `gold_value_ranges.sql` cobre também as tabelas de freguesia (FR-031). Real: catálogo `160da2ce8218`, 61 disponíveis + 1 pendente, 20 328 linhas municipais, 215 094 de freguesia (3 259 × 66). O A1 está resolvido pela FR-029. | — |

**PRÓXIMO**: `/sdd-converge 011-marts-indicadores-catalogo`.

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint — foco da etapa atual, não a árvore inteira. -->

- `config/criteria.yml` — catálogo (fonte única de verdade)
- `pipelines/gold/` — `criteria`, `observations`, `rent`, `climate`, `mobility`, `parish`, `quality`, `prepare`
- `pipelines/cli/build_gold.py` — candidato, dbt `tag:gold`, promoção por tabela (`GOLD_TABLES`)
- `analytics/dbt/models/gold/` (8 modelos + `schema.yml`) e `analytics/dbt/tests/gold_*.sql`
- `tests/fixtures/gold/ci_seed.py`, `tests/integration/test_gold_build.py`, `tests/unit/test_gold_*.py`
- `.docs/runbooks/coletas.md` (seção "Build Gold"), `.planning/memory/marts-gold-011-execucao.md`

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- `methodology_pt` com `": "` em escalar YAML sem aspas quebra o parse (aconteceu em `config/criteria.yml` e no
  `schema.yml` do dbt): use `>-` ou aspas.
- Uma tabela nova tem de entrar em `GOLD_TABLES` (`build_gold.py`), senão não é promovida, mesmo com o dbt verde.
- O `prepare` do build real leva cerca de 16 s (medido em 2026-11-24); o pivot do clima é a parte mais pesada.
- A suíte completa leva cerca de 11 minutos (648 s em 2026-11-24, com 836 testes); rode-a em segundo plano.
- Testes da 010 que leem o projeto real (`test_modeldocs_model.py`, `test_modeldocs_principal_described.py`)
  quebram com qualquer camada ou modelo principal novo; ajuste-os junto (R-014).

## Resultado Final

<!-- Anexado pelo sdd-converge em 2026-11-24. -->

**Construído:**

- A camada Gold no lake local (`lake/gold/`), com 8 tabelas, montada pelo `uv run python -m pipelines.cli.build_gold --local --root .data`.
- A lógica fica em `pipelines/gold/` (`criteria`, `observations`, `rent`, `climate`, `mobility`, `parish`, `quality`, `prepare`).
- O dbt (tag `gold`) só fixa os tipos e roda os testes: 8 modelos e 8 testes singulares.
- A promoção é feita tabela a tabela, com rollback.

**Números do build real (catálogo `160da2ce8218`):**

- 62 critérios em 12 categorias: 61 disponíveis e 1 pendente (`distancia_sede_distrito_km`).
- 20 328 linhas municipais (66 critério × variante × 308) e 215 094 de freguesia (× 3 259).
- Aluguel próprio em 42 municípios e 135 freguesias.
- Verificação: o contrato está 5/5 com a trava íntegra, e a suíte completa passou com 836 testes.

**Desvios em relação ao plano original:**

- O T001 previa uma fonte dbt nova (`GOLD_SILVER_DIR`); a Gold reusa `caop_silver` via `OBS_SILVER_DIR` (R-012).
- Os Censos usam `source_id = censos` e `dataset_id = census_parish_observation` (R-013).
- Os testes da 010 que leem o projeto real foram ajustados à camada gold (T043, R-014).
- São 8 tabelas Gold, não as 9 citadas no quickstart e no T037 (o `data-model.md` lista 8).
- A convergência acrescentou `clima_temp_max_anual` e `clima_temp_min_anual` (FR-014). A tabela do catálogo inicial em `contracts/criteria-catalog.md` §3 é o retrato do planejamento e não os inclui; `config/criteria.yml` é a fonte de verdade.
- O teste de faixas passou a cobrir também as tabelas de freguesia (FR-031).
- A1 do Analyze: a mediana `ALL` própria na freguesia com n ≥ 10 segue a FR-029.

**Continua em aberto (backlog):**

- R-002: sede de distrito; a FR-007 fica parcial por decisão de escopo.
- R-003: revisão de pesos, direções e faixas antes da Fase 4.
- A execução no S3 depende da Fase 1.
