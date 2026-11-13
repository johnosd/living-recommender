# Tasks: Censos 2021 por freguesia

**Input**: `sdd/specs/006-censos-2021-freguesia/`

**Prerequisites**: spec.md, plan.md, research.md, data-model.md, logic/territory-and-readiness.md, contracts/censos-cli.md, quickstart.md e travas existentes íntegras.

**Organization**: 24 tasks em ordem incremental. Em cada fase, escrever/rodar os testes adicionais antes da implementação correspondente; os cinco contratos já escritos não viram task de autoria nem podem ser editados. Não implementar fases seguintes como atalho para esconder falha da fase atual.

## Path Conventions

- Coletor: `pipelines/collectors/censos2021/`; comandos: `pipelines/cli/collect_censos.py`, `pipelines/cli/build_censos.py`.
- Compartilhados: `_shared/datasets.py`, `dataset_manifest.py`, `http.py`, `catalog.py`, storage e `ine/fetch.py`, `fingerprint.py`; preservar comportamento municipal e fontes existentes.
- Modelos: `analytics/dbt/models/censos/`; qualidade: `analytics/dbt/tests/censos_integrity.sql`, `censos_coverage.sql`, tag censos.
- Novos testes complementares: `tests/unit/test_censos_catalog.py`, `test_censos_validate.py`, `test_censos_transform.py`, `test_censos_territory.py`, `test_censos_coverage.py`; integração em `tests/integration/test_collect_censos.py`, `test_censos_build.py`.
- Fixture travada: `tests/fixtures/censos2021/responses.py`; seed complementar em `tests/fixtures/censos2021/ci_seed.py`. Só dados sintéticos no Git.

## Phase 1: Foundational — catálogo e comprovação da fonte

**Objetivo**: fixar licença, geografia, categorias e validação da configuração antes da coleta operacional (D1–D3).

### Implementation

- [X] T001 Conferir e registrar em `sdd/specs/006-censos-2021-freguesia/research.md` e `.docs/fontes_de_dados.md` licença/atribuição/termos, indisponibilidade de robots, versão geográfica e declaração oficial de reexpressão dos indicadores 0014632/0011719. Verificar disponibilidade das 18/19 faixas nos metadados; vincular evidências oficiais e não inferir método desconhecido. Proibição aplicável ou incompatibilidade sem solução reprova o gate e exige decisão antes de coletar. (FR-001/002/003/008; SC-003; R-001)
- [X] T002 Registrar `censos` em `config/sources.yml`: 41 itens (dados principais/fallback + metadados), seletores explícitos, roles, geografia, período e vínculos; adicionar validação censitária de catálogo em `pipelines/collectors/censos2021/validate.py`, mantendo `get_dataset_source` genérico e sem mudar o INE municipal. Atualizar contagens de fontes em `tests/unit/test_dataset_catalog_and_manifest.py` e `tests/unit/test_climate_catalog.py` só onde a nova fonte altera expectativas, sem tocar contratos travados. (FR-001/002/003/007; SC-002/003)

### Testes da Fase

- [X] T003 Criar `tests/unit/test_censos_catalog.py`: 41 IDs únicos, dois metadados, código temporal correto, sexo/nacionalidade, categorias por indicador e assinatura de seletores, rejeição de configuração insuficiente/desconhecida antes da rede. Rodar também os testes de catálogo das outras fontes. (FR-002/003/006; SC-003)

**Critério de Conclusão**: T001 com evidência revisável, catálogo válido, categorias necessárias comprovadas nos metadados e testes de catálogo verdes; nenhum coletor real executado sem o cadastro/regras da fonte.

**Registro da Fase**:

- Status: Concluída
- Feito: Catálogo com 41 itens e evidência oficial registrados
- Contrato: uv run --locked python -m pytest tests/unit/test_censos_catalog.py tests/unit/test_climate_catalog.py tests/unit/test_dataset_catalog_and_manifest.py -q --basetemp .data/tmp/censos-phase1: 32 passed; sem contrato nesta fase; trava íntegra.
- Testes executados: uv run --locked python -m pytest tests/unit/test_censos_catalog.py tests/unit/test_climate_catalog.py tests/unit/test_dataset_catalog_and_manifest.py -q --basetemp .data/tmp/censos-phase1: 32 passed; sem contrato nesta fase
- Pendências: Implementar US1 (Fase 2)

## Phase 2: User Story 1 — coleta auditável (Priority: P1)

**Objetivo**: obter originais e metadados com edição/geografia, idempotência e diagnóstico de falhas independentes.

### Contrato da Fase

- `test_us1_fr004_fr005_raw_metadata_unchanged_and_revision`
- `test_us1_ac3_fr006_invalid_response_has_no_raw_and_recovers`
- Comando: `uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q -k us1 --basetemp .pytest_tmp_censos_us1`.

### Implementation

- [X] T004 Implementar validação de dados e metadados em `pipelines/collectors/censos2021/validate.py`, seguindo L1: Sucesso, indicador, período, dimensões, geocod e inteiro não negativo; erro/HTML sem raw. → contrato: `test_us1_ac3_fr006_invalid_response_has_no_raw_and_recovers`. (FR-001/002/006/012/013)
- [X] T005 Implementar `collect_censos` em `pipelines/collectors/censos2021/handler.py` com `collect_datasets`, fetchers de dados/metadados, snapshot único de catálogo, entry_extra e fingerprint consulta+JSON; respeitar assinaturas em contracts/censos-cli.md. Não editar lógica municipal. → contratos: os dois de US1. (FR-004/005/006; SC-002/005)
- [X] T006 Criar `pipelines/cli/collect_censos.py` com argumentos/exit codes de `_common`, HttpDownloader identificado, intervalo 2 s, 90 s, três tentativas/backoff; imprimir run/status/manifest/erros sem credenciais. (FR-003/006/017)

### Testes da Fase

- [X] T007 Criar `tests/unit/test_censos_validate.py`: JSON de erro HTTP 200, indicador errado, ausência dos seletores, linha municipal/agregada, categoria desconhecida, decimal/negativo, metadado incompatível, revisão e mudança de seletor com mesmo valor. Testar query_signature para impedir falso unchanged ao alterar configuração. (FR-002/004/005/006/013; SC-005)
- [X] T008 Criar `tests/integration/test_collect_censos.py`: CLI local offline com mocks, bytes preservados, source_release_date das duas grafias oficiais, raw órfão/manifest falhado, reuso indevido de run_id, recuperação de item e catálogos/destinos inválidos; adicionar caso moto S3 sem conta externa usando os mesmos fixtures. (FR-004/005/006/017; SC-002/005/006)

**Critério de Conclusão**: comando do contrato → 2/2 verdes e `check-contract-tests.ps1 -Slug 006-censos-2021-freguesia` íntegro; testes complementares passam, coletor offline demonstra edição e metadados imutáveis sem depender de US2/US3.

**Registro da Fase**:

- Status: Concluída
- Feito: Coleta e CLI offline local/S3 implementadas com snapshot e idempotência
- Contrato: uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py tests/unit/test_censos_validate.py tests/integration/test_collect_censos.py -q -k "us1 or bad_responses or query_identity or cli_local or manifest_failure or s3_moto" --basetemp .data/tmp/censos-phase2: 13 passed; contratos US1 2/2 verdes; trava íntegra.
- Testes executados: uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py tests/unit/test_censos_validate.py tests/integration/test_collect_censos.py -q -k "us1 or bad_responses or query_identity or cli_local or manifest_failure or s3_moto" --basetemp .data/tmp/censos-phase2: 13 passed; contratos US1 2/2 verdes
- Pendências: Implementar US2 (Fase 3)

## Phase 3: User Story 2 — preparação territorial (Priority: P2)

**Objetivo**: produzir contagens utilizáveis por freguesia/categoria com origem e sem precisão inventada.

### Contrato da Fase

- `test_fr002_fr012_fr013_reader_preserves_age_bounds_zero_suppression_and_rejects_corruption`
- `test_fr008_fr009_fr010_fr011_official_precedence_inheritance_and_partial_absence`
- Comando: `uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q -k 'reader or precedence' --basetemp .pytest_tmp_censos_us2`.

### Implementation

- [X] T009 Implementar `read_censos_response` e `harmonize_age_categories` em `pipelines/collectors/censos2021/transform.py`, conforme data-model.md e L2: limites específicos do indicador, zero/supressão/ignorado separados, faixa aberta e Bronze nativa preservada; harmonizar 85+ legado só com termos publicados. → contrato: `test_fr002_fr012_fr013_reader_preserves_age_bounds_zero_suppression_and_rejects_corruption`. (FR-002/012/013; SC-003/004)
- [X] T010 Implementar `align_censos` em `pipelines/collectors/censos2021/territory.py`, seguindo estritamente L2 e D4: equivalência documental, precedência por observação, herança integral e ausência ambígua, sem somas territoriais; supressão não revela valor por fallback; conferir município/versões, auditar órfãos. → contrato: `test_fr008_fr009_fr010_fr011_official_precedence_inheritance_and_partial_absence`. (FR-007/008/009/010/011; SC-004)
- [X] T011 Criar `prepare_censos` em `pipelines/collectors/censos2021/prepare.py`: selecionar um manifest completo, congelar suas referências e snapshots, verificar hashes e dependências geográficas, ler Bronze e produzir candidato Silver. Falha mais recente bloqueia default; run anterior só explícito. Verificar prontidão das faixas e reconciliação por suporte de origem, nunca total próprio contra faixa herdada; chamar avaliação de cobertura quando US3 estiver pronta. (FR-002/004/007/008/013/015/017; SC-002/003/006)
- [X] T012 Criar modelos external `analytics/dbt/models/censos/census_age_category.sql`, `census_observation.sql`, `census_parish_observation.sql` e `schema.yml`; tipos, not_null, unique composto, relationships para CAOP e testes de estados/contagens em `analytics/dbt/tests/censos_integrity.sql`. Adicionar tag censos em `analytics/dbt/dbt_project.yml`, reutilizando source territorial existente. (FR-007/011/012/013; SC-002/004)

### Testes da Fase

- [X] T013 Criar `tests/unit/test_censos_transform.py` e `test_censos_territory.py`: todas as 18/19 faixas, 85–89+90+, não usar código etário isolado, desconhecido/supressão sem inferência por diferença, partial_origin em one_to_one, mudança municipal, conflito de mesma precedência, origem órfã e geografia incompatível. (FR-002/007/008/009/010/011/012/013; SC-003/004)
- [X] T014 Iniciar `tests/integration/test_censos_build.py` e seed `tests/fixtures/censos2021/ci_seed.py`: Bronze/Silver com cenário de três regiões, uma herança e ausência, metadados completos sintéticos, dimensões e correspondência; preparar offline sem nova coleta. Cobrir hash adulterado, run partial recente, seleção explícita anterior, mudança posterior de catálogo e reconciliação apenas entre categorias de mesmo suporte. (FR-004/008/013/015/017; SC-002/003/004/006)

**Critério de Conclusão**: comando do contrato → 2/2 verdes e trava íntegra; preparação offline e modelos validados por testes dirigidos. A cobertura/prontidão final da promoção só é declarada após US3.

**Registro da Fase**:

- Status: Concluída
- Feito: Leitor e correspondência territorial implementados; dbt external com 20 passos verdes após criar diretórios candidatos
- Contrato: uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q -k "reader or precedence" --basetemp .data/tmp/censos-us2-final: 2/2 verdes; testes complementares 7 verdes; dbt build --select tag:censos: 20/20; trava íntegra.
- Testes executados: uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q -k "reader or precedence" --basetemp .data/tmp/censos-us2-final: 2/2 verdes; testes complementares 7 verdes; dbt build --select tag:censos: 20/20
- Pendências: Implementar US3 (Fase 4)

## Phase 4: User Story 3 — qualidade e versão utilizável (Priority: P2)

**Objetivo**: expor cobertura completa e impedir promoção de entradas defeituosas ou resultados inválidos.

### Contrato da Fase

- `test_fr014_fr015_sc001_sc006_coverage_distinguishes_documented_absence_from_lost_record`
- Comando: `uv run --locked python -m pytest tests/contracts/test_censos2021_contract.py -q -k coverage_distinguishes --basetemp .pytest_tmp_censos_us3`.

### Implementation

- [X] T015 Implementar `assess_censos_coverage` e emissão de coverage.csv, summary.csv, readiness.json, orphans.csv em `pipelines/collectors/censos2021/coverage.py`, seguindo L3. Matriz exata de chaves, ausência motivada, blockers propagados e counts de observações; sem somar habitantes herdados. → contrato: `test_fr014_fr015_sc001_sc006_coverage_distinguishes_documented_absence_from_lost_record`. (FR-014/015; SC-001/006)
- [X] T016 Criar `analytics/dbt/models/censos/census_coverage.sql` e complementar `schema.yml`, `analytics/dbt/tests/censos_coverage.sql`: chaves dimensão×categoria, estados e relações, consistência relatório/tabelas sem hardcode nacional. Finalizar preparo em `prepare.py`, preservando diagnóstico de entrada falhada fora dos relatórios vigentes. (FR-014/015; SC-001/006)
- [X] T017 Criar `pipelines/cli/build_censos.py` conforme L4: lock por raiz, confinamento Windows, entrada congelada, dbt exclusivo com tag censos, readiness obrigatória, presença dos cinco caminhos e promoção com `_promote.promote_paths` após validar relatórios; erro retorna 1 sem tocar vigente nem tabelas vizinhas. (FR-016/017; SC-005/006)

### Testes da Fase

- [X] T018 Completar `tests/integration/test_censos_build.py` com dbt real offline e simulações de erro: callback/subprocess dbt falhado, caminho candidato ausente, escrita de relatório falhada antes da promoção, rename falhado com rollback, dependência territorial alterada durante build e dois builds concorrentes; hashes de vigente e tabelas vizinhas preservados. Testar lock interrompido sem apagar lock alheio e diagnóstico/recovery. (FR-013/014/015/016/017; SC-001/005/006)
- [X] T019 Criar `tests/unit/test_censos_coverage.py`: igualdade de chaves além da contagem, duplicados/extras, ausência sem evidência, sexo/nacionalidade não duplicados nas contagens, todo município/região no resumo e heranças nunca somadas em totais de pessoas; fonte inteira ausente e faixa insuficiente bloqueiam. (FR-014/015; SC-001/003/006)

**Critério de Conclusão**: comando do contrato → 1/1 verde e trava íntegra; cinco contratos completos verdes; build de fixture com dbt real e relatórios íntegros, cenários de falha demonstram preservação. Ausência oficial documentada pode ser aceita; falha técnica não pode.

**Registro da Fase**:

- Status: Concluída
- Feito: Cobertura e build com lock/rollback; relatório nacional sem somar heranças
- Contrato: uv run --locked python -m pytest tests/integration/test_censos_build.py tests/unit/test_censos_territory.py tests/unit/test_censos_coverage.py tests/contracts/test_censos2021_contract.py -q --basetemp .data/tmp/censos-phase4: 23 passed, contratos completos 5/5 verdes; trava íntegra.
- Testes executados: uv run --locked python -m pytest tests/integration/test_censos_build.py tests/unit/test_censos_territory.py tests/unit/test_censos_coverage.py tests/contracts/test_censos2021_contract.py -q --basetemp .data/tmp/censos-phase4: 23 passed, contratos completos 5/5 verdes
- Pendências: Polish: CI, docs, suíte completa e prova nacional real

- [X] T025 [Descoberta em T018/revisão] Reforçar ausência oficial sem fallback, coerência etária parcial, seleção explícita de run, confinamento de destinos e diagnóstico de limpeza pós-promoção em `territory.py`, `prepare.py`, `pipelines/cli/build_censos.py` e testes complementares de integração; manter helper compartilhado e contratos intocados. (FR-010/013/015/016; SC-005/006)

## Phase 5: Polish & Cross-Cutting Concerns

**Objetivo**: demonstrar repetibilidade offline e cobertura nacional real, sincronizando documentação e gates.

### Implementation

- [X] T020 Incluir fixture e `dbt build --select tag:censos` em `.github/workflows/python.yml`, com env vars da feature e sem INE/rede externa no teste; preservar jobs/tags/steps de 001–005. (FR-013/016; SC-005)
- [X] T021 Atualizar `docs/runbooks/coletas.md`, `.docs/fontes_de_dados.md` e `README.md`: execução/retomada/seleção de run, categorias, herança/ausência, licença, limites da prova, diagnóstico/recovery e comandos reais; ajustar `quickstart.md` apenas para os comandos efetivamente implementados. (FR-003/014/017; SC-002/006)

- [X] T026 [Descoberta em T023; D2 reaberta pelo usuário] Adaptar catálogo/coleta/leitor/preparo para lotes explícitos de até32 freguesias com todas as categorias; verificar produto cartesiano e união nacional, sem alterar contratos travados; repetir prova real e gates. (FR-001/005/013/016; SC-001/005/007)

### Testes da Fase

- [ ] T022 Executar quickstart offline: lint global, suíte completa, 5 contratos verdes e todas as travas 001–006 íntegras, seed e dbt da feature. Registrar saídas no `plan.md`/`tasks.md`; obter evidência do CI remoto quando disponível sem tratá-lo como inferido do local. (FR-013/016/017; SC-001/002/003/004/005/006)
- [X] T023 Executar coleta nacional real após T001 e build em `.data`, sem sobrescrever originais, medir as 19 categorias canônicas, cobertura por país/região/município/freguesia, proveniência, bytes/duração/limites e ausência explicada; repetir coleta e comprovar unchanged. Registrar evidências e licenças no runbook e no plan. Falha de faixa, registros perdidos ou ausência não comprovada impede concluir SC-007. (FR-001 a FR-017; SC-001 a SC-007)
- [X] T024 Auditar diff e rastreabilidade em `sdd/specs/006-censos-2021-freguesia/plan.md` e `tasks.md`, confirmar nenhum arquivo travado ou trabalho prévio alterado indevidamente, relatório honesto e status adequado no `.planning/backlog.md`. Não marcar convergida antes de sdd-converge. (SC-001 a SC-007)

**Critério de Conclusão**: cinco contratos verdes + todas as travas íntegras; lint/suíte/dbt/quickstart aprovados e execução real nacional com SC-007 comprovado. CI remoto tem resultado próprio registrado, conforme gate da constitution; sua indisponibilidade permanece pendência, não sucesso presumido. Nenhuma alegação de publicação, cloud ou indicadores finais.

### Checklist de Release

- [X] Fase 1: fonte/catálogo/categorias e regras comprovadas.
- [X] Fase 2: US1 concluída e dois contratos verdes.
- [X] Fase 3: US2 concluída e dois contratos verdes.
- [X] Fase 4: US3 concluída e contrato verde.
- [X] Todos os contratos verdes e travas 001–006 íntegras.
- [ ] Lint, suíte offline completa e dbt censos verdes; CI remoto e scan de segredos com evidência própria.
- [X] Quickstart offline e coleta/build nacional reais separados; ausência oficial não esconde falha técnica.
- [X] Rollback, confinamento dos caminhos, lock/recovery e preservação de tabelas vizinhas demonstrados.
- [X] Fonte/licença/runbook/README/backlog sincronizados, sem reescrever o trabalho local de 005.

**Registro da Fase**:

- Status: Implementação e provas locais concluídas;fase permanece aberta pelo gate remoto de CI.
- Feito: T020/T021/T023/T024/T025/T026 concluídas. D2 aprovada e implementada,prova nacional e repetição201/201 unchanged aprovadas;relatórios e22 arquivos vizinhos verificados. Nenhum contrato travado ou helper compartilhado alterado nesta emenda.
- Contrato: 5/5 verdes na suíte completa; travas 001–006 íntegras.
- Testes executados: `uv run --locked python -m pytest -q --basetemp .data/tmp/censos-batches-full` →411 passed em571,46s;61 da área censos em32,12s e2 regressões adicionais em3,37s; `uv run --locked ruff check pipelines tests` aprovado; seed/build em `.data/ci-censos-batches` aprovado; build real com4 modelos e21 testes dbt aprovados.
- Pendências: somente T022 e checkbox de CI remoto/scan de segredos. Sem commit/push autorizado;não presumir CI pelo resultado local.

## Dependencies & Execution Order

Fase 1 bloqueia coleta operacional. Fase 2 entrega P1 independentemente da preparação. Fase 3 pode ser validada com originais/fixtures preservados; o build final usa a qualidade da Fase 4. Fase 4 pode testar a avaliação com saídas sintéticas, mas a promoção depende do preparo da Fase 3. Fase 5 depende das três stories. Não há autorização automática de continuação entre skills.

Nenhuma delegação é necessária. As tarefas seguem ordem de dependência e compartilham catálogo/modelos; não executar dois editores no mesmo arquivo. Unitários de módulos independentes podem ser preparados separadamente sem concorrência de builds na mesma raiz.

## Requirement Traceability

| Origem | Tasks |
| --- | --- |
| FR-001 | T001, T002, T004, T023 |
| FR-002 | T001, T002, T003, T004, T007, T009, T011, T013 |
| FR-003 | T001, T002, T003, T006, T021 |
| FR-004 | T005, T007, T008, T011, T014 |
| FR-005 | T005, T007, T008, T023 |
| FR-006 | T003, T004, T005, T006, T007, T008 |
| FR-007 | T002, T010, T011, T012, T013 |
| FR-008 | T001, T010, T011, T013, T014 |
| FR-009 | T010, T013 |
| FR-010 | T010, T013 |
| FR-011 | T010, T012, T013 |
| FR-012 | T004, T009, T012, T013 |
| FR-013 | T004, T007, T009, T011, T012, T013, T014, T018, T020, T022 |
| FR-014 | T015, T016, T018, T019, T021 |
| FR-015 | T011, T014, T015, T016, T018, T019 |
| FR-016 | T017, T018, T020, T022 |
| FR-017 | T006, T008, T011, T014, T017, T018, T021, T022 |
| SC-001 | T015, T016, T018, T019, T022, T023 |
| SC-002 | T002, T005, T008, T011, T012, T014, T021, T023 |
| SC-003 | T001, T002, T003, T009, T011, T013, T014, T019, T023 |
| SC-004 | T009, T010, T012, T013, T014, T022, T023 |
| SC-005 | T005, T007, T008, T017, T018, T020, T022, T023 |
| SC-006 | T008, T011, T014, T015, T016, T017, T018, T019, T021, T023 |
| SC-007 | T023, T024 |

## Notes

Os arquivos de contrato e seus helpers travados são definição de pronto; qualquer alteração requer emenda no sdd-plan, nunca ajuste para facilitar implementação. Registros das fases estão deliberadamente vazios para o sdd-execute.

## Evidência final local da emenda D2

### Prova real concluída após emenda D2 — 2026-11-13

Coleta inicial `20261113T231450079026Z-ddf26aad`:201 chamadas/201 respostas,200 changed e1 metadado unchanged,32.804.869 bytes referenciados,449,406s. Repetição `20261113T232234325869Z-00a1b4a4`:201/201 unchanged,201 chamadas,449.906s,nenhum novo raw. Ambos os manifests estão em `.data/manifests/censos/`;originais,hashes,consultas e revisões da primeira rodada foram conferidos após a segunda. Recibos e auditorias em `.data/receipts/censos-proof/`.

Build real aprovado:3.259 freguesias,308 municípios,19 categorias canônicas e61.921 observações próprias;0 herdadas,0 ausentes. Bronze123.761 linhas;população total2021 de10.343.066. Cobertura regional completa e18 códigos alfanuméricos preservados. Todas as observações têm fonte,licença,território,run e referências raw verificadas. Vinte e dois arquivos vizinhos permaneceram idênticos. dbt:4 modelos e21 testes aprovados. Relatórios: `.data/lake/silver/census_reports/`. Fonte INE,Censos2021,CC-BY-4.0. O método de reexpressão não foi divulgado pelo publicador nas evidências consultadas;essa limitação permanece registrada,sem estimativa do projeto.

Validação local: `uv run --locked python -m pytest -q --basetemp .data/tmp/censos-batches-full` →411 passed em571,46s;2 regressões adicionais (histórico completo41 itens e repetição por lotes) →2 passed em3,37s,fora da coleta inicial dessa suíte. Área censos →61 passed em32,12s antes dessas2 adições. `uv run --locked ruff check pipelines tests` aprovado. Seed/build de CLI em `.data/ci-censos-batches` aprovado;travas001–006 íntegras;revisão independente sem bug material. O CI remoto e seu scan de segredos seguem pendentes de commit/push/PR autorizado;nenhuma execução em nuvem ou publicação foi demonstrada. Não marcar Implementada/Convergida antes do gate restante.
