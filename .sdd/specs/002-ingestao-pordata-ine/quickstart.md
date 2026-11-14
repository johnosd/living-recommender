# Quickstart de verificação — Pordata e INE

## Pré-requisitos

- Python 3.12 via `uv`; `uv sync --locked` (inclui `openpyxl` depois da T001).
- A spec 001 construída: a Silver da CAOP existe em `.data/lake/silver/dim_municipality/data.parquet` (`build_caop`). Sem ela, `build_observations` recusa e pede o `build_caop`.
- Acesso à internet para a coleta real. Pordata e INE são públicos e não exigem credencial; o modo local não usa AWS.
- Para a carga manual: a planilha exportada à mão do Pordata ("Poder de compra per capita", município, NUTS 2013). Ela fica fora do repositório (por exemplo, `Downloads`).

## Checagens automatizadas (sem rede)

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 002-ingestao-pordata-ine
```

Dbt sobre fixtures, uma tag por feature:

```powershell
uv run --locked python -m tests.fixtures.caop.ci_seed --root .data/ci
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:caop
uv run --locked python -m tests.fixtures.observations.ci_seed --root .data/ci-obs
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:observations
```

## Cenário local ponta a ponta (coleta real)

```powershell
uv run --locked python -m pipelines.cli.collect_pordata --local --root .data
uv run --locked python -m pipelines.cli.collect_ine --local --root .data
uv run --locked python -m pipelines.cli.load_pordata_manual --local --root .data --file "C:\caminho\PORDATA_NUTS2013_Poder-de-compra-per-capita.xlsx"
uv run --locked python -m pipelines.cli.build_observations --local --root .data
```

Conferir:

- **Pordata:** 16 datasets `changed` na primeira vez (~82 MB, cerca de 1 minuto: 43 s medidos, com 1 s entre pedidos). Repetir o comando: todos `unchanged`, sem raw novo.
- **INE:** 3 indicadores `changed`; repetir: `unchanged` (a impressão digital ignora o horário de extração). Se aparecer `changed` sem o INE ter republicado, é o R-008.
- **Carga manual:** `changed`; a mesma planilha de novo, `unchanged`; um arquivo qualquer, `failed` e código 1. O manifest registra `collection_method: manual_upload` na entrada e na execução.
- **Falha parcial:** um dataset com URL quebrada aparece como `failed` com o motivo, os outros ficam gravados e o comando sai com código 1.
- **Staging:** `lake/bronze/stg_observation/data.parquet`, um único arquivo com `source_id` e `dataset_id` como colunas; nenhum `dico` nulo; o `lake/silver` e o `stg_caop_*` não mudaram.
- **Cobertura:** `lake/bronze/coverage.csv` e a tabela no terminal: criminalidade com 308 de 308; rendas do INE com cerca de 247 de 308 em 2025; ausentes listados, nenhum zero inventado.
- **Escopo:** `lake/gold/` e `published/` não existem.

Os testes de CI usam fixtures sintéticas; esta coleta real é uma verificação manual adicional e depende da disponibilidade do Pordata e do INE (a API do INE já deu timeout de 60 s em pedidos de metadados).

## S3 simulado

```powershell
uv run --locked python -m pytest -q tests/integration/test_collect_pordata_s3.py --basetemp .pytest_tmp
```

Compara chaves e manifest com o modo local e confirma que a escrita negada falha antes de qualquer download. Nenhuma conta AWS real nesta feature.

## Gate de aceite

Lint, pytest, contratos íntegros (001 e 002), dbt das duas tags, `gitleaks` e CI verdes; nenhum segredo nem bruto real no Git; atribuições e R-001 documentados; CAOP e seu lake inalterados; sem Silver de indicadores, Gold, `published/` nem deploy.
