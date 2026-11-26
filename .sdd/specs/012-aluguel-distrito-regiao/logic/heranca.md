# Lógica: áreas, estatísticas e herança (spec 012)

Módulo: `pipelines/gold/areas.py`. Reusa as regras de amostra de `pipelines/gold/rent.py`. Nenhuma regra em SQL
(D2 da 011).

## 1. Anúncios usados

Os mesmos da 011: `rent._current(listings)` (o `snapshot_month` mais recente, com `asking_rent_eur` não nulo).

**Descarte a coluna `outlier` que `_current` devolve.** Ela é do grupo município × tipologia. No distrito e na
região, a marca é **recalculada** no grupo da área (FR-004). Para isso, generalize `rent._outliers(listings,
key="dico")` e chame com `key="district_or_island"` e `key="source_region"`. O comportamento com o padrão não pode
mudar (contrato da 011).

## 2. Onde cada anúncio cai

Para cada anúncio:

| Campo | Regra |
| --- | --- |
| distrito | com `dico`: `district_or_island` do município na CAOP (o `source_subregion` é ignorado, por exemplo `Horta` → Ilha do Faial) |
| | sem `dico`: `source_subregion`, traduzido pela seed de ilhas; sem tradução, o próprio nome |
| | sem `dico` e sem `source_subregion`: nulo (conta só na região) |
| região | `source_region`; se vazia, a da região autónoma do distrito (`rent.REGIONS`); senão, nula |

Texto vazio ou só com espaços vale como nulo (o formato antigo grava `source_region = ""`).

Falham com `AreaError`, citando o nome:

- nome de distrito (depois da seed) que não existe em `dim_municipality.district_or_island`;
- `dico` do anúncio que não existe em `dim_municipality` (senão o anúncio sumiria sem aviso).

**Seed** `analytics/dbt/seeds/idealista_island_aliases.csv` (UTF-8, lida com
`pipelines.collectors.idealista.territory.read_seed`), com as colunas `source_subregion,district_or_island`:

```csv
source_subregion,district_or_island
Madeira (Ilha),Ilha da Madeira
Porto Santo (Ilha),Ilha de Porto Santo
São Miguel (Ilha dos Açores),Ilha de São Miguel
Terceira (Ilha dos Açores),Ilha Terceira
Flores (Ilha dos Açores),Ilha das Flores
Pico (Ilha dos Açores),Ilha do Pico
```

Só entram nomes já vistos na fonte. Não adivinhe a grafia das ilhas que faltam (R-002).

## 3. Hierarquia (`territory_hierarchy`)

Para cada distrito, junte o conjunto de regiões: as dos anúncios do distrito (§2) mais a da região autónoma, nas
ilhas.

- Mais de uma região: `AreaError` com o nome do distrito (FR-005).
- Nenhuma (distrito do continente sem anúncio no snapshot): `source_region` nula. Não adivinhe (R-001).

Saída: uma linha por município, com `dico`, `district_or_island` e `source_region`.

## 4. Estatísticas por área

`district_rent_stats` e `region_rent_stats` devolvem as colunas de `data-model.md`. Para cada território **com
anúncios**, são as 6 linhas de `rent._territory_rows` (ou equivalente), com a proveniência de `rent._provenance`.

- Distrito: a coluna `source_region` vem da hierarquia (§3), igual nas 6 linhas.
- As duas funções validam como no §2 e no §3 (o contrato chama `district_rent_stats` com um distrito desconhecido).
- Sem anúncios no snapshot, devolva um DataFrame vazio **com as colunas** (o dbt faz `cast` delas).
- Aplique os tipos de `rent._frame` (float nas medidas, int nas contagens).
- Nenhuma coluna por anúncio (`listing_id`, `dico`, `dicofre`) sai.

## 5. Referência por município e variante

Uma única função interna resolve a cadeia, usada pelo §6 e pelo §7:

```text
referencia(dico, tipologia, medida):          # medida = rent_median | eur_m2_median
  se a Gold municipal tem a medida:           -> ("municipio", linha municipal)
  d = hierarquia[dico].district_or_island
  se district_stats[d, tipologia][medida]:    -> ("distrito", linha)
  r = hierarquia[dico].source_region
  se r não é nulo e region_stats[r, tipologia][medida]:  -> ("regiao", linha)
  senão:                                      -> (nulo, nada)
```

Cada variante e cada medida decidem sozinhas (FR-009). Não herde "o município inteiro" porque o `ALL` herdou.

## 6. `reference_levels` (tabela municipal de aluguel)

Devolve a tabela de `rent_stats` com 4 colunas a mais: `district_or_island`, `source_region`, `reference_level`
(medida `rent_median`) e `reference_level_eur_m2` (medida `eur_m2_median`).

Nenhuma coluna existente muda. Em especial, `rent_coverage`, `rent_median` e `n_eligible` continuam falando **só
do município** (FR-010).

## 7. `apply_rent_inheritance` (perfil municipal)

Entrada: o perfil municipal completo (todas as famílias). Saída: as mesmas linhas, na mesma ordem, em um
DataFrame novo (não altere a entrada), com `origin` e `origin_level`.

1. Todas as linhas: com valor, `proprio` / `municipio`; sem valor, `ausente` / nulo.
2. Linhas de critério com `compute.kind == "rent"` e sem valor: resolva a cadeia (§5, a partir do distrito) com a
   tipologia `variant` e a medida `rent.METRICS[compute["metric"]][0]`.
3. Se achar, `origin = herdado`, `origin_level` = `distrito` ou `regiao`, e copie da linha de origem:

| Coluna do indicador | Valor |
| --- | --- |
| `value` | a medida da linha de origem, sem arredondar (SC-003) |
| `period`, `dataset_latest_period` | `snapshot_month` |
| `source_id`, `license_id`, `attribution` | os da linha de origem |
| `dataset_id` | `idealista_listings` |
| `value_status` | `observado` |
| `missing_reason` | nulo |
| `is_older_period`, `is_stale` | falso |
| `usage_restriction` | **fica a da linha** (já preenchida por `rent_indicators`) |

4. Sem referência: a linha fica como estava, com o motivo próprio (`sem_anuncios`, `amostra_insuficiente` ou
   `regional_only`). Não crie código de motivo novo.

## 8. Freguesia (`parish.py`)

A base já é uma cópia do município; com o §7, o aluguel herdado de distrito ou região vem junto. Falta o nível:

| Caso | `origin` | `origin_level` |
| --- | --- | --- |
| valor próprio da freguesia | `proprio` | `freguesia` |
| copiado do município | `herdado` | o `origin_level` do município (`municipio`, `distrito` ou `regiao`) |
| sem valor | `ausente` | nulo |

Armadilhas:

- a base traz a coluna `origin` do município (`proprio`); ela **tem** de ser recalculada;
- se o perfil municipal não tiver `origin_level` (testes unitários da 011), o herdado é `municipio`;
- `_combine` monta linhas novas a partir de `base.columns`: defina `origin_level` nelas também.

## 9. Normalização (`criteria._values`)

Quando a tabela tem a coluna `origin`, use só `origin == "proprio"`, **em qualquer nível** (hoje só na freguesia).
Consequência: um critério sem nenhum valor próprio num nível falha o build, mesmo com herdados (R-004).

O teste `tests/unit/test_gold_parish.py::test_parish_normalization_ignores_inherited_values` monta um perfil
"municipal" a partir do de freguesia, levando junto a coluna `origin`, e passa a falhar. Ajuste **o teste**:
descarte `origin` e `origin_level` do perfil falso.

## 10. Qualidade (`quality.py`)

- `own` = linhas `origin == "proprio"` quando a coluna existe (nos dois níveis); sem a coluna, todas.
- `with_value`, `zero_by_convention`, `older_period` e `stale` contam só `own`; `missing = esperados − with_value`
  (inclui os herdados).
- `inherited` = linhas `herdado`; `inherited_municipio`, `inherited_distrito` e `inherited_regiao` pela
  `origin_level` (0 quando a coluna não existe).
