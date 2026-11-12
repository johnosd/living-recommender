# Quickstart: verificação da correspondência de freguesias

## 1. Pré-requisitos

- `uv sync --locked`. Nenhuma chave de API e nenhum `.env`.
- Internet, só para a coleta real (§4).
- `dim_parish` já construída: `uv run --locked python -m pipelines.cli.build_caop --local` (spec 001).

## 2. Verificações automáticas (sem rede)

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 004-correspondencia-freguesias
```

Esperado: lint limpo, suíte verde (contratos da 004 incluídos) e `PASS: trava íntegra`.

O dbt com a fixture da feature (mesmo passo do CI):

```powershell
uv run --locked python -m tests.fixtures.parish_crosswalk.ci_seed --root .data/ci-xwalk
$env:XWALK_BUILD_DIR = ".data/ci-xwalk"; $env:XWALK_PREPARED_DIR = ".data/ci-xwalk/prepared"
$env:OBS_SILVER_DIR = ".data/ci-xwalk/lake/silver"; $env:CAOP_DUCKDB_PATH = ".data/ci-xwalk/xwalk.duckdb"
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:parish_crosswalk
```

## 3. Cenário ponta a ponta com a fixture

1. `collect_parish_crosswalk` com um downloader offline grava os dois brutos; a segunda execução devolve `unchanged` sem bruto novo.
2. `build_parish_crosswalk` sobre a fixture promove a tabela e imprime as contagens; o CSV de revisão lista os pares que não são um-para-um.
3. Remover uma linha da tabela B de fixture e reconstruir: a cobertura reprova, o código de saída é 1 e `lake/silver/xwalk_parish_2013_2025` continua com o conteúdo anterior.

## 4. Coleta real e conferência com a pesquisa (T026)

```powershell
uv run --locked python -m pipelines.cli.collect_parish_crosswalk --local
uv run --locked python -m pipelines.cli.build_parish_crosswalk --local
```

Valores de referência (pesquisa de 2026-11-12, `research.md`): **3.260 pares**, 3.092 códigos de 2013, 3.259 de 2025; 2.957 um-para-um, 301 um-para-muitos, 0 muitos-para-um, 2 muitos-para-muitos; herança 303, origem parcial 8, nome alterado 297, município alterado 0. Divergência é aceitável **só** com explicação por mudança na fonte (SC-002); registre-a no `research.md`.

Repetir `collect_parish_crosswalk` deve devolver `unchanged` nas duas tabelas (SC-003). O tamanho esperado do bruto é 205.543 + 27.382 bytes.

## 5. Checklist de pré-aceitação (constitution)

- [ ] `config/sources.yml` e `.docs/fontes_de_dados.md` descrevem a fonte nova (Quality Gate 6).
- [ ] Nenhum segredo, nenhuma planilha real no Git (`git status` limpo de `.data/`).
- [ ] Modelos dbt novos com `not_null`, `relationships` com `dim_parish` e testes singulares; `dbt build` passa.
- [ ] `dim_parish`, `dim_municipality` e demais saídas com o mesmo SHA-256 antes e depois (SC-006).
- [ ] Licença das planilhas confirmada ou registrada como risco aceito (R-002).
- [ ] Mensagens de commit curtas e em inglês (Quality Gate 7).
