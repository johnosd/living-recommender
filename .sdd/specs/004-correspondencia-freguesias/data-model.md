# Data Model: Correspondência de freguesias 2013→2025

## 1. Catálogo (`config/sources.yml`, T001)

```yaml
  ine_parish_crosswalk:
    id: ine_parish_crosswalk
    publisher: Instituto Nacional de Estatística, IP – Portugal
    responsible_party: living-recommender
    license_id: CC-BY-4.0        # licença geral do INE aplicada às planilhas (R-002, T028): sem aviso específico para elas
    attribution: "Instituto Nacional de Estatística, IP – Portugal"
    collection_method: http_download
    frequency: on_demand
    territorial_level: parish
    datasets:
      - id: reorganizacao_2013
        role: pre2013_to_2013
        origin: https://smi.ine.pt/Versao/Download/9160
        format: xlsx
        sheet: "Correspondências 2013"
        columns:
          pre_code: "Código"
          pre_name: "Freguesias antes da Reorganização"
          name: "Freguesias - Reorganização de 2013"
          code: "Código Novo"
      - id: reposicao_2025
        role: pre2013_to_2025
        origin: https://smi.ine.pt/Versao/Download/10698
        format: xlsx
        sheet: "Sheet1"
        columns:
          pre_code: "Código - Freguesias antes da reorganização administrativa de 2013"
          pre_name: "Designação - Freguesias antes da reorganização administrativa de 2013"
          municipality_name: "Designação - Município"
          code: "Código - Freguesias repostas em 2025"
          name: "Designação - Freguesias repostas em 2025"
```

`load_catalog` valida a fonte por `get_dataset_source` (tem `datasets`), que já aceita `format`, `sheet`, `role` e `columns` como chaves livres do dataset. Os rótulos são comparados normalizados (research R3), então a grafia com dois espaços da tabela B não precisa ser copiada.

## 2. Bruto e manifest (inalterados)

`raw/source=ine_parish_crosswalk/dataset=<id>/run_id=<run>/<id>.xlsx` e `manifests/ine_parish_crosswalk/<run_id>.json`, manifest v2 de `collect_datasets` (`dataset_id`, `origin`, `status`, `key`, `sha256`, `bytes`, `http`, `error`, `previous_changed_run_id`). A impressão digital é o `sha256` dos bytes (sem `fingerprint` customizado: a planilha não traz horário de extração).

## 3. Tabelas normalizadas (saída de `read_crosswalk_table`, em memória)

| Papel | Coluna | Tipo | Observação |
| --- | --- | --- | --- |
| A | `pre_code` | texto(6) | `[0-9A-Z]{6}` |
| A | `pre_name` | texto | sem espaços nas pontas, espaços internos colapsados |
| A | `name_2013` | texto | designação em 2013 |
| A | `code_2013` | texto(6) | |
| A | `partial_origin` | bool | `pre_name` termina em `(parte)` |
| B | `pre_code`, `pre_name` | idem | |
| B | `municipality_name` | texto | só para auditoria |
| B | `code_2025` | texto(6) | |
| B | `name_2025` | texto | |

Estatísticas: `rows_read` (linhas com algum conteúdo), `ignored_rows` (legendas), `numeric_codes_normalized`, `partial_rows`.

## 4. Correspondência (`xwalk_parish_2013_2025`, uma linha por par)

| Coluna | Tipo | Regra |
| --- | --- | --- |
| `dicofre_2013` | varchar(6) | chave do par; código da divisão de 2013 |
| `name_2013` | varchar | designação em 2013 (tabela A) |
| `dicofre_2025` | varchar(6) | chave do par; `dicofre` da `dim_parish` |
| `name_2025` | varchar | tabela B; se a freguesia não foi reposta, a designação de 2013 |
| `relation` | varchar | `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many` |
| `inherited` | boolean | `destinos(dicofre_2013) > 1`: o valor de 2013 só pode ser herdado |
| `partial_origin` | boolean | alguma linha de evidência é "(parte)" |
| `name_changed` | boolean | designações normalizadas diferentes (casefold, NFC, espaços colapsados) |
| `municipality_changed` | boolean | 4 primeiros caracteres diferentes |
| `pre2013_codes` | varchar[] | códigos pré-2013 que sustentam o par, distintos e ordenados |
| `source_run_id_2013`, `source_run_id_2025` | varchar | `run_id` do estado vigente de cada tabela |
| `sha256_2013`, `sha256_2025` | varchar | checksums dos brutos usados |
| `license_id`, `attribution` | varchar | do catálogo |
| `collected_at_utc` | varchar | o mais recente entre as duas tabelas |
| `processed_at_utc` | varchar | |

Chave: (`dicofre_2013`, `dicofre_2025`) única. Ordenação: por `dicofre_2013`, depois `dicofre_2025`.

## 5. Relatório (`rpt_parish_crosswalk_coverage`)

Uma linha por `relation` mais uma linha `all`:

| Coluna | Significado |
| --- | --- |
| `relation` | natureza ou `all` |
| `pairs` | pares na categoria |
| `codes_2013`, `codes_2025` | códigos distintos de cada geração |
| `inherited_pairs`, `partial_origin_pairs`, `name_changed_pairs`, `municipality_changed_pairs` | contagens dos sinais |
| `parishes_expected`, `parishes_with_origin` | `dim_parish` esperada e coberta (só na linha `all`) |
| `source_rows_read`, `source_ignored_rows`, `source_numeric_codes_normalized`, `source_partial_rows` | estatísticas das duas planilhas somadas (só na linha `all`): linhas com conteúdo, legendas ignoradas, células numéricas normalizadas e linhas com o marcador "(parte)" (R-006) |
| `caop_version`, `collected_at_utc` | da `dim_parish` e das tabelas (só na linha `all`; no CSV do relatório, repetidos em todas as linhas) |
| `attribution` | atribuição da fonte (FR-019), em todas as linhas |

As quatro naturezas aparecem sempre, mesmo com zero pares. As estatísticas vêm de `prepared/table_stats.parquet`, gravado por `prepare_crosswalk` (uma linha por tabela: `dataset_id, rows_read, ignored_rows, numeric_codes_normalized, partial_rows`).

**CSV do relatório** `lake/silver/parish_crosswalk_report.csv` (`;`, `utf-8-sig`, FR-013 e US3/AC5): o `rpt_parish_crosswalk_coverage` em formato legível por pessoa, com `caop_version`, `collected_at_utc` e `attribution` repetidos em **todas** as linhas e as contagens como inteiros. É promovido e preservado junto das tabelas, e uma falha de cobertura ou do dbt o deixa intacto.

CSV de revisão `lake/silver/parish_crosswalk_review.csv` (`;`, `utf-8-sig`): os pares com `relation <> 'one_to_one'` ou com algum sinal verdadeiro, com códigos e designações das duas gerações e `pre2013_codes` unidos por `;`.

## 6. Regras de integridade

- `dicofre_2025` ∈ `dim_parish.dicofre` (dbt `relationships` + `verify_coverage`).
- Toda freguesia da `dim_parish` aparece como `dicofre_2025` (teste singular + `verify_coverage`).
- Todo código de 2013 da tabela A aparece como `dicofre_2013` (`verify_coverage`).
- `relation` é consistente com as contagens por par (teste singular).
- Ausente nunca é preenchido: sem destino, sem linha e o build reprova.
