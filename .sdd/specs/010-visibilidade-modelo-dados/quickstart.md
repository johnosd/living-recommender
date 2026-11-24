# Quickstart: verificação da spec 010

Pré-requisitos: dependências instaladas (`uv sync --locked`), lake construído em `.data/` (as fontes que o autor já
coletou), nenhuma chave necessária, sem rede.

## 1. Checagens automáticas

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp   # 5/5
uv run --locked python -m pytest -q --basetemp .pytest_tmp                                               # suíte inteira
uv run --locked python -m pipelines.cli.model_docs --check                                               # exit 0
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados              # trava íntegra
```

## 2. Documento (US1)

```powershell
uv run --locked python -m pipelines.cli.model_docs
git status --short .docs/modelo_de_dados.md      # sem mudança se nada foi alterado nos schema.yml
```

Abra `.docs/modelo_de_dados.md` (o GitHub e o VS Code com a extensão do Mermaid mostram o diagrama):

- [ ] a seção **Resumo** diz 25 tabelas e 15 relacionamentos;
- [ ] o diagrama liga `stg_municipality_pole_distance` a `dim_municipality` e a `dim_mobility_pole`;
- [ ] a seção **Lacunas** lista `census_observation.dico` (e outras) em "Chaves territoriais sem relacionamento declarado";
- [ ] depois da Fase 4, nenhuma das 18 tabelas principais aparece em "Sem descrição";
- [ ] teste de defasagem: edite uma `description` em um `schema.yml`, rode `model_docs --check` (exit 1 com a mensagem do comando) e desfaça.

## 3. Catálogo DuckDB (US2)

```powershell
uv run --locked python -m pipelines.cli.lake_catalog --root .data
```

Abra `.data/catalog.duckdb` (passo a passo no runbook `.docs/runbooks/modelo_de_dados.md`) e confira:

```sql
select layer, table_name, status, row_count from meta.tables order by 1, 2;      -- 25 linhas, todas "ok"
select count(*) from silver.dim_municipality;                                     -- 308
select source_id, count(*) from meta.raw_runs group by 1 order by 1;              -- 9 fontes, 43 coletas
select * from meta.columns c join meta.tables t using (layer, table_name)
 where t.kind = 'principal' and (not c.declared or c.description is null
       or lower(c.type_actual) <> lower(c.type_declared));                        -- vazio depois da Fase 4
```

Prova de leitura apenas: antes e depois, o hash de `.data/raw`, `.data/lake` e `.data/manifests` não muda
(`Get-FileHash` em um arquivo de cada, ou o teste de contrato).

## 4. Site do dbt (US4)

```powershell
uv run --locked python -m pipelines.cli.dbt_docs_site --root .data --serve
```

Abra a URL impressa (`http://127.0.0.1:8741`):

- [ ] o catálogo lista os 25 modelos, com descrição e colunas;
- [ ] abra `dim_municipality` e o grafo (ícone de lineage no canto): a fonte `caop_silver.dim_municipality` aparece
  ligada ao modelo, e os modelos de mobilidade, clima, Wikipedia etc. aparecem como dependentes (**R-002**);
- [ ] depois de `Ctrl+C`, `.data/ci` não ganhou nenhum arquivo novo.

## 5. Pre-acceptance (constitution)

- [ ] gitleaks verde no CI; nenhuma chave, valor de dado ou caminho local em `.docs/modelo_de_dados.md`
- [ ] `raw/` e `lake/` intactos
- [ ] nenhum recurso AWS nem custo recorrente
