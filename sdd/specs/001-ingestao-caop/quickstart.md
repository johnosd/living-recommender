# Quickstart de verificação — CAOP

## Pré-requisitos

- Python 3.12 via `uv`, ambiente local e dependências de `pyproject.toml`/`uv.lock` após as tasks de instalação.
- Diretório `.data/` ignorado pelo Git. Para coleta real, acesso à página oficial DGT; nenhum segredo AWS é necessário para `--local`.
- Catálogo `config/sources.yml` revisado com versão, URLs e licença da edição efetivamente vigente.

## Checagens automatizadas

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
```

Após o projeto dbt existir, executar `dbt build` pelo comando do `plan.md` com fixtures e sem rede.

## Cenário local ponta a ponta

```powershell
uv run --locked python -m pipelines.cli.collect_caop --local --root .data
uv run --locked python -m pipelines.cli.collect_caop --local --root .data --force-check
uv run --locked python -m pipelines.cli.build_caop --local --root .data
uv run --locked python -m pipelines.cli.view_caop --root .data
```

Conferir: primeiro run `changed`; segundo `unchanged` sem novos objetos `raw/`; manifests distintos com checksum, licença, versão e período; três regiões presentes; 308 municípios; freguesias sem órfãos; áreas e pontos válidos; Parquet Bronze/Silver; `lake/gold/` e `published/` não criados por esta feature. Conferir atribuição da DGT. Os testes de CI usam fixtures sintéticas; esta coleta real é verificação manual adicional e depende da disponibilidade da DGT.

## S3 simulado

Rodar os testes de integração com backend S3 simulado, comparar chaves/manifests aos do backend local e verificar falha de permissão antes do download. Não usar conta AWS real nesta feature.

## Gate de aceite

Lint, pytest, contrato íntegro, build dbt e testes geoespaciais verdes; nenhum segredo ou bruto real no Git; catálogo/licença atualizados; sem deploy AWS nem publicação.
