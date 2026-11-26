# Data Model: spec 012

Todas as tabelas ficam em `lake/gold/<tabela>/data.parquet`, com `catalog_version` e `processed_at_utc`.

## Tabelas novas

### `gold_rent_by_district_typology`

Chave: `district_or_island` × `typology`. Só distritos (ou ilhas) com anúncios no snapshot vigente, 6 linhas cada.
Arquivo preparado: `rent_district.parquet`.

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `district_or_island` | varchar | Nome do CAOP (`dim_municipality.district_or_island`). Não nulo. |
| `source_region` | varchar | Região da fonte do distrito; igual nas 6 linhas. |
| `typology` | varchar | `ALL`, `T0`, `T1`, `T2`, `T3`, `T4+`. |
| `n_listings`, `n_outliers`, `n_eligible`, `n_eur_m2` | bigint | Como na tabela municipal; outliers do grupo da área. |
| `rent_median`, `rent_p25`, `rent_p75` | double | Só com `n_eligible` ≥ 10. |
| `eur_m2_median` | double | Só com `n_eur_m2` ≥ 10. |
| `sample_status` | varchar | `suficiente`, `amostra_insuficiente`, `sem_anuncios`. |
| `snapshot_month`, `source_id`, `license_id`, `attribution` | varchar | Proveniência (FR-006). |

### `gold_rent_by_region_typology`

Chave: `source_region` × `typology`. Mesmas colunas, sem `district_or_island`. Arquivo preparado:
`rent_region.parquet`.

`source_region` aceita: `Norte`, `Centro`, `Área Metropolitana de Lisboa`, `Algarve`, `Alentejo`, `Madeira`,
`Açores`. É a região do Idealista, **não** a NUTS II.

## Tabelas alteradas (colunas acrescentadas)

| Tabela | Coluna nova | Tipo | Valores |
| --- | --- | --- | --- |
| `gold_municipality_indicator` | `origin` | varchar, não nulo | `proprio`, `herdado`, `ausente` |
| | `origin_level` | varchar | `municipio` (próprio), `distrito`, `regiao`; nulo se ausente |
| `gold_parish_indicator` | `origin_level` | varchar | `freguesia` (próprio), `municipio`, `distrito`, `regiao`; nulo se ausente |
| `gold_rent_by_municipality_typology` | `district_or_island` | varchar | do CAOP |
| | `source_region` | varchar | nula se desconhecida (R-001) |
| | `reference_level` | varchar | nível de `rent_median` publicado: `municipio`, `distrito`, `regiao`, nulo |
| | `reference_level_eur_m2` | varchar | o mesmo para `eur_m2_median` |
| `gold_data_quality` | `inherited_municipio`, `inherited_distrito`, `inherited_regiao` | bigint, não nulo | somam `inherited` |

## Colunas com sentido alterado

| Tabela.coluna | Antes (011) | Depois |
| --- | --- | --- |
| `gold_data_quality.with_value` | município: todos os valores; freguesia: próprios | próprios nos dois níveis |
| `gold_data_quality.inherited` | 0 no município | herdados nos dois níveis |
| `gold_parish_indicator.origin = herdado` | cópia do município | cópia do município, que pode ser herdado da área (ver `origin_level`) |
| `gold_municipality_indicator.value` (aluguel) | só próprio | próprio ou herdado (ver `origin`) |
| `gold_criteria_normalization` (município) | todos os valores | só próprios (mesmos números de hoje) |

`territorial_inheritance` **não muda**: continua só com o `coverage_status` dos Censos (R-009).

`rent_coverage` **não muda**: fala só da amostra do próprio território.

## Hierarquia territorial (em memória)

`dico` → `district_or_island` → `source_region`, única por município. Não é gravada como tabela própria; as colunas
saem na tabela municipal de aluguel.
