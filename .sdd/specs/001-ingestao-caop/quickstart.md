# Quickstart de verificação — CAOP

## Pré-requisitos

- Python 3.12 via `uv` e as dependências de `pyproject.toml`/`uv.lock` (`uv sync --locked`).
- Diretório `.data/` ignorado pelo Git. Para a coleta real, acesso à internet e à página oficial da DGT; nenhum segredo AWS é necessário para `--local`.
- Catálogo `config/sources.yml` revisado com versão, URLs e licença da edição efetivamente vigente.

## Checagens automatizadas (sem rede)

```powershell
uv sync --locked
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 001-ingestao-caop
```

Resultado esperado: ruff sem erros, 38 testes passando (incluindo os 5 contratos P1 e os 8 de S3 simulado) e `PASS: trava íntegra`.

Build dbt sobre a fixture sintética nacional (308 municípios), também sem rede:

```powershell
uv run --locked python -m tests.fixtures.caop.ci_seed --root .data/ci
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local
```

Resultado esperado: `PASS=31 WARN=0 ERROR=0`.

## Cenário local ponta a ponta (coleta real)

```powershell
uv run --locked python -m pipelines.cli.collect_caop --local --root .data
uv run --locked python -m pipelines.cli.build_caop --local --root .data
uv run --locked python -m pipelines.cli.view_caop --root .data
```

Conferir:

- **Primeira coleta num `.data/` vazio:** status `changed`, com três ZIPs em `raw/` e um manifest com checksum, licença, versão e período. Cada execução baixa ~143 MB (111,6 MB + 15,9 MB + 15,2 MB na CAOP2025) e leva cerca de 1 minuto.
- **Coleta seguinte, com a fonte igual:** status `unchanged`, só um novo manifest e nenhum objeto novo em `raw/`. Rodar o comando de novo já prova isso; a DGT não precisa ser consultada mais vezes do que o necessário.
- **`--force-check`:** repete a ida à fonte, mas não altera a regra do checksum: conteúdo idêntico continua `unchanged`. Na prática é igual a rodar o comando sem a opção.
- **Build:** 308 municípios e 3259 freguesias (na CAOP2025), com 18 códigos de freguesia com letras preservados; freguesias sem órfãos; áreas e pontos válidos; Parquet em `lake/bronze/` e `lake/silver/`.
- **Visualização:** `.data/explore/caop.html`, `municipios.csv` e `freguesias.csv`.
- **Escopo:** `lake/gold/` e `published/` não são criados por esta feature.
- **Atribuição:** "Fonte: Direção-Geral do Território (DGT), CAOP2025", CC-BY-4.0.

Os testes de CI usam fixtures sintéticas; esta coleta real é uma verificação manual adicional e depende da disponibilidade da DGT. Sobre homônimos, na CAOP2025 o único nome repetido entre municípios é "Lagoa" (`0806` em Faro e `4201` em São Miguel); o município dos Açores chama-se "Calheta de São Jorge".

## Destino S3 (simulado)

A prova automatizada usa o moto, sem conta AWS:

```powershell
uv run --locked python -m pytest -q tests/integration/test_caop_s3.py --basetemp .pytest_tmp
```

Ela compara chaves, bytes e manifest com os do modo local, confere que a escrita negada ou o bucket inexistente falham **antes** de qualquer download, que o modo local nunca cria um cliente AWS e que uma falha de upload limpa o run e permite repetir a coleta.

O comando para um bucket real, que **não** foi exercitado nesta feature (risco R-008), é:

```powershell
uv run --locked python -m pipelines.cli.collect_caop --s3 --bucket <bucket> [--prefix <prefixo>]
```

As credenciais vêm só da cadeia padrão da AWS (variáveis de ambiente, perfil ou papel IAM). Antes do primeiro uso, confirmar num bucket de teste que a escrita condicional (`IfNoneMatch`) recusa sobrescrever.

## Gate de aceite

Lint, pytest, contrato íntegro, build dbt e testes geoespaciais verdes; nenhum segredo ou bruto real no Git (`gitleaks` do CI); catálogo/licença atualizados; sem deploy AWS nem publicação.
