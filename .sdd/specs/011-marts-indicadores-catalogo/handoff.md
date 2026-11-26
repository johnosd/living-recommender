# Handoff — 011-marts-indicadores-catalogo (sdd-plan → sdd-execute)

## Contexto

- **Repositório:** `J:\living-recommender`, branch `feature/010-visibilidade-modelo-dados`. Os arquivos
  desta feature ainda não foram commitados; considere abrir uma branch `feature/011-...` antes de começar.
- **Stack:** Python 3.12 (uv), pandas, pyarrow, dbt-core + dbt-duckdb, pytest e ruff. O lake é local, em
  `.data/lake`.
- **Próximo comando:** `/sdd-execute 011-marts-indicadores-catalogo`. No backlog, a feature está como
  **Planejada** (0/54).
- O `spec.md` e o `.planning/backlog.md` foram alterados no disco pelos scripts de status; releia-os, sem
  desfazer nada.

## O que a feature entrega

- **P1:** o perfil municipal longo (308 × critério × variante), com aluguel (IQR), clima (extremos e TCI) e
  mobilidade, mais o `criteria_catalog` versionado por hash, com P5/P95. Um critério disponível sem dado
  **falha o build**.
- **P2:** `gold_data_quality` (cobertura, período anterior, zeros por convenção, `stale`, outliers,
  pendentes).
- **P3:** o perfil de freguesia (`proprio`/`herdado`/`ausente`), com o herdado sendo cópia exata do
  município.
- **Decisões do autor que contrariam o óbvio:**
  - o período é o mais recente **do município** (com a bandeira `is_older_period`), e não um ano nacional
    único;
  - `-` vira **0 só em contagens** (`dash_is_zero`), com `value_status = zero_convencao_fonte`;
  - o TCI é validado **só por casos sintéticos**, sem comparação com o legado;
  - **sem** exportação `criteria.json`/`published/vN`, e **sem** S3.
- `distancia_sede_distrito_km` é `fonte_pendente` de propósito, porque não há polo de sede em
  `config/poles.yml` (R-002).

## Leitura obrigatória, em ordem

1. `spec.md`: FRs, ACs e Clarifications (as decisões de período e de outliers estão lá).
2. `plan.md`: Decisões Invariantes D1–D11, riscos R-001–R-011 e Estratégia de Testes.
3. `tasks.md`: as fases; os IDs T006, T008, T010–T014 e T030 são citados nos stubs.
4. `contracts/criteria-catalog.md`: o formato do YAML, a validação (o id vai **entre aspas simples** na
   mensagem de erro), `catalog_tables`, o hash da versão e a **tabela do catálogo inicial**, a transcrever
   para `config/criteria.yml` (T005).
5. `data-model.md`: as 9 tabelas Gold, as colunas e os códigos fechados.
6. `logic/indicadores.md` (período, `-`, denominador, mobilidade), `logic/clima.md` (faixas do TCI) e
   `logic/aluguel.md` (IQR, n ≥ 10, `rent_coverage`).
7. `research.md` (medições reais), `quickstart.md` (verificação) e `.planning/memory/constitution.md`.

## Testes de contrato

- `tests/contracts/test_gold_indicators_contract.py`: **5 funções, todas na Fase 3 (US1)**, travadas em
  `contract-tests.lock`. O script não conta testes pytest (R-011); a contagem manual dá 5.
- Rodar: `uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp`.
  Vermelho confirmado: 5 failed por `NotImplementedError`.
- Trava: `.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 011-marts-indicadores-catalogo`.
- **Travas de outras features em risco:** o T002 mexe em `pipelines/modeldocs/` (camada `gold`). O contrato
  travado da 010 (`tests/contracts/test_modeldocs_contract.py`) tem de continuar verde; ele só usa
  bronze/silver.

## Stubs criados

Todos levantam `NotImplementedError`, com a task na mensagem. As assinaturas são fixas, porque o contrato
as importa.

| Arquivo | Conteúdo |
| --- | --- |
| `pipelines/gold/__init__.py` | Só o docstring do pacote. |
| `pipelines/gold/criteria.py` | `CriteriaError(ValueError)`, `load_criteria(path)` e `catalog_tables(criteria, indicators_by_level)`, que devolve `(catalogo, normalizacao)`. |
| `pipelines/gold/observations.py` | `municipal_indicators(observations, municipalities, criteria)`. |
| `pipelines/gold/climate.py` | `climate_monthly(daily)` e `climate_indicators(daily, municipalities, criteria)`. |
| `pipelines/gold/rent.py` | `rent_stats(listings, municipalities)` e `parish_rent_stats(listings, parishes)`. |
| `pipelines/gold/mobility.py` | `mobility_indicators(distances, poles, municipalities, criteria)`. |

`common.py`, `parish.py`, `quality.py`, `prepare.py` e `pipelines/cli/build_gold.py` ainda não existem e são
criados no execute.

## Armadilhas já mapeadas

- **Os dicts de critério do contrato são completos.** O contrato passa `criteria` como dict, sem YAML. As
  funções de cálculo **não** devem exigir campos além dos do helper `criterion()` do teste, nem validar pesos
  (quem valida é `catalog_tables`). `compute` do tipo `{"kind": "observation"}` sem `dataset_id` aparece no
  teste do catálogo: `catalog_tables` não pode exigir `dataset_id`.
- **`municipal_indicators` só processa critérios `compute.kind == "observation"`.** O mesmo vale para
  mobilidade e clima: cada função ignora os outros `kind`.
- **`filters: [{}]` significa `filter_1 = filter_2 = filter_3 = ""`.** O dict é uma parte do numerador;
  várias partes são somadas, e se faltar uma parte o numerador é nulo.
- **Denominador do mesmo período.** No teste, 0101 tem população de 2023 e 2024; usar a de 2023 dá 4.0, e
  não o 2.0 esperado.
- **`dataset_latest_period` é calculado depois da regra do `-`.** É o máximo, entre todos os municípios, do
  período com numerador não nulo; é string (`"2024"`).
- **Motivos exatos:** `simbolo_fonte:-`, `simbolo_fonte:x`, `sem_publicacao`, `sem_denominador`,
  `sem_par_elegivel` e `par_falha`. O teste compara as strings.
- **TCI:** o legado usa a umidade **média** também no CIA; as comparações das faixas usam as médias cruas. O
  contrato testa as bordas exatas (`20`, `27`, `19.9`, `27.1`, umidade `30` e `90` sem penalidade, `29.9`
  com penalidade) e o clamp em 0.
- **Extremos:** desigualdade estrita (`35.0` não é calor, `35.1` é); `valid_days` conta os dias com
  `temperature_2m_max`.
- **Aluguel:** o IQR só existe com n ≥ 10 no grupo; o ALL exclui os outliers marcados no grupo da tipologia;
  as 6 linhas saem para todo município, inclusive sem anúncios. Os percentis são **lineares**
  (`numpy.percentile` padrão).
- **Mobilidade, polo mais próximo:** se algum par elegível estiver em `falha`/`pendente`, o resultado é
  ausente (não se escolhe outro). O identity com valor 0 é `observado`.
- **`catalog_version`** não pode incluir `processed_at_utc`. Mesmo input, mesma versão; mudou um peso ou
  um valor, muda a versão.
- **Seleção dbt sempre por tag** (`--select tag:gold`); um `dbt build` sem tag roda modelos de outras
  features sem as entradas. Passe `CAOP_DUCKDB_PATH` para dentro do candidato e `DBT_TARGET_PATH` como
  caminho absoluto, se for usá-lo (memória da 010).
- **Promoção:** só as `lake/gold/<tabela>`, nunca a pasta `gold/` inteira (`_promote.py`).
- **`model_docs --check` roda no CI.** Depois de criar os modelos e o `schema.yml`, regenere
  `.docs/modelo_de_dados.md`, ou o CI falha. Declare **todas** as colunas no `schema.yml`: o documento só
  conhece as declaradas.
- **Rótulos com NBSP:** `filter_1` das seções CAE vem como `"A. \xa0…"`. Normalize os espaços dos dois lados
  da comparação.
- **Idealista:** a freguesia resolvida está em `dicofre`, com `locality_level = municipio`. Não filtre por
  `locality_level = freguesia`, que só pega 3 anúncios.
- **Nunca rede.** O build Gold só lê o lake local.

## Pendências do Analyze

- **A1 (MEDIUM).** Aluguel `ALL` na freguesia: o plano dá mediana própria com n ≥ 10, mas o plano do
  projeto (§8.4) sugere "só €/m²" quando a tipologia não tem n. A spec (FR-029) só fala das tipologias.
  Recomendação: confirmar com o autor antes do T030/T031. Se ele preferir "só €/m²", mude só o
  `logic/aluguel.md` §4 (não há contrato nisso).
- **A2 (MEDIUM).** FR-007 fica parcial: a sede de distrito está pendente (R-002). Recomendação: registrar no
  converge como lacuna conhecida e levar ao backlog (T041).
- **A3 (MEDIUM).** Os pesos, as direções e as faixas do catálogo inicial são provisórios (R-003).
  Recomendação: revisão do autor antes da Fase 4.
- **A4 (LOW).** pandas e numpy são dependências transitivas (via geopandas), não declaradas. Recomendação:
  manter como está (o `build_mobility` já depende disso) ou declarar em `pyproject.toml` num commit
  separado.
- **A5 (LOW).** A spec escreve `disponível`/`fonte pendente`; os dados usam `disponivel`/`fonte_pendente`
  (D10). Recomendação: nenhuma ação; os rótulos para exibição ficam com a Fase 4.

## Gate de pronto

- Contrato: 5/5 verdes e `check-contract-tests.ps1 -Slug 011-marts-indicadores-catalogo` íntegro; os
  contratos travados de outras features também verdes.
- `uv run ruff check pipelines tests` e `uv run python -m pytest -q --basetemp .pytest_tmp` verdes.
- `uv run python -m tests.fixtures.gold.ci_seed --root .data/ci-gold` seguido de
  `uv run python -m pipelines.cli.build_gold --local --root .data/ci-gold --criteria .data/ci-gold/criteria.yml`
  verdes.
- `uv run python -m pipelines.cli.model_docs --check` verde, depois de regenerar o documento.
- Build real `uv run python -m pipelines.cli.build_gold --local --root .data` e consultas do `quickstart.md`
  §3 sem divergência.
- Documentação no Polish: `.docs/modelo_de_dados.md`, `.docs/runbooks/coletas.md`, README (se couber),
  nota em `.planning/memory/` e backlog (R-002, R-003).
- Não há hardware nem UI: a passada manual é só o quickstart §4 (recomendação, não gate).
