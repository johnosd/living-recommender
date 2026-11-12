# Handoff para o sdd-execute: 004-correspondencia-freguesias

## Contexto

- **Repositório/branch:** `living-recommender`, branch atual `feature/pordata-845-catalogo` (já enviada ao GitHub, com o commit do dataset 845). **Não é a branch desta feature.** Há alterações não commitadas desta feature (spec, plan, stubs, contratos, `.planning/backlog.md`). Antes de implementar, confirme com o autor e crie uma branch própria a partir de `origin/main` (ex.: `feature/004-correspondencia-freguesias`), levando as alterações; não commite sem pedido.
- **Stack:** Python 3.12 + `uv`, `httpx`, `pandas`/`pyarrow`, `openpyxl`, dbt-core + dbt-duckdb, pytest, `moto`, `ruff`. Nenhuma dependência nova.
- **Próximo comando:** `/sdd-execute 004-correspondencia-freguesias`
- **Status no backlog:** `Planejada`, 0/41 (o script conta toda caixa `- [ ]`, inclusive as 12 do Checklist de Release; são 29 tasks, T001–T029).
- **Criado pelo plan em disco:** `pipelines/collectors/parish_crosswalk/{__init__,validate,transform,derive,coverage,handler}.py` (stubs), `tests/contracts/test_parish_crosswalk_contract.py`, `tests/fixtures/parish_crosswalk/{__init__,tables}.py`, `sdd/specs/004-correspondencia-freguesias/*`. **Nada** foi alterado em `config/sources.yml`, `http.py`, `_shared/` ou no dbt.
- **Também mudou fora desta feature, na mesma sessão:** o commit `246226f` (dataset 845 do Pordata) e a branch `docs/003-convergencia`, ambos já no GitHub. Releia o `git log` e o `git status`.

## O que a feature entrega

- **US1 (P1):** `collect_parish_crosswalk` baixa as duas planilhas do INE (tabela A: pré-2013→2013; tabela B: pré-2013→2025 das 302 repostas) como bruto imutável, manifest v2 por tabela, `unchanged` por `sha256`, falha isolada por tabela.
- **US2 (P1):** `derive_parish_crosswalk` encadeia A e B pelo código pré-2013 e gera 1 linha por par (2013, 2025) com `relation`, `inherited`, `partial_origin`, `name_changed`, `municipality_changed` e `pre2013_codes`; o dbt testa e promove `lake/silver/xwalk_parish_2013_2025`.
- **US3 (P2):** `verify_coverage` reprova a promoção se a `dim_parish` não for coberta; relatório de cobertura e CSV de revisão.
- **Decisões do autor que contrariam a expectativa óbvia:** só a correspondência (TopoJSON é outra spec); **sem pesos**: a herança é só um sinal; a cobertura **reprova o build** (mais estrito que o "aviso" da constitution III); só a CAOP 2025.

## Leitura obrigatória, em ordem

1. `spec.md`: o quê, 3 user stories, FR-001…FR-019, SC-001…SC-007.
2. `plan.md`: Decisões Invariantes D1–D10, Constitution Check, riscos R-001…R-009, comandos de teste.
3. `research.md`: **leia inteiro**: os fatos medidos nas planilhas reais e as decisões R1–R7 que refinam a spec (células numéricas, códigos alfanuméricos, relação por par).
4. `logic/derivacao-correspondencia.md`: **o mais importante**: pseudocódigo de leitura, derivação, cobertura e build, com as armadilhas.
5. `tasks.md`: 29 tasks em 6 fases, contratos amarrados às fases, tabela FR/SC → tasks.
6. `data-model.md`: entrada do catálogo (YAML pronto), colunas das tabelas, do Parquet e do relatório.
7. `contracts/correspondencia-cli.md`: opções, saída e códigos de saída das duas CLIs.
8. `quickstart.md`: verificação manual e os valores de referência da coleta real (T026).
9. `.planning/memory/constitution.md`: sobretudo III (ausente é ausente), IV (licença) e V (bruto imutável, promoção atômica).

## Testes de contrato

- **Arquivos travados (2):** `tests/contracts/test_parish_crosswalk_contract.py` (5 casos) e `tests/fixtures/parish_crosswalk/tables.py`. Fases: contratos 1–3 na Fase 3 (US1), contrato 4 na Fase 4 (US2), contrato 5 na Fase 5 (US3).
- **Comando:** `uv run --locked python -m pytest -q --basetemp .pytest_tmp tests/contracts/test_parish_crosswalk_contract.py`
- **Integridade:** `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 004-correspondencia-freguesias`. Para Python o script só confere o hash (`tests: unknown`); respeite o orçamento de 5 à mão.
- **Estado inicial:** os 5 estão vermelhos, todos por `NotImplementedError: not implemented: … (T0xx)` dos stubs.
- **Travas de outras features que esta pode quebrar:** o contrato **importa** `MemoryStorage` de `tests/fixtures/open_meteo/responses.py` (travado pela 003). Não altere esse arquivo. Os contratos das specs 001–003 devem seguir verdes.

## Stubs criados

- `validate.py` → `CrosswalkSchemaError` (**definido, já usado pelos contratos**) e `validate_crosswalk_table` (provisório até T006).
- `transform.py` → `read_crosswalk_table` (provisório até T007; docstring com as colunas).
- `derive.py` → `CROSSWALK_COLUMNS` (constante já correta) e `derive_parish_crosswalk` (provisório até T013).
- `coverage.py` → `CrosswalkCoverageError` (atributos já declarados) e `verify_coverage` (provisório até T019).
- `handler.py` → `SOURCE_ID` e a assinatura de `collect_parish_crosswalk` (provisório até T008).
- `layout.py` **não existe**; é a T004. `validate.py` e `transform.py` devem importá-lo; `layout.py` importa `CrosswalkSchemaError` de `validate.py` (cuidado com import circular: mantenha a exceção em `validate.py` e importe `layout` dentro das funções, ou mova a exceção para `layout.py` e reexporte em `validate.py` sem mudar o nome público).

## Armadilhas já mapeadas

- **A regra "número é erro" da spec não vale literalmente.** As planilhas reais têm **51 células inteiras** de 6 dígitos. Aceite inteiro de exatamente 6 dígitos e rejeite menos (research R1). Sem isso, a coleta real reprova.
- **Códigos têm letras** (`0308FC`, 31 linhas; 18 na `dim_parish`): padrão `[0-9A-Z]{6}`, nunca `\d{6}` (R2).
- **A tabela B tem a aba `Sheet1`** e o rótulo `Código -  Freguesias repostas em 2025` com **dois espaços**; compare rótulos normalizados (R3). O catálogo grava com um espaço.
- **`Versao/Download/9160` não tem extensão**: o sufixo `.xlsx` vem de `format: xlsx` no catálogo (`datasets._suffix`). Os links respondem 200 a `GET`; `HEAD` volta vazio, então não use `HEAD`.
- **Merge na granularidade da linha da A.** O código `021113` aparece duas vezes na A; `drop_duplicates("pre_code")` apagaria um par (`logic/` §3).
- **`partial_origin` é do par**, não do código pré-2013 (`110633` gera dois pares; só o de `110662` é parcial).
- **Não alterar `_shared/datasets.py`**; a única mudança em `_shared/` é `xlsx_content_check` em `http.py`.
- **dbt:** o source `caop_silver` já existe em `models/bronze/schema.yml`; acrescente `dim_parish` a ele, não crie outro (R-008). Sempre `--select tag:parish_crosswalk`; um `dbt build` sem seleção quebra por falta das entradas de outras features.
- **Promoção por caminho** com `_promote.promote_paths`; nunca `lake/silver` inteiro (apagaria `dim_*`).
- **Testes no Windows:** use `python -m pytest --basetemp .pytest_tmp` (o `pytest` direto não acha `pipelines`; o temp padrão nega permissão). O `dbt` precisa estar no PATH: rode tudo por `uv run --locked`.
- **Nunca rede nos testes**; downloader e storage são injetados. Os arquivos reais ficam em `.data/` (ignorado). **Nenhuma planilha real no Git.**
- **Commits curtos e em inglês** (constitution, Quality Gate 7).

## Pendências do Analyze

- **A-001 (MEDIUM): a spec contradiz os dados reais em "código lido como número é erro".** Resolvido no plano (D3, R1) sem editar a spec. Recomendação: o autor aprova a refinação e, se quiser, uma linha em `spec.md` → Clarifications.
- **A-002 (MEDIUM): tensão com a constitution III.** O princípio pede "aviso", a feature reprova a promoção. Registrada em Complexity Tracking. Recomendação: o autor decide se emenda a constitution (tabelas estruturais vs indicadores) ou mantém a exceção pontual.
- **A-003 (MEDIUM): FR-009 ambíguo ("mesmo conjunto de pares").** Resolvido por par (D6, R4). Recomendação: esclarecer a frase na spec quando conveniente.
- **A-004 (LOW): SC-002 fala em códigos, o relatório conta pares por natureza.** Os valores da spec saem do relatório (`codes_2013` por natureza: 2.957 e 135; `codes_2025` de `many_to_many`: 1), mas não há uma coluna "códigos com mais de um destino". Recomendação: T021 pode somá-la; T026 conferir.
- **A-005 (LOW): FR-017 pede S3 simulado; o build é só `--local`**, como `build_observations` e `build_climate`. A coleta tem teste S3 (T011). Recomendação: manter; abrir spec própria se um build em S3 for necessário.
- **A-006 (LOW): R-002 (licença) e R-001 (estabilidade dos links) abertos.** T028 e a falha explícita cobrem.
- **A-007 (LOW): o lock não infere a contagem de testes Python.** O orçamento de 5 foi respeitado à mão; revisar se alguém acrescentar casos ao arquivo (não pode: está travado).

## Gate de pronto

- 5 contratos verdes e `check-contract-tests.ps1` íntegro; contratos 001–003 intactos.
- `uv run --locked ruff check pipelines tests` limpo; `uv run --locked python -m pytest -q --basetemp .pytest_tmp` verde (suíte inteira).
- `dbt build --select tag:parish_crosswalk` verde sobre a fixture e sobre os dados reais.
- Coleta real conferida contra os valores de referência de `quickstart.md` §4 (T026) e `unchanged` na repetição.
- SHA-256 de `dim_parish`, `dim_municipality` e demais saídas inalterado (SC-006).
- Documentação do Polish (T025): `.docs/fontes_de_dados.md`, `docs/runbooks/coletas.md`, `README.md`.
- A passada com os dados reais (T026) é **gate**, não recomendação: o plano só se sustenta se a coleta real reprovar nada e reproduzir os números.
