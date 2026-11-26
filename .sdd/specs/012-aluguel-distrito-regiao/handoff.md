# Handoff — 012-aluguel-distrito-regiao (sdd-plan → sdd-execute)

## Contexto

- **Repositório:** `J:\living-recommender`, branch `feature/011-marts-indicadores-catalogo`. A 011 está commitada
  nela, sem push. Considere abrir `feature/012-aluguel-distrito-regiao` a partir dela antes de começar.
- **Stack:** Python 3.12 (uv), pandas, dbt-duckdb (DuckDB 2.0), pytest e ruff. Lake local em `.data/lake`.
- **Próximo comando:** `/sdd-execute 012-aluguel-distrito-regiao`. No backlog: **Planejada** (0/43).
- **Sem commit, de propósito:** os artefatos da 012, `pipelines/gold/areas.py`, o contrato, `.planning/backlog.md`,
  e o trabalho de exploração anterior (`analytics/notebooks/explorar_gold.ipynb`, o grupo `notebook` em
  `pyproject.toml` e `uv.lock`, `.planning/memory/duckdb-2-api-e-notebook.md`). Não desfaça.

## O que a feature entrega

- **US1 (P1):** `gold_rent_by_district_typology` e `gold_rent_by_region_typology`, com a mesma regra do município
  e outliers recalculados por área.
- **US2 (P1):** município sem amostra herda por variante (distrito, depois região), com `origin` e
  `origin_level`; a normalização P5/P95 usa só próprios.
- **US3 (P2):** freguesia com `origin_level`; qualidade com próprios e herdados por nível.
- **Decisões que contrariam o óbvio:**
  - coluna nova `origin_level`; `territorial_inheritance` continua só dos Censos (D7);
  - `rent_coverage` **continua** `sem_anuncios` no município que herda; o rótulo honesto são as colunas
    `reference_level*`;
  - a região é a do Idealista, derivada do snapshot, sem mapa fixo e sem NUTS (D3);
  - a freguesia mantém a mediana `ALL` própria com n ≥ 10 (R-007).

## Leitura obrigatória, em ordem

1. `spec.md`: FRs, ACs, edge cases e Clarifications.
2. `plan.md`: Decisões D1–D10, riscos R-001–R-009 e Estratégia de Testes.
3. `tasks.md`: T001–T033; os stubs citam T005, T006, T013 e T014.
4. `logic/heranca.md`: o "como" (colocação dos anúncios, cadeia, colunas copiadas, freguesia, qualidade).
5. `data-model.md`: tabelas novas, colunas novas e colunas que mudam de sentido.
6. `research.md` (números esperados), `quickstart.md` (verificação) e `.planning/memory/constitution.md`.

## Testes de contrato

- `tests/contracts/test_gold_area_rent_contract.py`: **5 funções** — 2 na Fase 3, 2 na Fase 4, 1 na Fase 5. A
  contagem é manual (o script mostra "unknown").
- Rodar: `uv run --locked python -m pytest tests/contracts/test_gold_area_rent_contract.py -q --basetemp .pytest_tmp`.
  Vermelho confirmado: 3 `NotImplementedError` e 2 asserções.
- Integridade: `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 012-aluguel-distrito-regiao`.
- **Travas de outra feature em risco:** `tests/contracts/test_gold_indicators_contract.py` (011) chama
  `rent_stats` sem `district_or_island` e `catalog_tables` sem coluna `origin`. Não mude essas assinaturas nem
  exija essas colunas.

## Stubs criados

| Arquivo | Conteúdo |
| --- | --- |
| `pipelines/gold/areas.py` | `AreaError(ValueError)`, `ISLAND_SEED`, `territory_hierarchy`, `district_rent_stats`, `region_rent_stats`, `reference_levels` e `apply_rent_inheritance`, todos com `NotImplementedError`. As assinaturas são fixas (o contrato importa 5 desses nomes). |

A seed `analytics/dbt/seeds/idealista_island_aliases.csv` **não existe** ainda (T004). Os contratos que usam ilhas
dependem dela.

## Armadilhas já mapeadas

- `rent._current` já devolve a coluna `outlier` do grupo municipal: **recalcule** na área, senão o outlier de
  distrito passa (o contrato cobra).
- Anúncio com `dico` ignora `source_subregion` (`Horta` não é distrito).
- `source_region` pode ser `""`; trate como nula.
- `dico` desconhecido sumiria sem aviso num `map`: levante `AreaError`.
- Em `parish_indicators`, a base traz `origin = proprio` do município: tem de ser sobrescrita. Sem `origin_level`
  no perfil municipal (testes da 011), o herdado é `municipio`.
- Filtrar a normalização por `origin` quebra
  `test_gold_parish.py::test_parish_normalization_ignores_inherited_values`: ajuste o teste (T016), não a regra.
- `test_gold_build.py::test_quality_mart_...` quebra na US3, porque `with_value` passa a contar só próprios (T027).
- A fixture `ci_seed.py` não tem `district_or_island` nem `source_subregion` (T001).
- Não use `relationships` do dbt para `district_or_island`: o `modeldocs` desenharia uma chave estrangeira para
  coluna repetida. Use o teste singular.
- Declare **todas** as colunas no `schema.yml` e regenere `.docs/modelo_de_dados.md`, ou o CI reprova.
- YAML com `": "` sem aspas quebra o parse (`criteria.yml` e `schema.yml`).
- Seleção dbt sempre por tag; `caop_silver` não pode ser declarada de novo.
- DuckDB 2.0: relação não tem `fetchone()`; use `.fetchall()[0][0]` ou `.df()`.
- A suíte completa leva ~12 min: rode em segundo plano.
- Nunca rede: o build só lê o lake local.
- Guarde a normalização atual **antes** do primeiro build real novo (quickstart §1), senão não há como conferir a
  SC-004.

## Pendências do Analyze

- **A1 (MEDIUM).** FR-007: um distrito do continente sem anúncios no snapshot fica sem região, e seus municípios
  não herdam da região (D3, R-001). Não ocorre em 2026-11. Recomendação: manter e registrar no converge.
- **A2 (MEDIUM).** A entrada da spec cita `territorial_inheritance = distrito|regiao`; o plano usa `origin_level`
  (D7, R-009). Recomendação: o autor confirma antes da T023; mudar o nome exigiria emendar o contrato.
- **A3 (MEDIUM).** R-007: pendência A1 da 011 (mediana `ALL` na freguesia) segue sem confirmação. Recomendação:
  confirmar com o autor; a regra atual é a convergida.
- **A4 (MEDIUM).** R-004: critério de aluguel sem nenhum valor próprio falha o build; a spec não trata o caso.
  Recomendação: manter.
- **A5 (LOW).** FR-010 lista três valores de cobertura e omite `regional_only`, que o plano mantém. Recomendação:
  nenhuma ação.
- **A6 (LOW).** A junção de distrito usa o nome do CAOP, não um código (constitution III fala em DICO/DICOFRE).
  Recomendação: aceitar, com a seed e a falha sem correspondência.
- **A7 (LOW).** SC-002 depende dos dados e só é verificada no quickstart. Recomendação: registrar os números na
  T031.

## Gate de pronto

- Contratos da 012 (5/5) e da 011 (5/5) verdes, com as duas travas íntegras.
- `uv run --locked ruff check pipelines tests` e `uv run --locked python -m pytest -q --basetemp .pytest_tmp`
  verdes.
- `uv run --locked python -m tests.fixtures.gold.ci_seed --root .data/ci-gold` (pasta vazia) e
  `uv run --locked python -m pipelines.cli.build_gold --local --root .data/ci-gold --criteria .data/ci-gold/criteria.yml`
  verdes.
- `uv run --locked python -m pipelines.cli.model_docs --check` verde, depois de regenerar.
- Build real e `quickstart.md` sem divergência.
- Polish: notebook (sem saídas), dicionário, runbook, README, §8.3 do plano do projeto, memória e backlog.
- Sem hardware nem UI: abrir o notebook é recomendação, não gate.
