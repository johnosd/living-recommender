# Modelo de dados: Ingestão de clima Open-Meteo

## 1. Catálogo: `open_meteo` em `config/sources.yml` (T001)

```yaml
  open_meteo:
    id: open_meteo
    publisher: Open-Meteo.com
    responsible_party: living-recommender
    # R-001 (plan 003): o plano gratuito é só para uso não comercial; o autor aceitou o risco (como no Pordata).
    license_id: CC-BY-4.0
    usage_restriction: "plano gratuito: uso não comercial (risco aceito R-001)"
    attribution: "Dados meteorológicos: Open-Meteo.com (CC BY 4.0); reanálise ERA5, Copernicus Climate Change Service/ECMWF"
    collection_method: api_json
    frequency: quarterly
    territorial_level: municipality
    api_url: https://archive-api.open-meteo.com/v1/archive
    model: era5                         # R1: o único modelo com as 13 variáveis completas e reprodutível
    timezone: auto                      # R2: o dia é o dia local do município
    window: {start: "2024-11-01", end: "2026-10-31"}   # 24 meses completos; 730 dias
    expected_municipalities: 308
    point_divergence_km: 25             # R6
    limits: {per_minute: 600, per_hour: 5000, per_day: 10000, min_interval_seconds: 7}
    variables:
      - {id: temperature_2m_mean, unit: "°C"}
      - {id: temperature_2m_max, unit: "°C"}
      - {id: temperature_2m_min, unit: "°C"}
      - {id: apparent_temperature_mean, unit: "°C"}
      - {id: apparent_temperature_max, unit: "°C"}
      - {id: apparent_temperature_min, unit: "°C"}
      - {id: precipitation_sum, unit: "mm"}
      - {id: snowfall_sum, unit: "cm"}
      - {id: sunshine_duration, unit: "s"}
      - {id: wind_speed_10m_mean, unit: "km/h"}
      - {id: wind_speed_10m_max, unit: "km/h"}
      - {id: wind_gusts_10m_max, unit: "km/h"}
      - {id: relative_humidity_2m_mean, unit: "%"}
```

Regras de `validate_climate_source` (T002), antes de qualquer rede:

| Campo | Regra |
| --- | --- |
| `license_id`, `collection_method`, `api_url`, `model`, `window`, `variables`, `expected_municipalities` | obrigatórios (`strict_metadata=False`); com `strict_metadata=True` (usado por `load_catalog`) exigem-se também `publisher`, `responsible_party`, `frequency`, `territorial_level`, `attribution`, `limits` e `point_divergence_km` |
| `collection_method` | `api_json` |
| `api_url` | HTTPS com host |
| `window.start`, `window.end` | datas ISO, `start <= end`; o número de dias é derivado (730 na janela inicial) |
| `variables` | lista não vazia de `{id, unit}` com `id` único; os ids são os nomes da API |
| `expected_municipalities` | inteiro positivo |
| `limits.*`, `point_divergence_km` | números positivos, quando presentes |

`load_catalog` ganha um terceiro ramo: uma fonte com a chave `window` é validada por `validate_climate_source`; as fontes com `datasets` e a CAOP continuam como estão.

## 2. Unidade de coleta (em memória)

O handler recebe a dimensão da spec 001 e monta um **item** por município, no formato que `collect_items` espera de um "dataset":

```python
{"id": "0106",                  # dico: vira dataset_id no manifest e dataset=<dico> na chave raw
 "name": "Lisboa",              # official_name, só para mensagens
 "latitude": 38.72, "longitude": -9.14,   # representative_lat/lon (spec 001)
 "collection_method": "api_json",
 "origin": "<api_url>",         # só descrição; a URL completa é montada pelo fetcher
 "window": {...}, "variables": [...], "model": "era5"}   # copiados da fonte para o validador e o fetcher
```

A lista vem de `dim_municipality` (`dico`, `official_name`, `representative_lat`, `representative_lon`) em `<silver>/dim_municipality/data.parquet`. O handler recusa a execução, antes de qualquer rede, se faltar a dimensão, se o total for diferente de `expected_municipalities`, se `dico` repetir ou se alguma coordenada estiver ausente ou fora de Portugal (latitude 29–43, longitude −32 a −6).

## 3. Raw e manifest (reuso do manifest v2 da spec 002)

Chave raw (mesmo layout da spec 002, `dataset` = município):

```text
raw/source=open_meteo/dataset=<dico>/run_id=<run_id>/<dico>.json
manifests/open_meteo/<run_id>.json
```

Entrada do manifest para um município (campos novos em **negrito**):

| Campo | Valor |
| --- | --- |
| `dataset_id` | `dico` |
| `status` | `changed`, `unchanged`, `failed` ou **`pending`** |
| `key`, `sha256`, `bytes`, `fingerprint` | como na spec 002; `fingerprint` é a impressão digital sem `generationtime_ms` (R5) |
| `reference_period` | `"2024-11-01/2026-10-31"` (a janela) |
| **`model`** | `"era5"` |
| **`requested_lat`**, **`requested_lon`** | coordenadas do ponto representativo (as pedidas) |
| **`returned_lat`**, **`returned_lon`** | coordenadas devolvidas pela fonte (a célula da grade) |
| **`elevation_m`**, **`timezone`** | `elevation` e `timezone` da resposta |
| `error` | motivo, em `failed` e em `pending` (por exemplo `cota diária esgotada`) |

Uma entrada `pending` traz só `dataset_id`, `status`, `error` e os campos nulos padrão; nunca `key`. O status da execução (`run_status`) passa a ser `failed` se **todas** falharam; `partial` se alguma falhou ou ficou `pending`; senão `changed` (se alguma mudou) ou `unchanged`.

O estado vigente de um município é a entrada `changed` mais recente (`latest_dataset_states`, inalterado). Ele é **atual** se `reference_period` for igual à janela do catálogo **e** `model` for igual ao do catálogo; senão o município conta como pendente de trabalho (janela ou modelo novo).

## 4. Staging: `climate_daily.parquet` (preparado em Python, T025; os pontos, T029)

Entrada do dbt. Uma linha por município, variável e dia:

| Coluna | Tipo | Origem |
| --- | --- | --- |
| `source_id` | texto | `open_meteo` |
| `dico` | texto (4 dígitos) | `dataset_id` do estado vigente |
| `variable` | texto | nome da variável da API |
| `date` | data | `daily.time`, o dia local; sem conversão de fuso |
| `value` | double, nulo permitido | `daily.<variável>`; `null` da fonte → nulo, nunca 0 |
| `unit` | texto | `daily_units.<variável>`, sem conversão |
| `model` | texto | `model` da entrada |
| `window_start`, `window_end` | data | `reference_period` da entrada |
| `source_run_id` | texto | `run_id` do estado |
| `license_id`, `attribution` | texto | catálogo |
| `collected_at_utc`, `processed_at_utc` | texto | estado / hora do build |

Chave: (`dico`, `variable`, `date`). Volume: 308 × 13 × 730 = **2.922.920 linhas**. A escrita é em fluxo (um grupo de linhas por município) para não manter tudo em memória.

Arquivos auxiliares do mesmo diretório `prepared/`:

- `climate_points.parquet` (T029): uma linha por município **coletado**: `dico`, `requested_lat/lon`, `returned_lat/lon`, `elevation_m`, `timezone`, `distance_km` (haversine entre pedido e devolvido), `diverged` (`distance_km > point_divergence_km`), `threshold_km`, `source_run_id`.
- `climate_meta.parquet`: uma linha por variável do catálogo: `variable`, `unit`, `window_start`, `window_end`, `expected_days`, `model`.

## 5. Bronze (dbt, tag `climate`): `lake/bronze/`

| Modelo | Conteúdo |
| --- | --- |
| `stg_climate_daily` | as colunas da §4, com tipos fixados (`date`, `double`, `varchar`) |
| `rpt_climate_coverage` | por variável (inclusive as sem nenhum dado): `variable`, `unit`, `window_start`, `window_end`, `expected_days`, `municipalities_expected` (da dimensão), `municipalities_collected`, `municipalities_complete` (dias com valor = `expected_days`), `municipalities_with_gaps`, `municipalities_not_collected`, `missing_days_total`, `gaps` (lista de `{dico, missing_days}`), `not_collected_dico` (lista) |
| `rpt_climate_points` | por município da dimensão: `dico`, `collected`, pedido e devolvido, `elevation_m`, `distance_km`, `diverged` |

Testes dbt (T021, T023): `not_null` em `dico`, `variable`, `date`, `unit`, `model`, `source_run_id`, `license_id`; `relationships` de `dico` com `dim_municipality`; singulares: chave (`dico`, `variable`, `date`) única; **dias por (município, variável) iguais a `expected_days`**; faixas físicas (umidade 0–100, precipitação e neve ≥ 0, sol 0–86.400 s, ventos e rajada ≥ 0, temperaturas entre −60 e 60 °C, sensação térmica entre −80 e 70 °C); temperatura mínima ≤ máxima no mesmo dia; `value` nulo só existe se for nulo no bruto (provado em Python, T026). Uma falha interrompe o build e **não promove** nada.

## 6. Lake e promoção

```text
.data/
  raw/source=open_meteo/dataset=<dico>/run_id=<run>/<dico>.json
  manifests/open_meteo/<run>.json
  lake/silver/dim_municipality/data.parquet            # spec 001, entrada (somente leitura)
  lake/bronze/stg_climate_daily/data.parquet           # promovido por caminho (D7)
  lake/bronze/rpt_climate_coverage/data.parquet
  lake/bronze/rpt_climate_points/data.parquet
  lake/bronze/climate_coverage.csv                     # legível por pessoa (`;`, utf-8-sig)
  lake/bronze/climate_points.csv
```

A promoção usa `promote_paths` (spec 002) com os três caminhos de `lake/bronze/`. Nenhum deles toca `stg_observation`, `rpt_observation_coverage`, nem a Silver da CAOP.
