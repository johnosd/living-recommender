# Tasks: Ingestão Wikipedia

**Input**: `.sdd/specs/008-ingestao-wikipedia/`.
**Prerequisites**: spec.md, plan.md, research.md, data-model.md,
contracts/wikipedia-cli.md, logic/coleta-e-texto.md e quickstart.md.
**Organization**: setup/fundação → US1 P1 → US2/US3/US4 P2 → Polish.
Nenhuma task pede reescrever os cinco contratos travados.

## Path Conventions

- Fonte: `pipelines/collectors/wikipedia/`; CLIs: `pipelines/cli/`.
- Configuração: `config/sources.yml`, `config/wikipedia_articles.csv`.
- Modelos/testes de dados: `analytics/dbt/models/wikipedia/`, `analytics/dbt/tests/`.
- Testes complementares: `tests/unit/test_wikipedia_*.py`, `tests/integration/test_wikipedia_*.py`.
- Fixtures complementares: `tests/fixtures/wikipedia/ci_seed.py`; `responses.py` já travado.
- Artefatos reais privados/evidências: `.data/`; nunca `J:/MPAlugueisLisboa`.
- [P] significa arquivo independente dentro da fase; não autoriza delegação nem mudanças nas dependências de outra task.

## Phase 1: Setup e gates da fonte

**Objetivo**: cadastrar a fonte/licença e preparar o contexto territorial com validação antes da rede.

### Contrato da Fase

Sem contrato dedicado; os contratos de US1 já existem e seguem vermelhos até a fase 3.

### Implementation

- [X] T001 Conferir R-001 já autorizado, rightsinfo/termos/contato; cadastrar fonte e implementar `pipelines/collectors/wikipedia/catalog.py` + entrada em `config/sources.yml`, sem alterar semântica de outras fontes. D1/D3; FR-002, FR-003, FR-017; Constitution IV/VII.
- [X] T002 [P] Adicionar beautifulsoup4 na faixa R4 de `research.md` em `pyproject.toml` e resolver `uv.lock` sem atualização geral; usar parser explícito e registrar versão. FR-011, FR-014; plan D6.
- [X] T003 Criar loader/esquema de `config/wikipedia_articles.csv` em `pipelines/collectors/wikipedia/identity.py`, validando DICO, universo, duplicatas, status/evidência/abrangência e dimensão. FR-001, FR-004, FR-005, FR-006; seguir `data-model.md` e `logic/coleta-e-texto.md`.

### Testes da Fase

- [X] T004 [P] Cobrir catálogo inválido/sem contato, exceção restrita, idioma errado, endpoint fora da allowlist e fixture com universo explícito em `tests/unit/test_wikipedia_catalog.py`. FR-001, FR-002, FR-003, FR-017.
- [X] T005 [P] Cobrir DICO duplicado/extra/perdido, evidência insuficiente e sede/município em `tests/unit/test_wikipedia_identity.py`. FR-004, FR-005, FR-006; SC-001.

**Critério de Conclusão**: testes complementares da fase e Ruff verdes, nenhuma rede antes da validação, R-001 registrado sem ampliar exceção; dependências/lock consistentes.

**Registro da Fase**:

- Status: concluída
- Feito: Catálogo restrito, dependência e validação de correspondências implementados.
- Contrato: sem contrato dedicado nesta fase; trava íntegra.
- Testes executados: pytest setup: 25 passed; ruff check área: aprovado.
- Pendências: Curadoria nacional e coleta/build ainda não executados.

## Phase 2: Fundação de HTTP, manifest e contexto

**Objetivo**: obter documentos por transporte responsável e persistir estado Wikipedia sem afetar resolvedores antigos.

### Contrato da Fase

Sem contrato dedicado; preparando colaboradores usados pelas interfaces de US1.

### Implementation

- [X] T006 Implementar snapshots, hashes, manifest próprio e seleção de conteúdo/tentativa em `pipelines/collectors/wikipedia/manifest.py` e `state.py`, conforme `data-model.md`. FR-008, FR-019, FR-020, FR-021, FR-022, FR-028; D7/D8/D10; → contrato: `test_us3_fr019_fr020_fr021_catalog_and_mapping_are_frozen_and_rechecked`.
- [X] T007 Implementar fetcher httpx injetável em `pipelines/collectors/wikipedia/fetch.py`: query por identidade, paginação, parse oldid/tocdata, timeout/limite/maxlag, Retry-After e erros de corpo. Não reusar cegamente HttpDownloader. FR-007, FR-009, FR-016, FR-017, FR-018; → contrato: `test_us1_ac2_ac4_fr006_fr009_invalid_identity_revision_and_api_error_do_not_become_state`.

### Testes da Fase

- [X] T008 [P] Com MockTransport/relogio injetados, testar 200 com erro, 403, 429, 503, maxlag, Retry-After data/segundos, prazo longo, continuação e nenhum acesso fora do endpoint em `tests/unit/test_wikipedia_http.py`. FR-007, FR-009, FR-017, FR-018.
- [X] T009 [P] Testar hash/canonização, reutilização por role, órfãos, run ID/caminhos inválidos, failed versus último válido e ausência com evidência em `tests/unit/test_wikipedia_state.py`. FR-008, FR-020, FR-021, FR-022, FR-028.

**Critério de Conclusão**: testes de HTTP/estado verdes; respostas preservadas como bytes; retorno failed/pending não interpretado como ausência; testes compartilhados da baseline continuam verdes.

**Registro da Fase**:

- Status: concluída
- Feito: HTTP serial com Retry-After, manifests próprios e reuso por role implementados.
- Contrato: sem contrato dedicado nesta fase; trava íntegra.
- Testes executados: pytest HTTP/estado: 21 passed; shared HTTP/storage/catalog: aprovado; ruff área aprovado.
- Pendências: US1 ainda em stub; curadoria e integração pendentes.

## Phase 3: User Story 1 — artigos corretos e auditáveis (P1)

**Objetivo**: entregar coleta bruta de identidades municipais validadas, demonstrável antes do build.

### Contrato da Fase

- `test_us1_fr004_fr008_fr009_pinned_identity_and_immutable_raw` — US1/AC1, FR-004/008/009.
- `test_us1_ac2_ac4_fr006_fr009_invalid_identity_revision_and_api_error_do_not_become_state` — US1/AC2/4, FR-006/009/018.
- Comando: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us1 -q --basetemp .data/tmp/wiki-us1`.

### Implementation

- [X] T010 Curar `config/wikipedia_articles.csv` para os 308 municípios a partir da dimensão vigente, com evidências verificáveis, nomes homônimos e escopos; ausência só após avaliação documentada. Não usar TXT como verdade. FR-001, FR-004, FR-005, FR-006, FR-030; SC-001; D2/R-002.
- [X] T011 Implementar `collect_wikipedia` em `pipelines/collectors/wikipedia/handler.py` e validação de identidade/revisão/evidência em `identity.py`, usando `logic/coleta-e-texto.md`. FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-018; → contratos: os dois casos US1.
- [X] T012 Criar `pipelines/cli/collect_wikipedia.py` com argumentos/status do contrato CLI, lock por fonte, contexto físico congelado e relatório da tentativa. FR-003, FR-017, FR-022, FR-029; → contrato: `test_us1_fr004_fr008_fr009_pinned_identity_and_immutable_raw`.

### Testes da Fase

- [X] T013 Regressões sintéticas de Cuba/país, Corvo/Gavião/aves, Nazaré/outro país, Santa Cruz/desambiguação, título movido e evidência removida em `tests/unit/test_wikipedia_identity.py`. FR-004, FR-005, FR-006, FR-007; SC-005.
- [X] T014 Usar LocalStorage real em raiz temporária para testar bytes/manifests, snapshots e recuperação de falha sem sobrescrever vizinhos em `tests/integration/test_wikipedia_collect.py`. FR-008, FR-009, FR-018, FR-030; SC-002.

**Critério de Conclusão**: comando US1 → 2/2 verdes e trava íntegra; coleta utilizável sem preparar texto, sem artigos de outros territórios e com associações nacionais revisáveis. Insucesso da curadoria não vira ausência aceita automaticamente.

**Registro da Fase**:

- Status: concluída
- Feito: 308 associações curadas por agente com evidência, coleta e CLI locais implementados.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us1 -q --basetemp .data/tmp/wiki-us1` → 2/2 verdes; trava íntegra.
- Testes executados: pytest US1: 2/2; área coleta/identidade/estado: 20 passed; ruff aprovado.
- Pendências: Build, extração e prova nacional ainda pendentes; curadoria será revalidada no HTML coletado.

## Phase 4: User Story 2 — texto completo e preparação offline (P2)

**Objetivo**: produzir introdução, seções e blocos completos sem fronteiras cruzadas nem perda silenciosa.

### Contrato da Fase

- `test_us2_fr010_fr011_fr012_fr013_complete_sections_keep_boundaries_and_nested_context` — US2/AC1–6, FR-010–013.
- Comando: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us2 -q --basetemp .data/tmp/wiki-us2`.

### Implementation

- [X] T015 Implementar `extract_article` em `pipelines/collectors/wikipedia/extract.py`, pelo algoritmo de `logic/coleta-e-texto.md`: lead, índice tocdata/sections, pilha de headings, ownership de folhas, tabelas/listas/referências/links e auditoria de completude. FR-010, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016; → contrato US2.
- [X] T017 Criar `pipelines/collectors/wikipedia/prepare.py`: entrada completa fixada, hashes/versões, schemas Parquet explícitos e catálogo/associação do run, sem rede. FR-008, FR-009, FR-021, FR-023; SC-006; → contrato US2.
- [X] T018 Criar os cinco SQL e `schema.yml` em `analytics/dbt/models/wikipedia/`, tag em `analytics/dbt/dbt_project.yml` e `analytics/dbt/tests/wikipedia_integrity.sql`; tipos, chaves, relacionamentos e ausência de placeholders nulos nas tabelas vazias. FR-010, FR-011, FR-012, FR-013, FR-023; SC-002, SC-003; → contrato US2.
- [X] T019 Criar `pipelines/cli/build_wikipedia.py`: candidato/banco isolados, lock, hashes, dbt, prontidão, journal e promoção/recuperação apenas dos caminhos Wikipedia. FR-024, FR-029; SC-005, SC-006; D11/D12. Não alterar `_promote.py` sem necessidade demonstrada.
- [X] T021 [P] Criar fixture de build em `tests/fixtures/wikipedia/ci_seed.py`, raiz nova isolada, usando documentos sintéticos e dimensão mínima coerente. FR-023; SC-006. Não editar responses.py travado.

### Testes da Fase

- [X] T016 Testar tocdata real sintético, sections legado, h2 do índice, títulos duplicados, seção vazia, links inline, referências, tabelas aninhadas e nós não suportados em `tests/unit/test_wikipedia_extract.py`. FR-010–016; SC-003.
- [X] T020 Testar preparo sem rede, corrupção, dependência trocada, exports dbt, vigência preservada, journal/lock/junction e recuperação após interrupção em `tests/integration/test_wikipedia_build.py`. FR-023, FR-024; SC-005, SC-006.

**Critério de Conclusão**: contrato US2 → 1/1 verde e trava íntegra; build offline da fixture aprovado com dbt, completude auditável e recuperação comprovada. Os contratos de US3/US4 podem continuar vermelhos até suas fases.

**Registro da Fase**:

- Status: concluída
- Feito: Extração auditada, schemas Parquet, cinco modelos dbt e promoção com journal implementados.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us2 -q --basetemp .data/tmp/wiki-us2` → 1/1 verdes; trava íntegra.
- Testes executados: pytest extração/build: 21 passed; dbt fixture real: 5 modelos e 30 testes aprovados; US2 1/1 verde; ruff global aprovado.
- Pendências: Prova nacional em andamento; fase 5/6 usam colaboradores já implementados para o build.

## Phase 5: User Story 3 — atualizações e retomada (P2)

**Objetivo**: verificar fonte em novos ciclos, retomar pendências e reprocessar mudanças sem duplicação ou falsa atualização.

### Contrato da Fase

- `test_us3_fr019_fr020_fr021_catalog_and_mapping_are_frozen_and_rechecked` — US3/AC1–3, FR-019/020/021.
- Comando: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us3 -q --basetemp .data/tmp/wiki-us3`.

### Implementation

- [X] T022 Completar fingerprints e comparação de contexto/bytes em `pipelines/collectors/wikipedia/state.py` e `handler.py`; reconsultar metadata+parse na execução padrão, preservar revisões e referência de roles iguais. FR-019, FR-020, FR-021; → contrato US3.
- [X] T023 Implementar resume-run-id, max-municipalities, Ctrl+C e prazo longo de cota em `pipelines/cli/collect_wikipedia.py`/`handler.py`, com snapshots congelados, run novo e verificação mantida dos sucessos do ciclo. FR-017, FR-022, FR-028, FR-029; → contrato US3.
- [X] T024 Implementar processing_signature, skip de promoção equivalente e seleção antiga explícita em `pipelines/collectors/wikipedia/prepare.py`/`pipelines/cli/build_wikipedia.py`; relatório atual fora do lake e falha recente não escondida. FR-020, FR-021, FR-024, FR-028; → contrato US3.

### Testes da Fase

- [X] T025 Em `tests/unit/test_wikipedia_state.py` e `tests/integration/test_wikipedia_cli.py`, verificar atualização renderizada com mesmo revid, mudança isolada, snapshots alterados pelo chamador, resume incompatível, preservação de sucesso, retry_at e build unchanged sem mover lake. FR-019–022, FR-024, FR-028; SC-004, SC-005.

**Critério de Conclusão**: contrato US3 → 1/1 verde e trava íntegra; repetir um ciclo completo verifica a fonte e não duplica bruto equivalente; retomada não disfarça datas nem altera contexto.

**Registro da Fase**:

- Status: concluída
- Feito: Reconsulta, fingerprints, reuso por role, retomada, retry_at e seleção antiga explícita comprovados.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us3 -q --basetemp .data/tmp/wiki-us3` → 1/1 verdes; trava íntegra.
- Testes executados: US3 1/1 verde já pela fundação; pytest CLI/estado/coleta: 19 passed; contratos não editados.
- Pendências: Coleta nacional segue em andamento; aguardando relatório para divergências de evidência.

## Phase 6: User Story 4 — cobertura e prontidão (P2)

**Objetivo**: contabilizar o universo completo com evidência de conteúdo utilizável e causas distintas de lacuna.

### Contrato da Fase

- `test_us4_fr025_fr026_fr027_fr028_readiness_rejects_loss_and_latest_failure` — US4/AC1/3/4, FR-025–028.
- Comando: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us4 -q --basetemp .data/tmp/wiki-us4`.

### Implementation

- [X] T026 Implementar `assess_wikipedia_coverage` em `pipelines/collectors/wikipedia/coverage.py`, por DICO esperado e evidência, sem contar linhas apenas. FR-001, FR-025, FR-026, FR-027, FR-028; → contrato US4.
- [X] T027 Integrar relatório CSV/JSON, inventário de seções/temas, últimas tentativas/versões e diagnósticos em `coverage.py`, `prepare.py` e CLIs; não converter narrativa em indicador. FR-014, FR-015, FR-025, FR-026, FR-027, FR-028, FR-031; → contrato US4.
- [X] T028 Acrescentar testes de universo/estados/relacionamentos em `analytics/dbt/tests/wikipedia_coverage.sql` e gate final em `pipelines/cli/build_wikipedia.py`. FR-024, FR-025, FR-027; SC-001; → contrato US4.

### Testes da Fase

- [X] T029 Testar artigo curto sem introdução/tema versus perda de extração, ausência comprovada versus erro, DICO extra/duplicado/perdido e versão antiga após falha em `tests/unit/test_wikipedia_coverage.py` e `tests/integration/test_wikipedia_build.py`. FR-025–028; SC-001, SC-005.

**Critério de Conclusão**: contrato US4 → 1/1 verde e trava íntegra; cobertura completa usa universo real, aceita somente ausência justificada e reprova falhas sem substituir vigente.

**Registro da Fase**:

- Status: concluída
- Feito: Cobertura por DICO com identidade/extração e evidência de ausência, relatórios e testes SQL implementados.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -k us4 -q --basetemp .data/tmp/wiki-us4` → 1/1 verdes; trava íntegra.
- Testes executados: US4 1/1 verde; pytest cobertura/build: 25 passed; cinco contratos verdes; trava íntegra.
- Pendências: Polish: documentação, suíte completa, prova nacional, repetição e CI remoto autorizado.

## Phase 7: Polish e aceite

**Objetivo**: comprovar a fonte real, preservar o ambiente existente e documentar operação/limites.

### Contrato da Fase

Todos os cinco: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -q --basetemp .data/tmp/wiki-contracts`.

### Implementation

- [X] T030 Atualizar `.docs/fontes_de_dados.md`, `.docs/runbooks/coletas.md` e README.md com comandos reais, estados, atribuição/exceção, ausência/abrangência, legado fora e distinção de narrativa/indicador. FR-002, FR-029, FR-030, FR-031; SC-007.
- [X] T031 Acrescentar fixture/build dbt Wikipedia em `.github/workflows/python.yml`, isolando paths/banco/target/logs e mantendo lint/testes/secrets existentes. FR-023; Constitution Quality Gates 1–3.
- [X] T033 Executar prova nacional e repetição conforme `quickstart.md`, registrando em `.data/receipts/wikipedia-proof/` runs, raw hashes, cobertura, versões/ausências e preservação dos arquivos anteriores. FR-001–031; SC-001, SC-002, SC-004, SC-006, SC-007. Revisão real mudou? Registrar changed sem forçar unchanged; provar idempotência também em origem controlada.
- [ ] T035 Confirmar CI remoto e scan de segredos do SHA final no fluxo de entrega autorizado; não fazer commit/push/PR sem autorização específica. Registrar evidência em checkpoint do `plan.md`. Constitution Quality Gate 1; SC-007.
- [X] T036 Fechar checkpoint e status de execução em `plan.md`/`tasks.md`/backlog apenas com gates comprovados; preservar análises históricas e encaminhar para sdd-converge. SC-001–007.

### Testes da Fase

- [X] T032 Rodar Ruff, cinco contratos, oito travas, suíte completa e build dbt da fixture pelos comandos de `plan.md`/`quickstart.md`; contar cinco casos Python sem desabilitações. SC-003, SC-005, SC-006; R-010.
- [X] T034 Executar cenários controlados adicionais de erro/revisão/cota/interrupção/recuperação e inspeção de homônimos/seções em `tests/integration/test_wikipedia_cli.py`, preservando resultado e nível de prova. FR-004, FR-005, FR-006, FR-009, FR-017, FR-018, FR-022, FR-024, FR-028; SC-005, SC-007.

### Checklist de Release

- [X] Setup e fundação concluídos.
- [X] US1, US2, US3 e US4 concluídas com registros das fases.
- [X] Cinco contratos verdes e oito travas íntegras; contagem/ausência de testes desabilitados conferidas pelo runner/AST.
- [X] Ruff, suíte completa, modelos/testes dbt e fixture isolada aprovados.
- [X] Quickstart real, repetição e cenários de falha comprovados; dados existentes preservados.
- [X] Cobertura dos 308 contabilizada sem falhas técnicas/identidades pendentes; ausências justificadas.
- [ ] Docs e catálogo refletem a entrega; CI remoto do SHA final e secrets aprovados no fluxo autorizado.

**Critério de Conclusão**: cinco contratos verdes e trava íntegra, todos os itens acima comprovados; estado local não substitui CI nem ausência editorial substitui erro técnico. Nenhum hardware, browser, AWS ou provedor pago é gate.

**Registro da Fase**:

- Status: implementação e aceite locais concluídos; release formal aguarda T035/CI remoto autorizado.
- Feito: documentação/CI configurados, 308 valid; repetição 308 unchanged sem novo raw nem mudança do lake; 616 referências verificadas e 1.319 arquivos anteriores preservados; auditoria reconstruiu 308 textos completos; handoff atualizado.
- Contrato: `uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -q --basetemp .data/tmp/wiki-contracts-final` → 5/5 verdes; oito travas íntegras; AST sem decorators/skip/xfail.
- Testes executados: `uv run --locked python -m pytest -q --basetemp .data/tmp/wiki-final` → 543 passed/433,90 s; `uv run --locked ruff check pipelines tests` aprovado; área Wikipedia → 101 passed/7,75 s; dbt real da fixture e nacional → 5 modelos + 30 testes verdes. Testes controlados incluem erro/revisão/limite/Retry-After/SIGINT e morte real de subprocesso com recuperação de lock/journal.
- Pendências: T035 e último item de release: branch/commit/push/PR autorizados para CI e scan do SHA final. Status permanece Em Execução. Handoff disponível para retomada/sdd-converge; não marcar Implementada antes do gate remoto.

## Dependencies & Execution Order

Fases 1→2→3→4→5→6→7; o módulo de coverage pode ser desenvolvido com fixtures
antes do build, mas o aceite integrado respeita essa sequência. T010 é trabalho
real de curadoria nacional; não marcar pronto com CSV todo pending_review.
Na fase 4, implementar T015 e T016 antes de preparo/dbt; T021 pode ser feito
em paralelo aos módulos de build. IDs são estáveis mesmo quando implementação
e testes são apresentados em blocos separados; execute segue dependências,
não apenas ordenação numérica.

MVP de US1 coleta originais verificáveis sem depender das saídas textuais;
aceite final da feature exige as quatro stories. Checkpoints não autorizam
commits/publicação nem pausas opcionais quando houver execução contínua autorizada.
