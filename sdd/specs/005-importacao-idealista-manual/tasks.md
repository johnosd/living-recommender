# Tasks: 005-importacao-idealista-manual

## Path Conventions
Código em pipelines/collectors/idealista e pipelines/cli; modelos em
analytics/dbt/models/idealista; dados reais exclusivamente .data/.

## Phase 1 — US1: importação imutável
**Goal:** entrada manual validada com manifest e repetição segura.
**Contrato:** raw_bytes_month_metadata_and_unchanged e invalid_later_file.
- [X] T001 [US1] Implementar snapshot.py, catálogo e CLI import_idealista_snapshot.py (FR-001–004; SC-001/005), deixando os dois contratos verdes.
**Tests:** entradas vazias/inválidas, hashes, mês isolado e S3 simulado.
**Critério:** contratos US1 verdes e trava íntegra.
**Registro da Fase:** US1 concluída: cópia imutável, catálogo e CLI. Dois contratos US1 verdes; testes de erro/remoção passaram. Trava íntegra. Sem pendências de código.

## Phase 2 — US2/US3: processamento e cobertura
**Goal:** anúncios tipados únicos, territórios honestos e todas as ocorrências auditáveis.
**Contrato:** unique_rows_typed_values_and_regional_coverage, unknown_municipality e tampered_raw.
- [X] T002 [US2] Implementar normalize.py e deduplicação em prepare.py (FR-005/006; SC-002/004), deixando o contrato de linhas únicas verde.
- [X] T003 [US3] Implementar territory.py, seeds e cobertura em prepare.py (FR-007/009; SC-003), deixando os contratos de território e checksum verdes.
- [X] T004 [US2/US3] Implementar build_idealista.py, modelos e testes dbt, fixture e integração (FR-008; SC-004/005).
**Tests:** parser, nulos, conflitos municipais, freguesia ambígua, rollback e integridade.
**Critério:** cinco contratos verdes, trava íntegra e build dbt sintético aprovado.
**Registro da Fase:** T002/T003 concluídas: 22 testes de contrato e unitários verdes; cinco contratos verdes. T004 concluída: 26 testes verdes, incluindo build dbt sintético e preservação após falha/tamper. Quatro casos de integração falharam pelo stub antes da implementação.

## Phase 3 — Polish e execução local real
**Goal:** importar e construir a extração aprovada com evidência.
- [X] T005 Importar 202508, construir, repetir e verificar hashes da origem/raw e das demais fontes (SC-001–005).
- [X] T006 Atualizar README, fontes, runbook, documentação SDD e CI; executar lint e suíte completa.
**Tests:** importação e build reais separados dos testes sintéticos e do CI remoto.
**Critério:** evidência local registrada sem afirmar deploy/CI remoto/publicação.
**Registro da Fase:** T005 concluída: 324 arquivos/16.566.429 bytes preservados; 17.472 ocorrências/16.117 IDs; 1.355 repetições; 255 municípios, 189 regionais, 8.891 freguesias resolvidas; importação repetida unchanged; 24 passos dbt verdes. Hashes dos 324 arquivos da origem/raw e dos 16 arquivos anteriores do lake conferem. T006 concluída: ruff limpo, suíte completa 350/350 verdes em 412,66 s, cinco travas íntegras; fluxo de fixture do CI passou localmente (24 passos dbt). O teste antigo de catálogo foi atualizado para incluir a sexta fonte após a primeira suíte mostrar 349 verdes e uma falha. README/fontes/runbook/SDD/CI sincronizados; revisão independente das correções sem novos achados. CI remoto não executado.

## Checklist de Release
- [X] US1 verificada.
- [X] US2/US3 verificadas com dbt e cobertura.
- [X] Cinco contratos verdes e trava íntegra.
- [X] Lint e suíte completa locais verdes.
- [X] Snapshot real importado e verificado, sem alterar origem nem outras fontes.
- [X] Documentação e backlog sincronizados; CI remoto identificado separadamente.
