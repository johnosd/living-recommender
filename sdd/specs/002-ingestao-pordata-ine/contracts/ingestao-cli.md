# Contrato das CLIs — Pordata e INE

Todas rodam por `uv run --locked python -m pipelines.cli.<nome>` e seguem as convenções da CAOP (`collect_caop`).

## Coleta

```text
collect_pordata --local [--root <dir>]            # padrão: --local, --root .data
collect_pordata --s3 --bucket <b> [--prefix <p>]
collect_ine     --local [--root <dir>]            # idem
collect_ine     --s3 --bucket <b> [--prefix <p>]
```

- `--local` e `--s3` são exclusivos; `--bucket`/`--prefix` só valem com `--s3`; `--s3` exige `--bucket` (erro de argumento, código 2). O modo local não exige credenciais; no S3 elas vêm só da cadeia padrão da AWS.
- Lê `config/sources.yml` e recusa fonte, dataset ou indicador que não esteja no catálogo. `collect_pordata` trata só os datasets `http_download`; o dataset `manual_upload` é ignorado aqui (entra por `load_pordata_manual`).
- Antes de qualquer rede, o destino passa pelo `preflight` (escrita e remoção); falha ali sai sem manifest.
- Saída: uma linha por dataset (`changed`/`unchanged`/`failed`, tamanho, motivo se falhou), o status da execução e a chave do manifest.
- **Código de saída:** `0` para `changed` e `unchanged`; `1` para `partial`, `failed` ou erro antes da tentativa. Um dataset falho nunca impede os demais de serem gravados.

## Carga manual

```text
load_pordata_manual --file <xlsx> [--dataset poder_compra_per_capita_xlsx] (--local [--root <dir>] | --s3 --bucket <b> [--prefix <p>])
```

Valida a planilha (abas `Quadro`/`Metainformação`, cabeçalho com `Anos`, 308 linhas com âmbito `Município`), grava o bruto e o manifest `pordata` com um único dataset. Mesma planilha → `unchanged`. Arquivo inválido → `failed`, sem bruto, código `1`. O arquivo de origem nunca é alterado nem copiado para dentro do repositório.

## Staging e cobertura

```text
build_observations --local [--root <dir>]
```

- Pré-requisito: a Silver da CAOP (`<root>/lake/silver/dim_municipality/data.parquet`). Ausente → falha pedindo `build_caop`.
- Para cada fonte, usa o **estado vigente de cada dataset** (verificando `sha256` do bruto), prepara o Parquet longo, roda o dbt em área temporária e só promove `lake/bronze/stg_observation/` e `lake/bronze/rpt_observation_coverage/` se todos os testes passarem. **Nunca** substitui `lake/bronze` ou `lake/silver` inteiros (isso apagaria a CAOP).
- Saída: contagem de observações por fonte e a tabela de cobertura (dataset, último período, municípios com valor de 308, sem valor, linhas de agregação excluídas), além de `<root>/lake/bronze/coverage.csv` com a lista de ausentes.
- Município sem correspondência → código `1`, informando dataset e nomes.

## Invariantes

O mesmo `run_id` nunca sobrescreve chaves. O estado de cada dataset é independente. Uma tentativa `failed` nunca vira estado vigente nem entrada do staging. Nenhum arquivo bruto real entra no Git.
