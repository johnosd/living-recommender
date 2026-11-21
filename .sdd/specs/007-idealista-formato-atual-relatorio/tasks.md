# Tasks: Idealista atual e relatório

## Path Conventions
Código em pipelines/collectors/idealista; CLI em pipelines/cli; testes em tests; dados privados em .data; documentação em .docs.

## Phase 1: US1 — compatibilidade territorial (P1)
**Objetivo**: preparar formato atual sem perder compatibilidade legada.
**Contrato**: três testes FR-002/FR-003 em tests/contracts/test_idealista_current_contract.py.
### Implementation
- [X] T001 [US1] Validar metadados em snapshot.py e resolver hierarquia em territory.py, com seeds explícitas → contratos FR-002/FR-003.
- [X] T002 [US1] Integrar metadados em prepare.py preservando deduplicação e legado → contratos FR-002/FR-003.
### Testes da Fase
- [X] T003 [US1] Testar tipos inválidos, município desconhecido, freguesia desconhecida, aliases e legado em tests/unit/test_idealista.py.
**Critério de Conclusão**: três contratos territoriais verdes, regressão Idealista verde, trava íntegra.
### Registro da Fase
Status: concluída; ajustes de estilo autorizados e lint geral aprovado.
Feito: hierarquia explícita, aliases CAOP e suporte legado.
Contrato: três territoriais verdes; trava íntegra.
Testes executados: 33 passed, 1 deselected; regressão antiga 26 passed.
Pendências: nenhuma no escopo local.

## Phase 2: US2 — relatório (P1)
**Objetivo**: estatísticas auditáveis com supressão de amostras pequenas.
**Contrato**: test_fr005_report_suppresses_small_groups_and_excludes_conflicting_prices.
### Implementation
- [X] T004 [US2] Implementar report.py e gerar artefatos no candidato do build_idealista.py → contrato FR-005.
### Testes da Fase
- [X] T005 [US2] Testar dados vazios, ausências e integração da promoção em tests/unit/test_idealista.py e regressão de build.
**Critério de Conclusão**: quatro contratos verdes, relatório preservado pela promoção e trava íntegra.
### Registro da Fase
Status: concluída; validação local aprovada.
Feito: Markdown/JSON/CSV integrados à promoção após dbt.
Contrato: 4/4 verdes; trava íntegra.
Testes executados: 39 passed, incluindo dbt sintético e snapshot vazio.
Pendências: nenhuma no escopo local.

## Phase 3: Polish — ingestão real e entrega
**Objetivo**: ingerir lote atualizado e entregar report com prova de preservação.
### Implementation
- [X] T006 Arquivar saídas antigas; registrar hashes origem/outras fontes e importar 202611; repetir unchanged (FR-001/007).
- [X] T007 Executar build dbt real e conferir números, integridade e cobertura (FR-004/007).
- [X] T008 Atualizar README, fontes, relatório agregado em .docs/reports e memória do projeto (FR-006).
### Tests
- [X] T009 Rodar suíte completa, ruff e todas as travas.
- [X] T010 [US1] Descoberta na T007: mapear 58 equivalências explícitas de escrita para freguesias no formato novo, com seed dedicada e teste de escopo municipal/legado.

### Checklist de Release
- [X] US1 concluída.
- [X] US2 concluída.
- [X] Contratos verdes, travas íntegras, dbt real aprovado.
- [X] Quickstart real validado; relatório e preservação conferidos.
**Critério de Conclusão**: SC-001 a SC-004 demonstrados localmente; CI remoto/nuvem/publicação não executados.
### Registro da Fase
Status: concluída; todos os gates locais aprovados.
Feito: importado 202611, repetição unchanged, 24 passos dbt aprovados, relatório agregado entregue e dados anteriores preservados. 58 aliases explícitos recuperaram 3.598 freguesias.
Contrato: 4/4 verdes; sete travas íntegras.
Testes executados: suíte geral 434 passed em 501,13 s; regressão final Idealista 41 passed em 30,77 s; lint de produção/unit/integration aprovado. Após autorização: 41 passed em 25,52 s, ruff geral limpo e sete travas íntegras.
Pendências: nenhuma no escopo local. CI remoto/nuvem/publicação não executados.

## Dependencies & Execution Order
US1 → US2 → Polish. Sem delegação. Sem commit automático.

## Phase 4: Convergence

**Objetivo**: fechar as lacunas CF-001 e CF-002 da auditoria de 2026-11-17, sem reduzir os requisitos ou substituir evidência remota por execução local.

### Implementation e verificação
- [X] T011 [US2] [HIGH] CF-001 — Completar FR-005 em pipelines/collectors/idealista/report.py: incluir no JSON os recortes por município e município/tipologia e apresentar o recorte município/tipologia no Markdown. Preservar CSV, n total/elegível, exclusão de preços ausentes/conflitantes, supressão de quartis com n elegível <10 e ausência de dados individuais. Acrescentar testes unitários/de integração que confirmem os recortes e reconciliem os três formatos, sem alterar os contratos travados. Origem: FR-005 / US2; evidência: report.py:42-71 e 105-110; statistics.json atual contém apenas lote, contagens de municípios, tipologias do lote e grupos regionais.
- [X] T012 [US2] [HIGH] CF-001 — Após T011, regenerar e conferir os agregados reais de 2026-11 e a entrega em .docs/reports/, preservando origem, raw, saídas anteriores e outras fontes. Reconciliar contagens e quartis nos formatos Markdown/JSON/CSV e registrar os hashes/evidências. Origem: FR-005 / FR-007 / SC-003 / SC-004; o recorte município/tipologia entregue hoje existe somente em CSV.
- [X] T013 [HIGH] CF-002 — Após as correções e pelo fluxo de entrega autorizado pelo autor, obter e registrar evidência de lint e testes no CI para o SHA final que contenha a feature 007; registrar URL, SHA e resultado dos jobs aplicáveis. Não usar CI antigo de outra revisão como prova nem fazer commit/push/publicação automaticamente. Origem: Constitution Quality Gates §1 e princípio I (verificação de segredos em PR); evidência: constitution.md:93, workflow .github/workflows/python.yml e plan.md:69/85 (CI remoto não executado). Execução local não satisfaz este gate.

**Critério de Conclusão**: FR-005 completo nos três formatos, agregados entregues reconciliados, contratos íntegros, validação local verde e evidência de CI da revisão final; depois executar sdd-converge novamente.

### Registro da auditoria
Status: Convergência Pendente; CF-001 partial/HIGH e CF-002 missing/HIGH.
Verificado nesta passada: 39 testes de contratos/unitários/build Idealista em 26,50 s e 2 testes de importação em 1,73 s (41 no total); ruff geral aprovado; sete travas íntegras; git diff --check aprovado antes desta anexação. A suíte geral de 434 testes permanece evidência da execução anterior, não foi repetida nesta auditoria.
Integridade atual: hashes dos 74 arquivos de origem, 74 raw novos, 324 raw antigos, dois manifests antigos, 25 arquivos de outras fontes e 11 saídas operacionais conferidos; unchanged de 2026-11 sem raw adicional; quatro extratos entregues idênticos aos operacionais. Totais reconciliados e quartis municipais conferidos independentemente com statistics.quantiles(method="inclusive") para os 308 municípios; resultados dbt existentes 24/24 aprovados, sem novo build no lake vigente.
Limites: nenhum código-fonte, contrato, dado de origem/raw ou saída vigente alterado pelo convergence; README já descreve as capacidades entregues e permanece intocado; plan.md e fases anteriores preservados. CI remoto não executado nesta passada. Próximo passo: sdd-execute desta fase, seguido de sdd-converge.

### Registro da Fase
Status: concluída; T011/T012/T013 concluídas, 17/17 itens totais; evidência remota em ci-validation.md.
Feito: JSON com municipality_stats/municipality_typology_stats e Markdown com 225 grupos município/tipologia; testes adicionais e integração estendida; backup, build real e entrega regenerada. Todos os 308 municípios e 225 grupos reconciliados nos três formatos; estatísticas anteriores e bytes dos CSV municipais preservados; hashes de 501 arquivos protegidos conferidos.
Contrato: `uv run --locked python -m pytest tests/contracts/test_idealista_current_contract.py -q` coberto pela regressão dirigida e suíte geral: 4/4 verdes; `.planning/scripts/powershell/check-contract-tests.ps1 -Slug 007-idealista-formato-atual-relatorio` aprovado; sete travas íntegras, nenhuma regravada.
Testes executados: dois testes adicionais não travados falharam antes da correção por ausência dos arrays; após implementação, 43 passed em 26,46 s na regressão Idealista. Gate geral: `uv run --locked python -m pytest -q --basetemp .data/pytest-007-phase4-full` — 437 passed em 493,04 s. `uv run --locked ruff check pipelines tests` aprovado; `uv run --locked python -m pipelines.cli.build_idealista --local --snapshot-month 2026-11` aprovado, dbt 24/24. `git diff --check` aprovado. Sem falha instável observada. UI/E2E de dispositivo não aplicável ao pipeline offline.
Pendências: nenhuma de implementação nesta fase; nova convergência ainda não executada. O autor autorizou branch/commit/push/PR; commit final da implementação 0f8972feb079861bd521c0776ade79c3b3ad3920 no PR #8; CI 44141146329 aprovou quality e secrets (436 passed, 1 skip, 1 warning; seis builds dbt verdes; gitleaks sem vazamentos em 29 commits). CI push 44141132271 aprovado. Conferir também os checks do checkpoint documental antes de encerrar a entrega. Avaliação geográfica e sua entrada de backlog preservadas localmente, fora do commit. Sem merge ou publicação.
Evidências desta retomada: `.data/idealista-review-202611/phase4-20261117/{before,after}.json`, `pytest-full.log`, `build.log` e `previous-202611/`; os dados individuais e backups permanecem ignorados pelo Git.
