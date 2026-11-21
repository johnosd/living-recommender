# Contrato das CLIs: correspondência de freguesias

Duas CLIs, no padrão `collect_*` / `build_*` das specs 001 a 003. Nenhuma lê segredo; o modo `--s3` usa a cadeia padrão da AWS.

## `python -m pipelines.cli.collect_parish_crosswalk`

Baixa as duas planilhas do INE e grava o bruto imutável.

| Opção | Efeito |
| --- | --- |
| `--local` (padrão) / `--s3 --bucket B [--prefix P]` | destino; mesmas regras de `collect_pordata` |
| `--root DIR` | raiz local (padrão `.data`) |
| `--catalog FILE` | catálogo alternativo (padrão `config/sources.yml`) |

Saída (mesmo formato de `collect_pordata`, via `print_result`):

```text
Correspondência INE: changed | run_id=20261112T150000000000Z-1a2b3c4d
  reorganizacao_2013: changed (205543 bytes)
  reposicao_2025: unchanged
  manifest: manifests/ine_parish_crosswalk/20261112T150000000000Z-1a2b3c4d.json
```

| Código | Quando |
| --- | --- |
| 0 | `changed` ou `unchanged` nas duas tabelas |
| 1 | alguma tabela `failed` (`partial`/`failed`), catálogo inválido ou destino inacessível |

Uma tabela que falha nunca bloqueia a outra e nunca vira estado vigente. Downloader: `User-Agent` identificado, 1 requisição por segundo, retentativas com backoff, `xlsx_content_check` (recusa HTML e arquivo que não começa como ZIP).

## `python -m pipelines.cli.build_parish_crosswalk`

Deriva a correspondência, verifica a cobertura, testa no dbt e promove.

| Opção | Efeito |
| --- | --- |
| `--local` | destino local (único nesta fase) |
| `--root DIR` | raiz local (padrão `.data`) |

Pré-requisitos: `build_caop` já rodou (`lake/silver/dim_parish`) e as duas tabelas têm estado vigente válido.

Saída em caso de sucesso:

```text
Correspondência: 3260 pares (3092 códigos de 2013 para 3259 de 2025)
  one_to_one: 2957 | one_to_many: 301 | many_to_one: 0 | many_to_many: 2
  herdado: 303 | origem parcial: 8 | nome alterado: 297 | município alterado: 0
  Silver: .data/lake/silver/xwalk_parish_2013_2025
  Cobertura: 3259 de 3259 freguesias da dim_parish com origem
  Relatório (Parquet): .data/lake/silver/rpt_parish_crosswalk_coverage
  Relatório (CSV, legível): .data/lake/silver/parish_crosswalk_report.csv
  Revisão (pares que não são um-para-um ou têm sinal): .data/lake/silver/parish_crosswalk_review.csv
```

| Código | Quando |
| --- | --- |
| 0 | promovido |
| 1 | tabela ausente ou inválida, `dim_parish` ausente, **cobertura reprovada**, teste do dbt reprovado ou erro de E/S. Nada é promovido; a tabela anterior permanece |

Em reprovação de cobertura a mensagem (stderr) lista os códigos por tipo:

```text
Correspondência: falha: cobertura reprovada
  freguesias da dim_parish sem origem (1): 999999 Nome
  códigos de 2013 sem destino (1): 010199
  destinos fora da dim_parish (1): 010132
```

## Layout em disco (e no S3 simulado)

```text
raw/source=ine_parish_crosswalk/dataset=reorganizacao_2013/run_id=<run>/reorganizacao_2013.xlsx
raw/source=ine_parish_crosswalk/dataset=reposicao_2025/run_id=<run>/reposicao_2025.xlsx
manifests/ine_parish_crosswalk/<run_id>.json
lake/silver/xwalk_parish_2013_2025/data.parquet
lake/silver/rpt_parish_crosswalk_coverage/data.parquet
lake/silver/parish_crosswalk_report.csv
lake/silver/parish_crosswalk_review.csv
```
