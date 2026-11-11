# Modelo de dados — Pordata e INE

## Catálogo (`config/sources.yml`)

Cada fonte ganha a lista `datasets`. A CAOP não muda (sem `datasets`, usa as `urls` por região). Campos comuns a uma fonte: `id`, `publisher`, `responsible_party`, `license_id`, `attribution`, `collection_method`, `frequency`, `territorial_level`.

```yaml
sources:
  pordata:
    id: pordata
    publisher: PORDATA (Fundação Francisco Manuel dos Santos)
    responsible_party: living-recommender
    license_id: not_granted_by_source        # R-001: risco aceito pelo autor
    attribution: "Fonte: PORDATA"
    collection_method: http_download         # padrão dos datasets; o manual declara o seu
    frequency: monthly
    territorial_level: municipality
    # Padrões da fonte, herdados por cada dataset que não os redefina (catalog.DATASET_DEFAULTS).
    name_column: "Nome Região (Portugal)"
    expected_labels: [Ano, "Nome Região (Portugal)", "Âmbito Geográfico", Escala, Símbolo, Valor]
    datasets:
      - {id: farmacias, pordata_table: 464, origin: "https://ffmspstdlspub01.blob.core.windows.net/data/Modelo_20/464.csv"}
      # … demais 15 CSV (tabelas 1, 4, 295, 354, 375, 379, 439, 470, 559, 560, 581, 623, 631, 978, 980)
      - id: poder_compra_per_capita_xlsx
        collection_method: manual_upload
        format: xlsx
  ine:
    id: ine
    publisher: Instituto Nacional de Estatística, IP – Portugal
    responsible_party: living-recommender
    license_id: CC-BY-4.0
    attribution: "Instituto Nacional de Estatística, IP – Portugal"
    collection_method: api_json
    frequency: monthly
    territorial_level: municipality
    datasets:
      - id: rendas_novos_contratos
        indicator: "0014698"
        params: {Dim1: T, Dim2: "lvl@5"}
      - id: taxa_criminalidade
        indicator: "0008074"
        params: {Dim1: T, Dim2: "lvl@5", Dim3: "T,1,2,3,4,5,6"}
      - id: poder_compra_per_capita
        indicator: "0014580"
        params: {Dim1: T, Dim2: "lvl@5"}
```

`dataset.id` é único dentro da fonte; o identificador completo é `<source_id>/<dataset.id>` (ex.: `pordata/farmacias`). Os `expected_labels` são rótulos sem o prefixo numérico.

## Manifest v2 (`manifests/<source_id>/<run_id>.json`)

Não substitui o v1 da CAOP (`schema_version: 1`, `files[]`). O v2 é por dataset:

```json
{
  "schema_version": 2,
  "source_id": "pordata",
  "run_id": "20261111T170000000000Z-ab12cd34",
  "collected_at_utc": "2026-11-11T17:00:00Z",
  "status": "partial",
  "license_id": "not_granted_by_source",
  "collection_method": "http_download",
  "datasets": [
    {"dataset_id": "farmacias", "origin": "https://…/464.csv", "collection_method": "http_download", "status": "changed",
     "key": "raw/source=pordata/dataset=farmacias/run_id=<run_id>/farmacias.csv",
     "sha256": "…", "bytes": 327571, "fingerprint": "…",
     "reference_period": null, "source_release_date": null,
     "http": {"etag": "0x8DE0…", "last_modified": "Mon, 20 Oct 2025 14:05:28 GMT"},
     "error": null, "previous_changed_run_id": null},
    {"dataset_id": "hospitais", "origin": "…", "status": "failed", "key": null,
     "sha256": null, "bytes": null, "fingerprint": null, "error": "validação: coluna ausente: Valor"}
  ]
}
```

- `status` da execução: `changed` (≥ 1 `changed`, nenhum `failed`), `unchanged` (todos `unchanged`), `partial` (≥ 1 `failed` e ≥ 1 sucesso) ou `failed` (todos `failed`).
- `status` do dataset: `changed`, `unchanged` ou `failed`. Em `unchanged`, `key` e `sha256` apontam para o bruto do último `changed` (como na CAOP, o `unchanged` não grava arquivo) e `previous_changed_run_id` o identifica.
- `fingerprint`: chave de comparação. Nos CSV e na planilha é o `sha256` dos bytes; no INE é o `sha256` do JSON canônico sem `DataExtracao` (ver `logic/ingestao-datasets.md`).
- `http` só existe nos downloads por HTTP e é informativo (auditoria; não decide `unchanged` no v1).
- `collection_method` é **por dataset** (o do dataset, herdado da fonte quando não o redefine). O `collection_method` da execução é o método comum a todas as entradas ou `mixed`; assim a carga manual do Pordata grava `manual_upload`, e não o `http_download` da fonte. Manifests anteriores, sem o campo na entrada, valem o método da execução.
- `reference_period` e `source_release_date`: no INE, `UltimoPref` e `DataUltimoAtualizacao`; no Pordata, nulos (o CSV não informa).

**Estado vigente de um dataset** = a entrada `changed` mais recente (por `collected_at_utc`, depois `run_id`) daquele `dataset_id` em qualquer manifest da fonte, mesmo que esse manifest seja `partial`. Uma entrada `failed` nunca é estado.

## Layout do bruto

`raw/source=<source_id>/dataset=<dataset_id>/run_id=<run_id>/<arquivo>`, em que `<arquivo>` é `<dataset_id>.<csv|json|xlsx>`. Sem sobrescrita. O arquivo guarda os bytes exatamente como vieram (o JSON do INE com `DataExtracao`; a planilha como o operador a entregou).

## Staging — `lake/bronze/stg_observation/data.parquet` (Parquet único, com `source_id` e `dataset_id` como colunas)

Uma linha por observação municipal. Chave: `(dataset_id, dico, period, filter_1, filter_2, filter_3)`.

| Coluna | Tipo | Descrição |
|---|---|---|
| `source_id`, `dataset_id` | texto | `pordata`/`ine` e o id do dataset |
| `dico` | texto (4) | município resolvido; nunca nulo no resultado final |
| `source_name` | texto | nome ou código como veio da fonte, para auditoria |
| `period` | inteiro | ano (Pordata: coluna `Ano`; INE: período anual/bienal; planilha: ano da coluna) |
| `filter_1`, `filter_2`, `filter_3` | texto | dimensões do dataset (INE criminalidade: `filter_1` = categoria de crime) |
| `value` | double, nulo | valor numérico; **nulo quando a fonte não informa** (nunca 0) |
| `symbol` | texto, nulo | símbolo da fonte (`r`, `x`, `-`, `...`, `Pro`, `Quebra de série`, `sinal_conv`) |
| `unit` | texto | unidade sem espaços nas pontas |
| `source_run_id` | texto | execução do bruto de origem |
| `license_id`, `attribution` | texto | do catálogo |
| `collected_at_utc`, `processed_at_utc` | texto | coleta e processamento, separados |

## Cobertura — `lake/bronze/rpt_observation_coverage/`

Uma linha por dataset: `source_id`, `dataset_id`, `latest_period`, `latest_period_with_data`, `municipalities_expected` (308), `municipalities_with_value`, `municipalities_without_value`, `missing_dico` (lista), `aggregate_rows_excluded`. Definição: um município **tem valor** no período mais recente (`latest_period`, o maior `period` do dataset) se tiver pelo menos uma observação com `value` não nulo naquele período. `latest_period_with_data` é o último período com pelo menos um valor não nulo em qualquer município; difere de `latest_period` quando o período mais recente está vazio (na coleta real de 2026-11-11, `ensino_nao_superior` tem `latest_period` 2024, com 0 de 308 municípios, e `latest_period_with_data` 2023) e é nulo se o dataset não tiver nenhum valor. A cobertura por combinação de filtros fica para a camada Gold.

## Seed — `analytics/dbt/seeds/municipality_synonyms.csv`

`source_name` (grafia exata da fonte), `dico`, `reason`. 5 linhas iniciais (R4 do `research.md`). Só municípios; a regra do nome normalizado é a de `pipelines/collectors/caop/names.py`.

## Integridade

Todo `dico` existe em `lake/silver/dim_municipality`; chave única; `period`, `unit` e `dataset_id` não nulos; `value` e `symbol` coerentes (valor nulo implica símbolo ou ausência registrada); nome sem correspondência reprova. Falha de qualquer teste impede a promoção.
