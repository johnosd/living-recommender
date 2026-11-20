# Implementation Plan: Ingestão Wikipedia

**Slug**: `008-ingestao-wikipedia` | **Date**: 2026-11-20 | **Spec**: `.sdd/specs/008-ingestao-wikipedia/spec.md`

## Summary

Adicionar uma fonte local de textos enciclopédicos para os 308 municípios,
com correspondências curadas por DICO, identidade/revisão verificáveis,
originais imutáveis, texto integral estruturado e prontidão nacional honesta.
O fluxo reutiliza a arquitetura Python → Parquet preparado → dbt por tag →
promoção de candidato do projeto. Texto inglês, mídia, declarações Wikidata,
legado, publicação, agendamento e AWS ficam fora. Cinco contratos executáveis
e stubs fixam as fronteiras antes da implementação.

## Technical Context

**Language/Version**: Python >=3.12,<3.13, `uv.lock`, PowerShell para gates SDD.

**Primary Dependencies**: httpx >=0.28,<1, PyYAML >=6,<7, pyarrow >=20,<25,
pandas já usado pelas pipelines, dbt-core/dbt-duckdb >=1.9,<2. Adicionar
beautifulsoup4 >=4.14,<5 no execute; parser explícito html.parser/Python 3.12.
Não acrescentar requests, Spark, banco ou serviço. A versão instalada de cada
dependência continua determinada pelo lock, sem atualização geral.

**Storage**: LocalStorage existente; raw/manifests imutáveis, contexto congelado,
schemas Parquet explícitos e diretórios exclusivos Wikipedia. Interface de
storage injetável não implica entrega em S3 real. Sem ler/regravar bases legadas.

**Testing**: pytest >=8,<10; fixtures sintéticas/MemoryStorage existentes;
HTTP com MockTransport; Ruff; dbt em candidato e banco isolados. Nenhuma rede
nos testes. Contratos sem parametrização/skip/xfail: cinco casos efetivos.

**Target Platform**: CLI local Windows/PowerShell e CI Linux. Backend futuro
compatível com a direção ADR-001/002, sem implantação nesta feature.

**Performance Goals**: 308 unidades, requisições seriais com intervalo mínimo
1 s; processar um artigo por vez sem manter HTML nacional inteiro em memória.
Timeout 30 s, até 3 tentativas/request e checkpoints. Tempo real será medido,
não há promessa de caber em Lambda nem SLA de duração nacional.

**Constraints**: fonte read-only, idioma pt, revisão exata, nenhuma inferência
territorial por nome ou associação automática a homônimos. Preservar dados das
sete fontes existentes. R-001 é exceção aprovada, não permissão de contorno.

**Scale/Scope**: 308 municípios em produção; catálogo alternativo explícito
para universos pequenos de fixture. Cinco modelos, dois comandos, um CSV
curado, um schema de manifest próprio e relatórios privados.

**Cost**: US$ 0/mês em novos serviços/API paga; execução e armazenamento locais
existentes. Nenhum recurso cloud nem credencial são criados. Volume/tempo
reais serão medidos na prova; eventual operação cloud exige outro planejamento.

## Decisões Invariantes

- **D1 — Escopo aprovado:** pt + ligação en/QID como metadados. Nada de texto
  inglês, declarações Wikidata, mídia, IA, backfill, frontend ou agendamento.
- **D2 — Identidade curada:** `config/wikipedia_articles.csv`, um DICO por
  linha; page ID + escopo/evidência revisável. Nome/QID isolados não bastam.
  Evidência retirada ou destino alterado exige revisão, sem autoaprovação.
- **D3 — API e exceção:** só Action API oficial de leitura, GET query/parse,
  conforme autorização R-001. Respeitar bloqueios reais e espera; sem proxy,
  troca de identidade ou endpoint para evitar restrição. Revalidar termos/licença.
- **D4 — Revisão coerente:** query identifica a revisão; parse usa oldid
  fixado. IDs precisam conferir. Guardar ambas as respostas, com metadados
  observados distintos da revisão. Revalidar conteúdo renderizado também.
- **D5 — API atual:** usar tocdata; aceitar sections em entradas históricas/
  fixtures. Mudança de HTML/índice sem tratamento completo reprova extração.
- **D6 — Corpo editorial:** lead separado e percurso por ordem/hierarquia;
  parágrafos/listas/tabelas/legendas/referências sem duplicação de folhas,
  fronteira de seção explícita. Nenhum find_next global nem classificação por IA.
- **D7 — Contexto fixo:** deep-copy catálogo, dimensão e associação por
  invocação/ciclo. Atualizações externas só na próxima execução padrão;
  verificar hashes físicos antes/depois e bloquear mistura de versões.
- **D8 — Estado próprio:** manifest Wikipedia v1; não modificar resolvedor
  v2/coletores antigos para encaixar ausência editorial e última tentativa.
- **D9 — Atualidade e retomada:** default verifica todas as unidades;
  resume usa contexto congelado e só conclui pendências do mesmo ciclo.
  Histórico válido não mascara falha recente. Toda ausência requer evidência.
- **D10 — Idempotência:** fingerprints editoriais/contextuais e hashes dos
  bytes separados. Reusar role idêntico; não promover mesmo processing_signature.
  Nova verificação tem recibo fora do lake sem fingir nova revisão editorial.
- **D11 — Transformação:** Python normaliza DOM para Parquet; dbt Core/DuckDB
  valida/exporta cinco modelos com tag wikipedia. Não trocar motor do ADR-001.
- **D12 — Proteção local:** lock por fonte/build, candidatos confinados,
  journal/hash/backup e recuperação explícita. Não prometer atomicidade de
  vários diretórios apenas por usar promote_paths. Nunca tocar bronze/silver inteiros.
- **D13 — Aceite:** 308 linhas de cobertura, valid ou absent comprovado;
  erro técnico/identidade pendente/perda textual bloqueia. Provas simulada,
  local real e CI remoto permanecem separadas.

## Constitution Check

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Nenhum segredo fora do cofre | Conforme | Conforme | API pública sem chave; contato não secreto; não coletar cookies/credenciais/nomes de editores. Scan de segredos do CI preservado. |
| II. Núcleo estático e sem chave | Conforme | Conforme | Apenas dados locais; nenhuma API de produto ou dependência do navegador. |
| III. Dados honestos e rastreáveis | Conforme | Conforme | DICO + curadoria, revisão/bytes, estados explícitos e gate; nenhuma imputação ou estatística substituída. |
| IV. Coleta responsável e licenciada | Exceção aprovada R-001 | Exceção aprovada R-001 | Autor aprovou uso específico da API apesar de Disallow:/w/; risco registrado, identificação/limite/espera obrigatórios. Licença textual verificada via rightsinfo; conferir atribuição adicional. |
| V. Bruto imutável/publicação atômica | Conforme | Conforme | Bytes e manifests imutáveis; candidato validado, journal/rollback; nenhuma alteração em published/current.json. |
| VI. Privacidade por padrão | Conforme | Conforme | Sem preferências, dados pessoais de anúncios, métricas de visitante ou chamadas de frontend. Conteúdo bruto privado fora do Git. |
| VII. Custo como requisito | Conforme | Conforme | Nenhum serviço ou API pagos; sem Terraform/deploy no escopo local aprovado. |

ADRs 001/002 lidos integralmente; ADR-003 conferido e sem credencial nova.
Orquestração/delivery futura não são relitigadas. A exceção pontual prevista
no princípio IV não altera a constitution nem autoriza outras fontes/endpoints.

## Project Structure

### Documentation (this feature)

```text
.sdd/specs/008-ingestao-wikipedia/
  spec.md                  # existente; só status atualizado pelo script
  plan.md
  tasks.md
  research.md
  data-model.md
  contracts/wikipedia-cli.md
  logic/coleta-e-texto.md
  quickstart.md
  contract-tests.lock
  handoff.md
```

### Source Code (repository root)

```text
config/sources.yml                          # existente; cadastrar no execute
config/wikipedia_articles.csv               # novo no execute
pipelines/collectors/_shared/                # existente; reusar sem mudar semântica
pipelines/collectors/wikipedia/
  __init__.py, handler.py, extract.py, coverage.py  # stubs atuais
  catalog.py, identity.py, fetch.py           # novos no execute
  manifest.py, state.py, prepare.py           # novos no execute
pipelines/cli/
  _common.py, _promote.py                     # existentes; reuso delimitado
  collect_wikipedia.py, build_wikipedia.py    # novos no execute
analytics/dbt/
  dbt_project.yml, profiles.yml              # existentes; adicionar só tag/config necessária
  models/wikipedia/                          # novo no execute
    wikipedia_revision.sql, wikipedia_article.sql
    wikipedia_section.sql, wikipedia_block.sql, wikipedia_coverage.sql
    schema.yml
  tests/wikipedia_integrity.sql, wikipedia_coverage.sql  # novos
tests/contracts/test_wikipedia_contract.py   # novo e travado agora
tests/fixtures/wikipedia/responses.py         # novo e travado agora
tests/fixtures/wikipedia/ci_seed.py           # novo no execute, não travado
tests/unit/test_wikipedia_{catalog,identity,http,state,extract,coverage}.py # futuros
tests/integration/test_wikipedia_{collect,build,cli}.py                  # futuros
.github/workflows/python.yml                 # existente; acrescentar fixture/dbt da tag
.docs/fontes_de_dados.md, .docs/runbooks/coletas.md, README.md # existentes
```

**Structure Decision:** mesma separação por fonte e CLI/modelos/testes do
checkout real. Caminhos marcados como futuros não existem ainda. Modelos
ficam em models/wikipedia para não herdar a tag observations de models/bronze.
Storage de origem usa layout raw/manifests existente e namespace exclusivo.

## Complexity Tracking

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |
| Exceção pontual ao robots, princípio IV | API oficial de leitura é a origem escolhida; autor aprovou risco específico em 2026-11-20, R-001 | Dumps demandariam avaliar outra origem; ignorar robots silenciosamente não seria aceitável. |

Demais decisões não violam a constitution. Manifest próprio e journal evitam
estender incorretamente estados/promoções das fontes já convergidas.

## Estratégia de Testes

Prioridade: unitário → contrato/integração → CLI/dbt offline → prova real
automatizada → inspeção humana da curadoria. Nenhuma execução em hardware
especial, browser ou cloud é gate desta feature.

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -q --basetemp .data/tmp/wiki-contracts
uv run --locked python -m pytest tests/unit tests/integration -k wikipedia -q --basetemp .data/tmp/wiki-area
uv run --locked python -m pytest -q --basetemp .data/tmp/wiki-full
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .planning/scripts/powershell/check-contract-tests.ps1 -Slug 008-ingestao-wikipedia
uv run --locked python -m tests.fixtures.wikipedia.ci_seed --root .data/ci-wikipedia
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data/ci-wikipedia
```

O comando de área usa `-k wikipedia`, sem depender de expansão de globs de
arquivos no PowerShell.

Build efetivo após implementação:

```powershell
$env:WIKIPEDIA_BUILD_DIR = '.data/ci-wikipedia'
$env:WIKIPEDIA_PREPARED_DIR = '.data/ci-wikipedia/prepared'
$env:OBS_SILVER_DIR = '.data/ci-wikipedia/lake/silver'
$env:CAOP_DUCKDB_PATH = '.data/ci-wikipedia/wikipedia.duckdb'
$env:DBT_TARGET_PATH = '.data/ci-wikipedia/dbt-target'
$env:DBT_LOG_PATH = '.data/ci-wikipedia/dbt-logs'
uv run --locked dbt build --project-dir analytics/dbt --profiles-dir analytics/dbt --target local --select tag:wikipedia
```

Usar variáveis somente na sessão/processo de fixture. O build CLI prepara o
candidato e define seus caminhos isolados; não rodar dbt genérico sobre lake real.

### Testes de Contrato

Travados: `tests/contracts/test_wikipedia_contract.py` e
`tests/fixtures/wikipedia/responses.py`. Reutiliza MemoryStorage de
`tests/fixtures/open_meteo/responses.py`, já protegido pela feature 003.

| Teste | Origem | Fase | Vermelho confirmado |
| --- | --- | --- | --- |
| test_us1_fr004_fr008_fr009_pinned_identity_and_immutable_raw | US1/AC1; FR-004/008/009; Constitution III/V | 3 | NotImplementedError: 008: collect_wikipedia |
| test_us1_ac2_ac4_fr006_fr009_invalid_identity_revision_and_api_error_do_not_become_state | US1/AC2/4; FR-006/009/018 | 3 | NotImplementedError: 008: collect_wikipedia |
| test_us3_fr019_fr020_fr021_catalog_and_mapping_are_frozen_and_rechecked | US3/AC1–3; FR-019/020/021 | 5 | NotImplementedError: 008: collect_wikipedia |
| test_us2_fr010_fr011_fr012_fr013_complete_sections_keep_boundaries_and_nested_context | US2/AC1–6; FR-010–013; Constitution III | 4 | NotImplementedError: 008: extract_article |
| test_us4_fr025_fr026_fr027_fr028_readiness_rejects_loss_and_latest_failure | US4/AC1/3/4; FR-025–028 | 6 | NotImplementedError: 008: assess_wikipedia_coverage |

Comando real de confirmação: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -q --tb=short --basetemp .data/tmp/wiki-plan-red-20261120`
→ **5 failed/0,19 s**, todas por stubs; coleta `--collect-only -q` → 5 testes.
Ruff global aprovado. Baseline antes dos stubs: contratos antigos + unidades
compartilhadas → 63 passed/6,47 s; mesma área após os stubs → 63 passed/7,34 s.
A versão final do contrato também falhou 5/5 apenas por NotImplementedError,
em 0,18 s; o terceiro caso inclui mutação do catálogo e das associações pelo
chamador. Oito travas conferidas, todas íntegras.

O script PowerShell grava/confere SHA-256 normalizado, mas não possui adaptador
Python para contar testes/desabilitações: total unknown é limitação explícita.
Contar via pytest e auditar AST/markers; proibir skip/xfail/parametrização nos
cinco casos. Não alterar o script compartilhado neste escopo.

Stubs não travados: handler.collect_wikipedia, extract.extract_article e
coverage.assess_wikipedia_coverage. Não tornar testes verdes com retorno fixo,
mock da própria unidade, lógica de fixture ou supressão de NotImplementedError.

## Estado Atual

| Área | Estado |
| --- | --- |
| Implementação | Setup, fundação e quatro stories concluídos; aceite local completo |
| Testes locais | 543 pytest/433,90 s; Ruff; 5 contratos/8 travas; dbt fixture e nacional: 5 modelos + 30 testes |
| Nacional | 308 valid, 7.028 seções, 248.931 blocos, 6.699.736 caracteres; 308 introduções/QIDs/ligações inglesas |
| Repetição | 308 unchanged; 616 raw antes/depois; build unchanged; lake idêntico |
| Preservação | 616 referências verificadas; 1.319 arquivos anteriores intactos, incluindo 308 TXT e notebook |
| Release formal | 43/43 checkboxes; T035 e checklist remoto aprovados; Implementada |
| Entrega Git | Branch feature/008-ingestao-wikipedia publicada; PR #9 sobre feature/007 (42a5f59); implementação 5f8c72f aprovada no run 44809254508 |
| CI remoto | Quality e secrets aprovados: 542 passed/1 skipped no Linux, Ruff e sete builds isolados; CI do fechamento documental consultável nos checks do head final do PR |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | API oficial sob regra geral Disallow:/w/ do robots | Gate IV | Autor autorizou explicitamente exceção específica em 2026-11-20, resposta estruturada; só query/parse, read-only, identificação, série/limite e sem contorno. Revalidar se mudar endpoint/política. |
| R-002 | Curadoria nacional não pronta; artigo cidade/município ambíguo | Alto | Resolvido localmente: 308 associações curadas por agente e confirmadas na coleta; nenhuma ausência presumida. T010 revisa 308 associações; trecho/evidência/escopo verificáveis; ausência não pode mascarar trabalho pendente. |
| R-003 | Mesma revisão renderiza dependências diferentes | Alto | Reconsultar parse, fingerprint do conteúdo e originais; build offline a partir de bytes fixados. |
| R-004 | DOM/índice ou parser muda e perde texto | Alto | tocdata atual, fixtures sections compatíveis, auditoria de nós/headings e falha de completude; versionar regras/parser. |
| R-005 | Estado anterior esconde falha atual | Alto | Última tentativa separada do conteúdo válido, default reprova parcial, fallback só por run explícito e sinalizado. |
| R-006 | Licença/atribuição adicional ignorada | Alto | rightsinfo e termos verificados; preservar avisos e metadados; mídia/publicação fora. |
| R-007 | Queda do processo entre trocas/lock preso no Windows | Alto | Journal, backups/hashes, destinos confinados, inspeção PID e recuperação antes de novo build. |
| R-008 | Reuso genérico aceita estados API incorretos | Alto | Validador/estado/fetcher próprios; preservar contratos das fontes antigas. |
| R-009 | CI remoto exige autorização para entrega Git | Gate de release | Resolvido: autorização explícita do autor em 2026-11-20; branch 008, commit/push e PR #9 sobre feature/007; quality/secrets aprovados no run 44809254508 para 5f8c72f. Checks do fechamento documental ficam no head final do PR. |
| R-010 | Script de trava não conta Python | Médio | Hash do script + contagem real pytest de cinco casos + auditoria AST sem skip/xfail. |
| R-011 | load_catalog validava qualquer fonte nova como CAOP | Integração | Resolvido: despacho explícito para o validador próprio Wikipedia; métodos/semânticas das fontes antigas preservados; 34 testes compartilhados verdes. |
| R-012 | Espaços inseridos por markup e citações quebravam evidências curatoriais | Identidade | Resolvido: normalização específica de pontuação/parênteses e marcadores de referência; palavras alteradas continuam reprovando. Raw e texto editorial conservam referências; 308 identidades revalidadas. |
| R-013 | Windows pode manter handle de processo já encerrado | Recuperação | Resolvido: consultar GetExitCodeProcess/STILL_ACTIVE; teste encerra subprocesso abruptamente e recupera lock/journal sem apagar vizinhos. |
| R-014 | Mudanças de código/SQL durante build poderiam misturar regras | Integridade | Resolvido: dependências incluem módulos/SQL e são conferidas após preparo/dbt e na promoção. Primeiro build nacional foi bloqueado ao detectar edição concorrente; candidato não promovido. |
| R-015 | Teste unitário antigo enumerava exatamente sete fontes | Regressão | Resolvido: enumerar as oito fontes reais mantendo igualdade estrita. Arquivo unitário não travado; contratos e locks não alterados. |
| R-016 | Tabelas de layout/blockquote abrangem várias seções em quatro artigos reais | Consumo do modelo | Folhas pertencem à seção atual; containers conservam a seção de abertura e texto nulo. Documentado em logic/coleta-e-texto.md; 308 textos reconstruídos exatamente. Não impor igualdade de seção entre todo pai/filho do DOM. |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-20 | Fase 6 | Cobertura por DICO com identidade/extração e evidência de ausência, relatórios e testes SQL implementados. | Polish: documentação, suíte completa, prova nacional, repetição e CI remoto autorizado. |
| 2026-11-20 | Fase 5 | Reconsulta, fingerprints, reuso por role, retomada, retry_at e seleção antiga explícita comprovados. | Coleta nacional segue em andamento; aguardando relatório para divergências de evidência. |
| 2026-11-20 | Fase 4 | Extração auditada, schemas Parquet, cinco modelos dbt e promoção com journal implementados. | Prova nacional em andamento; fase 5/6 usam colaboradores já implementados para o build. |
| 2026-11-20 | Fase 3 | 308 associações curadas por agente com evidência, coleta e CLI locais implementados. | Build, extração e prova nacional ainda pendentes; curadoria será revalidada no HTML coletado. |
| 2026-11-20 | Fase 2 | HTTP serial com Retry-After, manifests próprios e reuso por role implementados. | US1 ainda em stub; curadoria e integração pendentes. |
| 2026-11-20 | Fase 1 | Catálogo restrito, dependência e validação de correspondências implementados. | Curadoria nacional e coleta/build ainda não executados. |
| 2026-11-20 | Fase 7 parcial | 543 testes, Ruff, 8 travas e builds dbt aprovados; auditoria nacional 308/308 sem perda; nenhuma entrega Git realizada | Repetição real e CI remoto autorizado |
| 2026-11-20 | Fase 7 local concluída | 308 unchanged, zero novos raw; build unchanged; 616 referências e 1.319 arquivos preservados. Runs 20261120T185614436452Z-061ad950 / 20261120T190030045538Z-077e4eb3. Handoff e docs atualizados | T035/CI remoto e scan do SHA final, dependentes de autorização Git |
| 2026-11-20 | Entrega Git autorizada | Autor autorizou branch, commit, push e PR; branch 008 publicada em 5f8c72f, PR #9 sobre feature/007; oito travas reconferidas íntegras | CI quality e secrets no PR antes de concluir T035 |
| 2026-11-20 | Fase 7 concluída | Quality e secrets do PR #9 aprovados para 5f8c72f no run 44809254508; 542 testes/1 skip Linux e sete builds verdes; T035/release concluídos, 43/43 | Publicar fechamento documental e reconferir checks do head; próxima etapa sdd-converge |

**PRÓXIMO**: sdd-converge, mediante solicitação do autor. Implementação concluída; o resultado do CI do fechamento documental fica nos checks do head final do PR #9.

## Arquivos Principais

- `pipelines/collectors/wikipedia/`
- `pipelines/cli/collect_wikipedia.py`, `pipelines/cli/build_wikipedia.py`
- `config/wikipedia_articles.csv`
- `analytics/dbt/models/wikipedia/`
- `.data/receipts/wikipedia-proof/proof-summary.json` (privado)

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- Não modificar código/SQL durante a prova: os hashes bloqueiam a promoção.
- Evidência curatorial normaliza espaços de markup/citações; nunca remover palavras para fazê-la caber.
- Provas nacionais/locks e status estão nos recibos; não tratar CI local como remoto.

### Evidência final local

Coleta completa `20261120T185614436452Z-061ad950`: 308 artigos validados, sem ausência editorial,
identidade pendente ou falha técnica. A coleta começou em lote e teve retomadas
para revisar a normalização das evidências. Curadoria por agente registrada no CSV;
nenhuma lacuna técnica foi convertida em ausência.

Build `20261120T185847215174Z-e5ca6350` aprovado em 102.465 s:
308 revisões/artigos, 7.028 seções e 248.931 blocos, cobertura 308 valid.
São 6.699.736 caracteres de texto editorial; 308 introduções, QIDs e ligações
inglesas. A auditoria reconstruiu exatamente os 308 textos a partir dos títulos
e folhas ordenadas. Lisboa preserva seções próprias para população, religiões e saúde.
Cuba, Gavião, Nazaré, Santa Cruz, Corvo e os pares Lagoa/Calheta foram conferidos
contra as identidades curatoriais. dbt: cinco modelos e 30 testes aprovados.

Repetição `20261120T190030045538Z-077e4eb3` em 620.528 s:
308/308 unchanged, 616 brutos antes/depois e zero novos arquivos raw.
Build `20261120T191050484861Z-7028d282` em 97.757 s:
unchanged, sem mover/substituir o lake. Os 616 brutos referenciados conferem
com bytes/SHA-256. Os 1.319 arquivos anteriores inventariados, incluindo os
308 TXT e o notebook legados, permaneceram idênticos. Recibos privados:
`.data/receipts/wikipedia-proof/proof-summary.json`, `before.json`,
`raw-before-repeat.json`, `lake-before-repeat.json` e `manual-audit.json`.

Validação local final: `uv run --locked python -m pytest -q --basetemp .data/tmp/wiki-final`
→ 543 passed/433,90 s; Ruff aprovado; cinco contratos e oito travas íntegros.
Área Wikipedia: 101 testes adicionais aprovados. Fixture dbt isolada aprovada.
Os cenários controlados cobrem alteração renderizada na mesma revisão, erro,
espera/limite, SIGINT, corrupção e morte de subprocesso com recuperação.
### Entrega e evidência remota — 2026-11-20

O autor autorizou branch, commit, push e PR. A implementação foi publicada em
`feature/008-ingestao-wikipedia`, commit `5f8c72f6307d66c12afa4c2315aa86e6b16f91e7`, no
[PR #9](https://github.com/johnosd/living-recommender/pull/9), com base em
`feature/007-idealista-formato-atual-relatorio` (`42a5f59`), preservando a pilha existente.

O [run 44809254508](https://github.com/johnosd/living-recommender/actions/runs/44809254508)
aprovou quality e secrets para esse SHA: Ruff, 542 testes verdes/1 skip no Linux
em 331,31 s, os sete builds isolados (incluindo Wikipedia com prontidão aprovada)
e gitleaks sem segredos encontrados. Recibo privado: `ci-implementation.json`
em `.data/receipts/wikipedia-proof/`. Oito travas foram reconferidas íntegras.

T035 e checklist concluídos; 43/43 checkboxes, status Implementada. O resultado
do CI do fechamento documental fica nos checks do head final do mesmo PR,
conferidos antes de encerrar a entrega. Dados reais/recibos não foram versionados.
