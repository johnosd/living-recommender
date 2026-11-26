# Data Model: camada Gold (spec 011)

Todas as tabelas ficam em `lake/gold/<tabela>/data.parquet`, construídas pelo `build_gold` (tag dbt `gold`) e
promovidas uma a uma (`_promote.promote_paths`). Entradas, sempre do lake já promovido:

| Entrada | Camada | Uso |
| --- | --- | --- |
| `dim_municipality`, `dim_parish` | silver | universo de 308 municípios e 3 259 freguesias; área; região autónoma |
| `stg_observation` | bronze | Pordata e INE (`logic/indicadores.md` §1) |
| `stg_climate_daily` | bronze | clima (`logic/clima.md`) |
| `stg_municipality_pole_distance`, `dim_mobility_pole` | bronze | mobilidade (`logic/indicadores.md` §2) |
| `idealista_listings` | silver | aluguel (`logic/aluguel.md`) |
| `census_parish_observation` | silver | população da freguesia (P3) |
| `config/criteria.yml` | config | catálogo (`contracts/criteria-catalog.md`) |

## Códigos fechados

| Campo | Valores |
| --- | --- |
| `status` | `disponivel`, `fonte_pendente` |
| `value_status` | `observado`, `zero_convencao_fonte`, `ausente` |
| `origin` (freguesia) | `proprio`, `herdado`, `ausente` |
| `sample_status` | `suficiente`, `amostra_insuficiente`, `sem_anuncios` |
| `rent_coverage` | `propria`, `insuficiente`, `regional_only`, `sem_anuncios` |
| `typology` / `variant` (aluguel) | `ALL`, `T0`, `T1`, `T2`, `T3`, `T4+`; `variant = ""` nos demais critérios |
| `level` | `municipio`, `freguesia` |
| `missing_reason` | ver `logic/indicadores.md` §3 |

## `gold_municipality_indicator` — grão `dico` × `criterion_id` × `variant`

Uma linha para **cada** município × critério `disponivel` com `municipio` em `levels` × variante (FR-001).

| Coluna | Tipo | Nota |
| --- | --- | --- |
| dico | varchar | FK `dim_municipality` |
| criterion_id, category | varchar | FK lógica para `gold_criteria_catalog` |
| variant | varchar | `""` ou a tipologia |
| value | double | nulo = ausente |
| unit | varchar | do catálogo |
| period | varchar | ano, `AAAA-MM`, ou janela `início/fim` |
| dataset_latest_period | varchar | período nacional mais recente do critério |
| is_older_period | boolean | FR-003 |
| value_status | varchar | código fechado |
| missing_reason | varchar | não nulo ⇔ `value` nulo |
| source_symbol | varchar | símbolo da fonte (informativo) |
| source_id, dataset_id | varchar | proveniência |
| license_id, attribution, usage_restriction | varchar | da fonte; `usage_restriction` nula quando não há |
| is_stale | boolean | só mobilidade; `False` nos demais |
| catalog_version | varchar | igual à do catálogo do mesmo build |
| processed_at_utc | varchar | instante do build |

## `gold_parish_indicator` — grão `dicofre` × `criterion_id` × `variant` (P3)

Mesmas colunas, com `dicofre` e `dico` (FK `dim_parish` e `dim_municipality`) e mais:

| Coluna | Tipo | Nota |
| --- | --- | --- |
| origin | varchar | `proprio` (há `compute_parish` com valor), `herdado` (cópia exata do município), `ausente` |
| territorial_inheritance | varchar | `coverage_status` dos Censos (`own`/`inherited`/`missing`) nos critérios `census`; nulo nos demais |

Regra: há uma linha para todo critério `disponivel` (de qualquer nível) e toda freguesia. Com `compute_parish`
e valor próprio, `origin = proprio`. Senão, a linha herda **todas** as colunas de valor e de proveniência do
município (`origin = herdado`), ou fica `ausente` se o município também não tiver valor. A cobertura própria
(qualidade e normalização) só conta `proprio` (FR-030). Freguesias são normalizadas dentro do município pelo
ranker (plano §8.3); os parâmetros do catálogo na freguesia são só de referência nacional.

## `gold_rent_by_municipality_typology` — grão `dico` × `typology` (6 por município)

`dico, typology, n_listings, n_outliers, n_eligible, rent_median, rent_p25, rent_p75, n_eur_m2, eur_m2_median,
sample_status, rent_coverage, snapshot_month, source_id, license_id, attribution, processed_at_utc`.

## `gold_rent_by_parish_typology` — grão `dicofre` × `typology` (P3)

As mesmas colunas, mais `dicofre` (FK `dim_parish`).

## `gold_municipality_climate_monthly` — grão `dico` × `year_month`

`dico, year_month, valid_days, temp_mean, temp_max_mean, temp_min_mean, precip_total, sun_hours_mean, wind_mean,
humidity_mean, hot_days, cold_days, rain_days, snow_days, extreme_days, extreme_days_pct, cid, cia, p_index,
s_index, w_index, tci, window_start, window_end, source_id, license_id, attribution, usage_restriction,
processed_at_utc`.

## `gold_criteria_catalog` — grão `criterion_id`

| Coluna | Tipo | Nota |
| --- | --- | --- |
| catalog_version | varchar | `contracts/criteria-catalog.md` §2 |
| schema_version | integer | do YAML |
| criterion_id, category, category_label_pt, category_label_en | varchar | |
| label_pt, label_en, unit, direction, methodology_pt | varchar | |
| levels, modes, options | varchar | JSON (lista; `options` nulo quando não há) |
| default_range_min, default_range_max | double | nulos = aberto |
| weight | double | |
| status, pending_reason | varchar | |
| source_ids, dataset_ids, license_ids, attributions, usage_restrictions | varchar | distintos dos indicadores, unidos por `" | "`; nulos nos pendentes |
| reference_periods | varchar | períodos distintos usados (JSON, ordem crescente) |
| processed_at_utc | varchar | |

## `gold_criteria_normalization` — grão `criterion_id` × `level` × `variant`

`catalog_version, criterion_id, level, variant, n (bigint), min, p5, p95, max (double), is_degenerate (boolean)`.

## `gold_data_quality` — grão `criterion_id` × `level` × `variant` (P2)

Uma linha por critério do catálogo × nível declarado × variante (os pendentes com `variant = ""`).

| Coluna | Nota |
| --- | --- |
| catalog_version, criterion_id, level, variant, status | |
| territories_expected | 308 (município) ou 3 259 (freguesia); 0 nos pendentes |
| with_value | linhas com valor (na freguesia: só `proprio`) |
| missing | `territories_expected - with_value` (na freguesia inclui as herdadas) |
| zero_by_convention | linhas com `zero_convencao_fonte` |
| older_period | linhas com `is_older_period` |
| inherited | freguesia: linhas `herdado`; município: 0 |
| stale | linhas com `is_stale` |
| outliers | aluguel: soma de `n_outliers` da variante; 0 nos demais |
| dataset_latest_period | máximo de `dataset_latest_period` |
| pending_reason | dos pendentes ("fonte pendente: …") |
