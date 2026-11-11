# Quickstart: verificação da ingestão de clima

Passos manuais para conferir a feature depois do `sdd-execute`. Tudo roda na raiz do repositório, no PowerShell.

## 1. Pré-requisitos

- `uv` e Python 3.12 (`uv sync --locked`).
- **Silver da CAOP construída** em `.data/lake/silver/dim_municipality/data.parquet` (spec 001): `uv run --locked python -m pipelines.cli.build_caop --local` (precisa dos GeoPackages já coletados com `collect_caop`).
- Acesso à internet, só para a coleta real (§4). Nenhuma chave de API, nenhum `.env`.
- Cota do Open-Meteo livre: 10.000 chamadas/dia no plano gratuito. A coleta real consome cerca de 21 mil a 31 mil chamadas no total, ou seja, **3 dias** (R-003).

## 2. Verificações automatizadas (sem rede)

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
uv run --locked python -m pytest -q tests/contracts/test_climate_collection_contract.py --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 002-ingestao-pordata-ine
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 003-ingestao-clima-open-meteo
```

Esperado: `ruff` limpo, suíte inteira verde (140 existentes + os novos), 5/5 contratos verdes e as três travas `íntegra`.

## 3. Cenário ponta a ponta com fixtures (sem rede)

```powershell
uv run --locked python -m tests.fixtures.climate.ci_seed --root .data/ci-climate
$env:OBS_SILVER_DIR = ".data/ci-climate/lake/silver"
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:climate
```

O seed cria uma Silver sintética com 308 municípios (com latitude e longitude), coleta com um fetcher offline numa janela curta (`2025-01-01` a `2025-01-31`, 31 dias) e prepara o Parquet. O `dbt build` deve passar, com os testes de chave, de dias por município, de faixa física e de `relationships`. Esse é o mesmo passo do CI.

Para exercitar o build completo e a promoção:

```powershell
uv run --locked python -m pipelines.cli.build_climate --local --root .data/ci-climate
```

Esperado: `Clima: <308 × 13 × 31> linhas de 308 municípios`, a tabela de cobertura com `308/308` e `climate_coverage.csv` e `climate_points.csv` em `.data/ci-climate/lake/bronze/`.

## 4. Coleta real e medição (T037, SC-008)

Uma vez, no ambiente local do autor.

```powershell
# 1. Smoke: 5 municípios, ~350 chamadas
uv run --locked python -m pipelines.cli.collect_open_meteo --local --max-municipalities 5
# 2. Repetir sem o teto, uma vez por dia, até aparecer "nada a coletar (308/308 atuais)"
uv run --locked python -m pipelines.cli.collect_open_meteo --local
# 3. Staging e cobertura
uv run --locked python -m pipelines.cli.build_climate --local
```

Registrar no `plan.md` (Execution Notes) e em `research.md` (R3, R4):

- número de execuções necessárias e de municípios por execução (calcula o peso real por município: `10.000 ÷ municípios no dia`);
- se a cota diária foi atingida: o **texto exato** do `reason` do 429, para conferir a fixture (R4);
- municípios com lacuna, com ponto divergente (> 25 km) ou com elevação 0 m, de `climate_coverage.csv` e `climate_points.csv`;
- o tamanho de `.data/raw/source=open_meteo` (esperado: ~20 MB);
- uma recoleta de 3 municípios com `--recollect --max-municipalities 3`: esperado `unchanged`, ou `changed` com os meses finais da janela (dados preliminares, R-006).

## 5. Cuidados antes de considerar pronta (constitution)

- [ ] `.env`, chaves e brutos reais **fora do Git** (`.data/` está no `.gitignore`); nenhuma resposta real em `tests/fixtures/`.
- [ ] CI verde, incluindo o passo do `dbt` do clima e o `gitleaks` no PR.
- [ ] `config/sources.yml`, `.docs/fontes_de_dados.md`, `docs/runbooks/coletas.md` e `README.md` atualizados (Quality Gate 6).
- [ ] Atribuição "Dados meteorológicos: Open-Meteo.com (CC BY 4.0)" presente no catálogo, no manifest e em cada linha do staging; restrição de uso não comercial registrada (R-001).
- [ ] Nenhum recurso AWS criado; custo recorrente zero.
