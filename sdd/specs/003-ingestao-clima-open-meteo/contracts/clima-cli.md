# Contrato das CLIs de clima

Duas CLIs, no padrão `collect_*`/`build_*` das specs 001 e 002.

## `collect_open_meteo` (T013, T018)

```powershell
uv run --locked python -m pipelines.cli.collect_open_meteo --local [--root .data] [--silver <dir>] [--catalog <yml>]
                                                           [--max-municipalities N] [--recollect] [--no-wait]
uv run --locked python -m pipelines.cli.collect_open_meteo --s3 --bucket <b> [--prefix <p>] [--silver <dir>] ...
```

| Opção | Efeito |
| --- | --- |
| `--local` / `--s3 --bucket --prefix` / `--root` / `--catalog` | iguais às CLIs da spec 002 (`add_destination_arguments`) |
| `--silver DIR` | onde ler `dim_municipality/data.parquet`; padrão `<root>/lake/silver`. Mesmo com `--s3`, a dimensão é lida de um diretório local (R-008) |
| `--max-municipalities N` | consulta no máximo N municípios pendentes nesta execução, em ordem de `dico`. Os demais ficam como estão e não entram no manifest. Serve para controlar o gasto de cota |
| `--recollect` | consulta de novo também os municípios que já têm estado atual, para confirmar `unchanged` ou detectar revisão da fonte (R-006). Gasta cota |
| `--no-wait` | trata um limite de minuto ou de hora como pausa (o município corrente e os seguintes ficam `pending`) em vez de esperar |

Sem rede e sem chave de API. O `User-Agent` é o do projeto (`living-recommender/0.1 …`); a taxa mínima é `limits.min_interval_seconds` do catálogo.

### Saída

```text
Open-Meteo: partial | run_id=20261111T120000000000Z-ab12cd34
  janela 2024-11-01/2026-10-31 | modelo era5 | 308 municípios
  gravados: 120 | inalterados: 0 | falhas: 0 | pendentes: 188 (cota diária esgotada)
  já atuais (sem chamada): 0 | restantes: 188
  falhas:
    0412: validação: temperature_2m_min ausente
  manifest: manifests/open_meteo/20261111T120000000000Z-ab12cd34.json
  Continue com o mesmo comando amanhã; a cota diária do Open-Meteo reinicia.
```

Sem municípios a coletar (todos atuais e sem `--recollect`): `Open-Meteo: nada a coletar (308/308 atuais)`, sem manifest e sem `run_id` consumido.

### Códigos de saída

| Código | Quando |
| --- | --- |
| `0` | execução `changed` ou `unchanged`, ou nada a coletar |
| `1` | algum município `failed`; ou erro antes de começar (catálogo, dimensão ausente ou diferente de 308, destino inacessível). Vence o `2` quando os dois ocorrem |
| `2` | **só** pendentes por cota, por `--no-wait` ou por interrupção do operador (Ctrl+C), sem nenhuma falha. É um estado esperado, não um erro de dado |

Ctrl+C: a coleta termina o município corrente, marca o restante como `pending` (`interrompida pelo operador`), grava o manifest e sai com `2`. Um encerramento forçado do processo não grava manifest: os brutos já escritos ficam órfãos (R-007) e a próxima execução os refaz.

## `build_climate` (T025, T030)

```powershell
uv run --locked python -m pipelines.cli.build_climate --local [--root .data]
```

Lê o estado vigente de cada município, confere `sha256` e tamanho do bruto, prepara `prepared/climate_daily.parquet`, `climate_points.parquet` e `climate_meta.parquet`, roda `dbt build --select tag:climate` em área isolada e **só então** promove os três modelos (`promote_paths`). Qualquer falha preserva o staging anterior.

| Situação | Resultado |
| --- | --- |
| Silver da CAOP ausente | falha: `execute python -m pipelines.cli.build_caop primeiro` |
| Nenhum município coletado | falha: `execute collect_open_meteo primeiro` |
| Alguns municípios sem estado atual | **sucesso** com os coletados; os ausentes aparecem em `not_collected_dico` e no CSV (staging parcial é válido, a ausência é o dado) |
| `sha256`/tamanho do bruto diferente do manifest | falha: `checksum ou tamanho alterado: <key>` |
| Teste dbt reprovado | falha, com as últimas linhas do dbt; nada é promovido |

Saída:

```text
Clima: 2.922.920 linhas de 308 municípios (13 variáveis, 2024-11-01/2026-10-31, era5)
  Bronze: .data/lake/bronze/stg_climate_daily
Cobertura (municípios com série completa, de 308):
  temperature_2m_mean        308/308  com lacuna: 0   não coletados: 0
  …
  Pontos divergentes (> 25 km): 0 | elevação 0 m: 3
  Detalhe: .data/lake/bronze/climate_coverage.csv e climate_points.csv
```

Código de saída: `0` em sucesso; `1` em qualquer falha.
