# Implementation Plan: Visibilidade do modelo de dados

**Slug**: `010-visibilidade-modelo-dados` | **Date**: 2026-11-22 | **Spec**: `.sdd/specs/010-visibilidade-modelo-dados/spec.md`

## Summary

O autor não enxerga as 25 tabelas do projeto nem como elas se ligam. A abordagem é tirar tudo de **um único
`dbt parse` do projeto inteiro** (verificado: ~4 s, sem lake, sem banco) e derivar três visões: (A) o documento
`.docs/modelo_de_dados.md` (diagrama Mermaid dos 15 relacionamentos declarados e dicionário de dados), gerado por
`model_docs` e conferido no CI; (B) um catálogo DuckDB único com views sobre o lake, metadados e o inventário do
`raw/`, gerado por `lake_catalog`; (C) o site do `dbt docs` com o grafo ligando as fontes aos modelos de outros builds,
gerado por `dbt_docs_site`. Em paralelo, preenche-se descrição, tipo e fonte das 18 tabelas principais nos
`schema.yml` (hoje 0 descrições de coluna), e a checagem de completude sai do próprio catálogo (`meta.columns`).

## Technical Context

**Language/Version**: Python 3.12 (`requires-python >=3.12,<3.13`), dbt Core 1.12.6, dbt-duckdb 1.11.1, duckdb (Python) 2.0.0

**Primary Dependencies**: já presentes no `pyproject.toml`: `dbt-core`, `dbt-duckdb`, `pyarrow`, `PyYAML`. **Nenhuma
dependência nova.**

**Storage**: leitura de `lake/{bronze,silver}/<tabela>/data.parquet` e `manifests/<fonte>/<run_id>.json`; escrita só de
`.docs/modelo_de_dados.md` (versionado), `.data/catalog.duckdb` e `.data/dbt-docs/` (ambos em `.data/`, fora do Git).

**Testing**: pytest (`tests/unit`, `tests/integration`, `tests/contracts`), ruff. O contrato usa o `dbt parse` real e
manifests sintéticos; o lake dos testes é minúsculo e fica em `tmp_path`.

**Target Platform**: máquina local do autor (Windows 11) e GitHub Actions (ubuntu). Sem AWS, sem servidor.

**Performance Goals**: N/A. Referência medida: `dbt parse` ~4 s; `dbt docs generate --empty-catalog` ~6 s.

**Constraints**: determinismo byte a byte do documento; LF sempre e conferência insensível a CRLF; caminhos do manifest
normalizados (barra invertida no Windows); o catálogo nunca escreve no lake nem nos manifests; site servido só em
`127.0.0.1`.

**Scale/Scope**: 25 modelos, 9 domínios, 15 relacionamentos, 2 fontes dbt, 43 manifests de coleta, 18 tabelas principais
(≈345 colunas) a descrever.

## Decisões Invariantes

- **D1. Fonte única**: o `manifest.json` do `dbt parse` do projeto inteiro alimenta as três visões. Nenhum SQL é
  parseado e nenhum arquivo do lake é lido para gerar o **documento**.
- **D2. Documento só com estrutura**: colunas e tipos são os **declarados** no `schema.yml`; sem contagens, amostras,
  datas, `run_id` nem caminhos locais. O que existe de fato no lake aparece só no catálogo (B) e no `catalog.json` (C).
- **D3. Relacionamento = teste `relationships` declarado.** A fonte `source('s','t')` resolve para o modelo `t`; alvo
  sem modelo é `ModelError` (arquivo, modelo, alvo). Chave `dico`/`dicofre` sem relação vira lacuna, nunca aresta.
- **D4. Formato do documento fixado em `logic/documento.md`** e nos contratos travados; gravação com LF; `--check`
  ignora `\r\n`; todo caminho normalizado para `analytics/dbt/...` com `/`.
- **D5. Catálogo = views**: `CREATE VIEW ... read_parquet('<abs>')` em `bronze` e `silver`, metadados em `meta`;
  geração em arquivo temporário e `os.replace`; só `<camada>/<tabela>/data.parquet` é tabela, o resto do lake é
  ignorado e listado; modelo sem parquet = `nao_construida`, parquet sem modelo = `sem_modelo`, nunca falha.
- **D6. Inventário do `raw/`** = uma linha por manifest legível; `checksums` por varredura da chave `sha256`.
- **D7. Site**: `dbt docs generate --empty-catalog` com `DBT_TARGET_PATH` e `CAOP_DUCKDB_PATH` dentro da pasta de saída
  (nunca no `.data/ci` do projeto); manifest com `link_sources_to_models`; `catalog.json` do lake quando houver;
  `--serve` só em `127.0.0.1`; saída `.data/dbt-docs`.
- **D8. Principal × relatório** por nome (`rpt_*` ou `*_coverage` = relatório). A completude do US3 é verificada para
  **uma lista fixa** das 18 tabelas principais de hoje, sem gate para modelos novos (decisão do autor).
- **D9. Descrição só com evidência**: o texto de cada descrição vem do SQL do modelo, do coletor, dos docs
  (`.docs/fontes_de_dados.md`) ou das specs. Se não houver evidência, a coluna fica **sem descrição** (constitution III);
  nunca um palpite.
- **D10. Comandos**: `uv run --locked python -m pipelines.cli.{model_docs,lake_catalog,dbt_docs_site}`, no padrão dos
  `build_*` existentes; `dbt` chamado por `subprocess` com `shutil.which("dbt")`, como `build_mobility.py`.

## Constitution Check

*GATE: deve passar antes da Fase 0. Reavaliado após o design da Fase 1.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | ✅ | ✅ | Nenhuma chave é lida. O documento só tem estrutura; o catálogo e o site ficam em `.data/` (ignorado). O gitleaks do CI continua passando (SC-008). |
| II. Núcleo do produto estático e sem chave | ✅ | ✅ | Artefatos de apoio ao autor; nada entra em `published/vN` nem exige servidor. O `--serve` é local e opcional. |
| III. Dados honestos e rastreáveis | ✅ | ✅ | "Sem descrição" é explícito (FR-018); D9 proíbe descrição sem evidência; as lacunas aparecem no documento; licença e atribuição por fonte vêm de `config/sources.yml`. |
| IV. Coleta responsável e licenciada | ✅ N/A | ✅ N/A | Nenhuma coleta nova. |
| V. Bruto imutável e publicação atômica | ✅ | ✅ | `raw/`, `lake/` e manifests só são lidos; o contrato 5 prova com hash antes/depois. O catálogo é gravado em temporário + `os.replace`. |
| VI. Privacidade por padrão | ✅ | ✅ | O documento versionado não leva valores; o catálogo pode conter dados do lake, mas vive em `.data/`. Nenhum rastreamento. |
| VII. Custo como requisito | ✅ | ✅ | US$ 0 recorrente: sem AWS, sem API paga, ~MB de disco local. |

Quality Gates: (1) ruff e pytest no CI ✅; (2) N/A, sem coletor; (3) modelos dbt alterados só em `description`,
`data_type` e `meta` (nenhum SQL, nenhum teste removido); `dbt build` dos 8 domínios continua verde no CI ✅;
(6) documentação acompanha: runbook, README e `.docs/modelo_de_dados.md` ✅; (7) commits curtos em inglês ✅.

## Project Structure

### Documentation (this feature)

```text
.sdd/specs/010-visibilidade-modelo-dados/
├── spec.md
├── plan.md
├── research.md            # decisões verificadas em 2026-11-22
├── data-model.md          # estruturas, catálogo DuckDB e mudanças nos schema.yml
├── quickstart.md
├── handoff.md
├── contract-tests.lock
├── contracts/cli.md       # as 3 CLIs
├── logic/documento.md     # manifest -> documento (formato fixado pelos contratos)
├── logic/site.md          # manifest com fontes ligadas e catalog.json
└── tasks.md
```

### Source Code (repository root)

```text
pipelines/
├── cli/
│   ├── model_docs.py          # NOVO (stub): documento A
│   ├── lake_catalog.py        # NOVO (T010): catálogo B
│   ├── dbt_docs_site.py       # NOVO (T022): site C
│   └── build_*.py, collect_*.py   # existentes; padrão de CLI e de chamada ao dbt
└── modeldocs/                 # NOVO pacote
    ├── model.py               # stub: DataModel, load_model, run_dbt_parse
    ├── render.py              # stub: load_sources_info, render_markdown
    ├── catalog.py             # stub: build_catalog
    └── site.py                # stub: link_sources_to_models, lake_catalog_json
analytics/dbt/models/<domínio>/schema.yml   # ALTERADO (US3): description, data_type, meta.source_ids
config/sources.yml                           # só leitura (licença e atribuição)
.docs/modelo_de_dados.md                     # NOVO, gerado e versionado
.docs/runbooks/                              # seção nova (DuckDB UI, DBeaver, dbt docs)
.github/workflows/python.yml                 # passo novo: model_docs --check
tests/
├── contracts/test_modeldocs_contract.py     # TRAVADO (5)
├── fixtures/modeldocs/{manifests,lake}.py   # TRAVADOS
├── unit/test_modeldocs_*.py                 # NOVOS (executor)
└── integration/test_modeldocs_*.py          # NOVOS (executor)
```

**Structure Decision**: pacote próprio `pipelines/modeldocs/` (lógica pura e testável) com CLIs finas em
`pipelines/cli/`, igual ao par `pipelines/collectors/mobility/` + `pipelines/cli/*_mobility.py`. As descrições ficam nos
`schema.yml` existentes de cada domínio, sem arquivo de metadados paralelo.

## Complexity Tracking

Sem violações do Constitution Check. Dois pontos fora do usual, ambos sem violar princípio:

| Ponto | Por que é necessário | Alternativa mais simples rejeitada porque |
| --- | --- | --- |
| `link_sources_to_models` altera `parent_map`/`child_map` do manifest só na cópia do site | o dbt não liga a fonte `caop_silver.X` ao modelo `X` de outro build; sem isso o grafo da US4 não mostra a dependência | usar o grafo padrão (nós de fonte soltos) não cumpre SC-006; R-002 registra o risco e o fallback |
| `catalog.json` escrito por nós a partir do lake | o `docs generate` completo exige um banco único que não existe | deixar o catálogo vazio perde os tipos reais e as colunas não declaradas |

## Estratégia de Testes

Prioridade: unitário → contrato/integração → manual (só o grafo no navegador).

Comandos-base:

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp
uv run --locked python -m pytest -q --basetemp .pytest_tmp
uv run --locked python -m pipelines.cli.model_docs --check
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 010-visibilidade-modelo-dados
```

Em ambiente com permissão restrita ao `%TEMP%` do pytest, use `--basetemp` dentro do repositório (já ignorado em
`.pytest_tmp`) ou na área temporária da sessão.

### Testes de Contrato

Arquivos travados em `contract-tests.lock`: `tests/contracts/test_modeldocs_contract.py`,
`tests/fixtures/modeldocs/manifests.py`, `tests/fixtures/modeldocs/lake.py`.

Comando: `uv run --locked python -m pytest tests/contracts/test_modeldocs_contract.py -q --basetemp .pytest_tmp`

| Teste | Origem | Fase | Vermelho esperado (antes do execute) |
| --- | --- | --- | --- |
| `test_the_document_is_complete_deterministic_and_free_of_values_and_local_paths` | US1-AC1, AC2, AC5; FR-001, FR-002, FR-005, FR-006; SC-001 | Fase 2 | `NotImplementedError: T001: load_model` |
| `test_gaps_are_explicit_never_invented_and_territorial_keys_without_a_relationship_are_listed` | US1-AC3; FR-003, FR-018; Constitution III | Fase 2 | `NotImplementedError: T001: load_model` |
| `test_a_relationship_to_a_table_that_does_not_exist_fails_naming_file_model_and_target` | FR-009 | Fase 1 | `NotImplementedError: T001: load_model` |
| `test_check_mode_flags_a_stale_document_names_the_regenerating_command_and_ignores_line_endings` | US1-AC4; FR-008; armadilha CRLF | Fase 2 | `NotImplementedError: T005: model_docs.main` |
| `test_the_catalog_exposes_every_lake_table_without_copying_or_touching_the_lake` | US2-AC1, AC2, AC3, AC5, AC6, AC7; FR-010, FR-011, FR-013, FR-014, FR-015; SC-004, SC-005; Constitution V | Fase 3 | `NotImplementedError: T001: load_model` (o teste chama `load_model` antes de `build_catalog`) |

Cobertura sem contrato (testes comuns do executor): US3 (completude das 18 tabelas) e US4 (`link_sources_to_models`,
`lake_catalog_json`, CLI do site), o inventário `raw_runs` em detalhe e a normalização de caminhos do Windows.

Stubs criados pelo plan (ponto de partida, não travados): `pipelines/modeldocs/{__init__,model,render,catalog,site}.py`,
`pipelines/cli/model_docs.py`.

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. Vazia na criação. -->

| Área | Estado |
| --- | --- |
| Fase 1 (Foundational) | Concluída: `load_model`, `run_dbt_parse`, `load_sources_info` |
| Fase 2 (US1 documento) | Concluída: `render_markdown`, CLI `model_docs`, documento gerado, passo no CI, runbook (seção do documento) |
| Fase 3 (US2 catálogo) | Concluída: `build_catalog`, CLI `lake_catalog`, runbook do catálogo |
| Fase 4 (US3 descrições) | Concluída, aguardando revisão dos textos pelo autor (R-007): 18 principais com descrição, tipo e fonte em todas as colunas |
| Fase 5 (US4 site do dbt) | Implementada: `site.py`, CLI `dbt_docs_site`, runbook; gate visual do grafo pendente (T027/R-002) |
| Polish | T025 feito; T026 parcial (revalidado em 2026-11-24: suíte 775 passed, ruff, `--check`, trava OK; `dbt build` dos domínios OK em 2026-11-22; falta o CI remoto); T027 pendente |
| Contratos | 5/5 verdes; trava íntegra |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | O manifest só conhece as colunas declaradas; hoje o `schema.yml` declara de 2 a 13 colunas por tabela e o lake tem de 8 a 39. Sem declarar todas, o dicionário fica parcial sem avisar. | Alto | Fase 4 declara todas as colunas das 18 principais. `meta.columns` (`declared = false`) é a prova de completude; relatórios ficam com a observação "lista possivelmente incompleta". |
| R-002 | O dbt docs pode não desenhar a aresta fonte→modelo criada em `parent_map`/`child_map` (comportamento não documentado). | Médio | Conferência manual no `quickstart.md`. Fallback: dizer na descrição da fonte qual modelo a produz. |
| R-003 | O Windows não substitui um `.duckdb` aberto no DBeaver ou no DuckDB UI. | Baixo | Geração em temporário + `os.replace`; se falhar, mensagem pedindo para fechar o cliente e o catálogo anterior continua intacto. |
| R-004 | As views guardam o caminho absoluto dos parquets; mover `.data/` quebra o catálogo. | Baixo | Basta gerar de novo; está no runbook. |
| R-005 | Mudança de versão do dbt pode alterar o formato do manifest. | Médio | `uv.lock` fixa o dbt; o contrato 1 roda o `dbt parse` real e acusa quebra no CI. |
| R-006 | CRLF do Windows vs LF do CI fariam o `--check` divergir. | Médio | Gravar sempre com LF e comparar ignorando `\r\n`; coberto pelo contrato 4. |
| R-007 | Escrever ~345 descrições é trabalho de conteúdo; descrição errada é pior que nenhuma (constitution III). | Alto | D9: só com evidência do SQL, do coletor ou dos docs; sem evidência, fica "sem descrição". Revisão do autor ao fechar a Fase 4. |
| R-008 | O `data_type` declarado pode divergir do tipo real depois de uma mudança no SQL, sem ninguém notar. | Baixo | `meta.columns` compara `type_declared` e `type_actual`; a Fase 4 zera as divergências. Sem gate de CI (decisão do autor). |
| R-009 | O documento ficará com muitas lacunas "chave territorial sem relacionamento" (ex.: `census_observation.dico`, `stg_caop_*`). | Baixo | É o efeito desejado: tornar as lacunas visíveis. Declarar os testes que faltam é decisão futura, fora desta spec. |
| R-010 | O `dbt docs generate` abre uma conexão DuckDB mesmo com `--empty-catalog`. | Baixo | `CAOP_DUCKDB_PATH` aponta para a pasta de saída (D7); verificado em 2026-11-22 que nada é criado em `.data/ci`. |
| R-011 | A asserção `".data" not in document` do contrato 1 (feita para barrar o caminho `.data/`) casa com qualquer lacuna de coluna chamada `dataset_id` (`- tabela.dataset_id`). Descoberto na Fase 2. | Médio | Contornado com dados, não com código: `stg_observation.dataset_id` e `rpt_observation_coverage.dataset_id` ganharam `description` (evidência no SQL). **Frágil**: uma futura coluna `data*` sem descrição reprova o contrato. Emenda sugerida ao autor: trocar a asserção por `.data/`. Contrato não editado. |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-22 | Fase 1 (Foundational) | `load_model`/`run_dbt_parse`/`load_sources_info`; 8 testes unitários; contrato FR-009 verde. | Nenhuma |
| 2026-11-22 | Fase 2 (US1) | `render_markdown`, CLI, `.docs/modelo_de_dados.md` (25 tabelas, 15 arestas), passo no CI, runbook; 3 contratos verdes; 9 testes unitários. | R-011 (contrato casa `dataset_id`) |
| 2026-11-22 | Fase 3 (US2) | `build_catalog`, `meta.raw_runs`, CLI `lake_catalog`, runbook; catálogo real com 25 tabelas ok e 43 manifests; 10 testes novos. | Abertura no DBeaver/UI não exercitada no navegador |
| 2026-11-22 | Fase 4 (US3) | 18 tabelas principais: descrição de tabela, `meta.source_ids` e 364 colunas com `description` e `data_type` (9 `schema.yml`); consulta de completude → 0 linhas; documento regerado (principais 100%). | Revisão humana dos textos (R-007) |
| 2026-11-22 | Fase 5 (US4) + Polish | `site.py` e `dbt_docs_site` (aresta fonte→modelo, catálogo do lake, `--serve` em 127.0.0.1); README, memória; suíte completa 773 passed; `dbt build` dos domínios OK. | Gate visual (R-002), revisão dos textos (R-007) e CI remoto |
| 2026-11-24 | Polish (revalidação) | Trava íntegra, ruff limpo, `model_docs --check` exit 0, suíte completa 775 passed; nada mudou no código. | Commit/push/PR para o CI remoto; T027; R-007 |

**PRÓXIMO**: commit na branch `feature/010-visibilidade-modelo-dados`, push e PR para o CI remoto (T026); o autor confere o grafo no navegador (T027) e revisa as descrições (R-007); então `sdd-converge`

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint — foco da etapa atual, não a árvore inteira. -->

- `pipelines/modeldocs/{model,render}.py`, `pipelines/cli/model_docs.py` (prontos)
- `pipelines/modeldocs/catalog.py`, `pipelines/cli/lake_catalog.py` (prontos)
- `.data/catalog.duckdb` (gerado; `meta.columns` lista as colunas reais para a Fase 4)
- `.docs/modelo_de_dados.md` (gerado), `.docs/runbooks/modelo_de_dados.md`, `.github/workflows/python.yml`
- `analytics/dbt/models/*/schema.yml` (Fase 4, prontos)
- `pipelines/modeldocs/site.py`, `pipelines/cli/dbt_docs_site.py` (prontos)

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- Heredoc do shell com aspas triplas e `['"]` corrompe a gravação de arquivos Python: use a ferramenta de escrita.
- Toda mudança em `schema.yml` exige `uv run --locked python -m pipelines.cli.model_docs` e commit do documento, senão o `--check` do CI falha.
- `DBT_TARGET_PATH` relativo é resolvido a partir de `analytics/dbt/`: use caminho absoluto (a CLI do site faz `.resolve()`).
- O tipo `NULL` de coluna toda nula vem do DuckDB como `"NULL"`; o catálogo tira as aspas.
- `executemany` do DuckDB falha com lista vazia: use `_insert_many` em `catalog.py`.
- O contrato 1 proíbe a substring `.data` no documento: cuidado com colunas `data*` sem descrição (R-011).
