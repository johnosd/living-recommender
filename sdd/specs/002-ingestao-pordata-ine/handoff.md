# Handoff — 002-ingestao-pordata-ine

## Contexto

Repositório `living-recommender`, Python 3.12 + `uv`, dbt-duckdb. A branch `feature/fundacao-ingestao` já foi mergeada em `main` (PR #1), então **crie uma branch nova antes de executar** (por exemplo, `feature/ingestao-pordata-ine`). Está sem commit: a convergência da spec 001 (edições em `plan.md`, `spec.md`, `tasks.md` e `.planning/backlog.md`) e toda a pasta `sdd/specs/002-ingestao-pordata-ine/`, mais os stubs e o contrato (`pipelines/collectors/_shared/datasets.py`, `_shared/municipality.py`, `pipelines/collectors/ine/`, `tests/contracts/test_dataset_ingestion_contract.py`). Próximo comando: `/sdd-execute 002-ingestao-pordata-ine`. Backlog: `Planejada`, 0/50. **A `spec.md` foi emendada durante o plano, por decisão do autor** (poder de compra por API do INE **e** carga manual do Excel, nova US5 e FR-023, FR-013 com resolução por código no INE, FR-022 respondido, `NEEDS CLARIFICATION` zerado); releia-a.

## O que a feature entrega

- **US1 (P1):** `collect_pordata` baixa 16 CSV, cada um com estado próprio; falha de um dataset não bloqueia os outros (`partial`, código 1).
- **US2 (P2):** `collect_ine` coleta 3 indicadores da API JSON do INE (rendas `0014698`, criminalidade `0008074`, poder de compra `0014580`) sem falso `changed`.
- **US3 (P2):** `build_observations` gera `stg_observation` (Parquet longo, `dico` resolvido, particionado por dataset) sem tocar a CAOP.
- **US4 (P3):** relatório de cobertura por dataset (`coverage.csv`).
- **US5 (P3):** `load_pordata_manual` guarda a planilha de poder de compra do Pordata, que o site só entrega por botão JavaScript. O autor decidiu manter **os dois** (API do INE e planilha).
- Decisão do autor: coletar o Pordata **apesar** de os termos não concederem licença (risco aceito R-001; `license_id: not_granted_by_source`).

## Leitura obrigatória, em ordem

1. `spec.md`: escopo, 5 histórias, FR-001 a FR-023, SC-001 a SC-007, clarificações.
2. `plan.md`: decisões D1–D10, Constitution Check (exceção do princípio IV), riscos R-001 a R-009, estratégia de testes.
3. `tasks.md`: T001–T036 por fase, com o contrato de cada fase.
4. `logic/ingestao-datasets.md`: o algoritmo de `collect_datasets`, a impressão digital do INE, a resolução de município, a cobertura e a promoção. **Leia antes de codar.**
5. `data-model.md`: catálogo, manifest v2, layout do bruto, tabela de staging.
6. `contracts/ingestao-cli.md`: as 4 CLIs, códigos de saída.
7. `research.md`: medições reais de 2026-11-11 (formatos, códigos do INE, licenças).
8. `quickstart.md` e `.planning/memory/constitution.md`.

## Testes de contrato

`tests/contracts/test_dataset_ingestion_contract.py`: **5 testes** (US1: 3, na Fase 3; INE: 1, na Fase 4; US3: 1, na Fase 5). Rodar: `uv run --locked python -m pytest -q tests/contracts/test_dataset_ingestion_contract.py --basetemp .pytest_tmp` (filtros por fase: `-k us1`, `-k ine`, `-k us3`). Integridade: `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 002-ingestao-pordata-ine`. Hoje: **5 falham por `NotImplementedError`**. Esta feature mexe em código da 001 (`http.py`, `catalog.py`, `build_caop._run_dbt`), então `tests/contracts/test_caop_collection_contract.py` (trava `001-ingestao-caop`) **precisa continuar verde** e íntegro.

## Stubs criados (não travados)

- `pipelines/collectors/_shared/datasets.py`: `collect_datasets(...)` e `DatasetCollectionError`; o corpo levanta `NotImplementedError` até a T007.
- `pipelines/collectors/_shared/municipality.py`: `resolve_municipality_names(...)` e `UnresolvedMunicipalities(names)`; provisório até a T020.
- `pipelines/collectors/ine/__init__.py` (vazio) e `ine/fingerprint.py`: `fingerprint_ine_response(path)`; provisório até a T014.

## Armadilhas já mapeadas

- **`build_caop._promote` apaga a CAOP.** Ele troca `lake/bronze` e `lake/silver` inteiros. Promova só `stg_observation` e `rpt_observation_coverage` (R-006). Teste que a CAOP fica byte a byte igual.
- **`dbt build` sem seleção quebra tudo.** Hoje `build_caop` e o CI rodam sem `--select`. A **T005 vem antes de qualquer modelo dbt novo** (tags `caop`/`observations`, R-007).
- **INE:** a resposta tem `DataExtracao` (muda a cada chamada) e a API não envia `ETag`. Compare pela impressão digital, não pelo `sha256` bruto. `Dim3=T` devolve **só "Total"**: use `Dim3=T,1,2,3,4,5,6`. Use `Dim2=lvl@5`. Pedidos de metadados deram timeout de 60 s: timeout de 90 s e retentativas.
- **CSV do Pordata:** valide e leia **pelo rótulo**, nunca por posição (o prefixo numérico varia; o dataset 4 tem `Max. 08. Escala`; os datasets 1 e 559 têm `Nome País`). Município = `Âmbito Geográfico == "Município"`; agregação tem âmbito vazio.
- **Nomes:** só 5 grafias precisam de seed (`Lagoa`→0806, `Lagoa [R.A.A.]`→4201, `Calheta [R.A.A.]`→4501, `Calheta [R.A.M.]`→3101, `Vila da Praia da Vitória`→4302). `Lagoa` sem a seed é **ambígua** e deve reprovar. INE: `dico = geocod[-4:]`.
- **`HttpDownloader` rejeita tudo que não é ZIP** (`PK\x03\x04`, mensagem de GeoPackage). Parametrize sem mudar o padrão da CAOP (T003).
- **`catalog.get_source` e `manifest.validate_changed` são da CAOP** (três regiões). Não os generalize: crie `get_dataset_source` e `dataset_manifest.py`.
- **Fakes dos contratos:** o `MemoryStorage` tem `list_keys()` **sem argumentos** e **não tem `preflight`** (mantenha `hasattr`). Um `fetcher` do contrato devolve `None`.
- **Ausente nunca é 0:** `value` nulo + `symbol`. O símbolo `-` do Pordata e o `sinal_conv: "-"` do INE significam nulo.
- **O `�` no terminal do Windows é só a página de código**, não dado quebrado: os arquivos são UTF-8.
- **Dados reais fora do Git:** a planilha do autor está em `C:\Users\johns\Downloads\PORDATA_NUTS2013_Poder-de-compra-per-capita.xlsx` (layout: aba `Quadro`, cabeçalho na linha 12, anos 1993–2021, 308 linhas `Município`). Não a copie para o repositório; use a fixture sintética e a planilha real só na T035. Os arquivos baixados na pesquisa estão no scratchpad da sessão, não no repositório.
- **CI fica vermelho** nesta branch até a Fase 5 (os contratos pendentes quebram o `pytest` completo), como aconteceu na 001. Evite abrir PR antes disso, ou aceite o vermelho temporário.
- **`openpyxl` não está instalado** até a T001. Nunca rode scripts de projeto com `python -I` (perde o `import pipelines`).

## Pendências do Analyze

- **A-001 MEDIUM:** contratos vermelhos deixam o CI vermelho até a Fase 5. Recomendação: abrir o PR só depois da US3, ou aceitar o vermelho temporário.
- **A-002 MEDIUM:** o edge case "execução concorrente" da spec não tem teste. Recomendação: acrescentar à T012 um caso com dois `run_id` distintos (análogo a `tests/unit/test_caop_concurrency.py`).
- **A-003 LOW:** o S3 simulado só é exercitado no Pordata (T013); INE e carga manual usam o mesmo `collect_datasets` e o mesmo `S3Storage`. Recomendação: parametrizar a T013 pelas três CLIs (SC-005).
- **A-004 MEDIUM:** `.docs/fontes_de_dados.md` contém afirmações agora sabidamente falsas (rendas do INE "para todos os municípios", Pordata "uso livre com citação", a URL do poder de compra). A T034 as corrige no Polish; até lá o `.docs` engana. Recomendação: tolerar ou corrigir antes.
- **A-005 LOW:** a cobertura ("≥ 1 valor no último período") pode mascarar lacunas por filtro em datasets como o 1 (sexo × idade). É decisão registrada no `data-model.md`; confirmar com o autor se basta para o Gold.
- **A-006 LOW:** dois esquemas de ID parecidos (`research.md` R1–R8 e riscos `R-001`–`R-009` do plano). Cite sempre "research R4" versus "R-004".

## Gate de pronto

Contratos 5/5 verdes e as duas travas íntegras (001 e 002); `uv run --locked ruff check pipelines tests`; `uv run --locked python -m pytest -q --basetemp .pytest_tmp`; `dbt build ... --select tag:caop` (31 passos, após `ci_seed` da CAOP) e `--select tag:observations`; `gitleaks` via Docker e CI verdes; `quickstart.md` executado (coleta real distinta da prova automatizada); README, runbook e `.docs/fontes_de_dados.md` atualizados (T034); CAOP e seu lake inalterados; nenhum bruto real nem credencial no Git; nenhum Silver de indicadores, Gold, `published/` ou deploy.
