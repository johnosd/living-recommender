# Implementation Plan: Idealista atual e relatório
**Slug**: `007-idealista-formato-atual-relatorio` | **Date**: 2026-11-17

## Summary
Estender o preparador existente; importar só municipios/202611; relatório agregado local gerado no candidato e promovido junto das tabelas após dbt. Sem nova dependência.

## Technical Context
Python 3.12, pandas/PyArrow, dbt-core/dbt-duckdb; Windows; armazenamento local .data; pytest e ruff. ADR-001/002 preservadas. Escala real 74 arquivos/18.059 ocorrências. Sem recurso recorrente ou custo externo.

## Decisões Invariantes
- Metadado novo completo é autoridade de contexto territorial. Município nulo significa regional, mesmo se arquivo/título coincide com município/freguesia.
- Município não resolvido falha; exceções apenas em seed explícita. Freguesia explícita desconhecida não é substituída por título; título é fallback somente se campo estiver vazio.
- Novas colunas source_subregion/source_municipality/source_parish preservam valores; source_region é a Região no novo formato. Legado usa regra antiga.
- Seleção canônica continua por caminho/posição, sem presumir recência. Estatísticas excluem preços conflitantes e suprimem n<10. Sem remoção automática de outliers.
- Região é contexto da coleta, não endereço validado. Catálogo de links auxilia auditoria, não é anúncio nem prova de completude.
- Arquivar cópia das saídas anteriores em .data antes da execução real e verificar hashes de origem e outras fontes antes/depois.

## Constitution Check
| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Segredos | PASS | PASS | Nenhuma credencial |
| II. Estático | PASS | PASS | Sem API/UI/publicação |
| III. Rastreabilidade | PASS | PASS | CAOP, n>=10, ausências e incertezas |
| IV. Coleta responsável | PASS | PASS | Importação offline; método original não atestado |
| V. Raw imutável | PASS | PASS | Novo run, hashes e promoção isolada |
| VI. Privacidade | PASS | PASS | Dados individuais apenas .data |
| VII. Custo | PASS | PASS | Local, custo recorrente adicional zero |

## Project Structure
pipelines/collectors/idealista/{snapshot,territory,prepare,report}.py; pipelines/cli/build_idealista.py; analytics/dbt/seeds/idealista_file_localities.csv; tests/contracts/test_idealista_current_contract.py; tests/unit/test_idealista.py; .docs/reports/; config/sources.yml.

## Complexity Tracking
Sem violações ou nova arquitetura.

## Estratégia de Testes
Comandos: `uv run --locked python -m pytest tests/contracts/test_idealista_current_contract.py -q`; regressão Idealista em tests/{unit,integration,contracts}; `uv run --locked python -m pytest -q --basetemp .data/pytest-007-final`; `uv run --locked ruff check pipelines tests`; build real com `uv run --locked python -m pipelines.cli.build_idealista --local --snapshot-month 2026-11`.
Quatro contratos (orçamento <=5), travados em contract-tests.lock. Adaptador PowerShell não conta Python; pytest comprova quatro casos. Vermelho confirmado: freguesia explícita ausente; distrito recebe DICO errado; metadado parcial não é rejeitado; relatório lança NotImplementedError. Mapeamento: nomes dos testes citam FR-002, FR-003, FR-005. Stub report.write_report não é travado. Contratos antigos da 005 devem continuar verdes.
Referência técnica consultada: Context7 /pandas-dev/pandas, Series.quantile com interpolação linear e exclusão explícita de nulos.

Phase 4 (convergência): os quatro contratos existentes já estavam verdes; dois testes adicionais não travados reproduziram CF-001 com KeyError nos arrays municipais ausentes. Comandos desta retomada:
- `uv run --locked python -m pytest tests/unit/test_idealista_report.py -q --basetemp .data/pytest-007-report-red` — 2 falhas esperadas antes da implementação.
- `uv run --locked python -m pytest tests/unit/test_idealista_report.py tests/unit/test_idealista.py tests/contracts/test_idealista_current_contract.py tests/contracts/test_idealista_import_contract.py tests/integration/test_idealista_build.py tests/integration/test_idealista_import.py -q --basetemp .data/pytest-007-phase4` — 43 passed em 26,46 s.
- `uv run --locked python -m pytest -q --basetemp .data/pytest-007-phase4-full` — 437 passed em 493,04 s; saída integral em `.data/idealista-review-202611/phase4-20261117/pytest-full.log`.
- `uv run --locked python -m pipelines.cli.build_idealista --local --snapshot-month 2026-11` — aprovado, 24 passos dbt; console em `.data/idealista-review-202611/phase4-20261117/build.log`.
- `uv run --locked ruff check pipelines tests` — aprovado; `check-contract-tests.ps1` executado para as sete features com trava, todas íntegras.

E2E de UI/dispositivo não aplicável: esta feature altera importação, preparação e artefatos locais; integração dbt e relatórios são cobertos pelos comandos acima. CI remoto permanece T013.

## Estado Atual
| Área | Estado |
| --- | --- |
| US1 | Contratos territoriais verdes; legado preservado |
| US2 | CF-001 corrigida: JSON municipal e município/tipologia; Markdown com os 225 grupos município/tipologia; 43 testes Idealista verdes |
| Operação | Build real Phase 4 aprovado em 24 passos dbt; 308 municípios/225 grupos reconciliados nos três formatos; 501 arquivos protegidos com hashes preservados |
| Dados | 18.059 únicos; 54 municípios/42 com n>=10; 6.371 regionais; 10.751 com freguesia/937 sem freguesia municipal |
| Suíte geral | Phase 4: 437 passed em 493,04 s; contratos verdes na suíte completa |
| Lint | `uv run --locked ruff check pipelines tests` aprovado |
| CI remoto | PR #8, SHA 0f8972feb079861bd521c0776ade79c3b3ad3920; quality/secrets aprovados, 436 passed/1 skip/1 warning; seis builds dbt verdes |
| Fechamento | 17/17 itens; T013 concluída com evidência remota em ci-validation.md; Implementada, aguardando nova convergência |

## Riscos e Decisões
| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |
| R-001 | Distritos homônimos e ilhas | Cobertura falsa | Metadado explícito nulo mantém região |
| R-002 | Metadados do exportador são contexto | Não prova endereço | Limitação explícita no relatório |
| R-004 | 58 variações de escrita de freguesia | Precisão perdida apesar de nome equivalente | Seed exclusiva do formato novo; código só faz lookup exato por município; legado não muda |
| R-003 | Coleta parcial/limites de páginas | Viés da amostra | Sem inferência nacional/temporal |
| R-005 | Emenda de estilo no contrato 007 | Lint I001/PIE804 bloqueava fechamento | Resolvido: autor respondeu "autorizado"; imports separados e keyword equivalente, sem alterar asserts; trava regravada; 41 testes e lint geral aprovados |
| R-006 | CF-001: recortes incompletos no JSON/Markdown | FR-005 parcialmente atendido | Resolvido: dois arrays municipais no JSON e 225 grupos município/tipologia no Markdown; dois testes adicionais, integração estendida e reconciliação real nos três formatos; contratos preservados |
| R-007 | CF-002: evidência de CI ausente para a revisão final | Gate 1 da constitution | Resolvido: autor autorizou branch/commit/push/PR; CI 44141146329 do SHA 0f8972feb079861bd521c0776ade79c3b3ad3920 aprovou quality/secrets; 436 passed/1 skip/1 warning, seis builds dbt verdes; evidências em ci-validation.md; sem uso de CI antigo |

## Execution Notes
| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |
| 2026-11-17 | US1 | 33 testes territoriais/legados verdes; modo contínuo autorizado pelo autor | Lint do contrato |
| 2026-11-17 | US2 | 39 testes Idealista verdes e 4/4 contratos; report integrado | Ingestão real |
| 2026-11-17 | Polish | Importação changed/unchanged, dbt 24/24; 58 aliases; auditoria e report entregues | Lint do contrato aguarda aprovação |
| 2026-11-17 | Validação geral | 434 passed/501,13 s; 7 travas íntegras | Regressão final: 41 passed/30,77 s; lint de produção/unit/integration aprovado |
| 2026-11-17 | Fechamento autorizado | Emenda estritamente de estilo, trava atualizada, 41 passed/25,52 s, ruff geral e sete travas aprovados | Nenhuma no escopo local |
| 2026-11-17 | Phase 4 / T011 | Dois testes adicionais vermelhos por arrays ausentes; recortes implementados, regressão 43 passed/26,46 s; ruff e trava 007 aprovados | T012 e validação geral |
| 2026-11-17 | Phase 4 / T012 | Backup anterior a execução; dbt real 24/24, 501 hashes protegidos, 308 municípios e 225 grupos conciliados; CSV municipais e estatísticas anteriores idênticos; entrega regenerada | Suíte geral em execução; T013 requer fluxo remoto autorizado |
| 2026-11-17 | Phase 4 / checkpoint local | Suíte geral 437 passed/493,04 s; ruff geral e sete travas aprovados; revisão concreta em delivery-review.md; T011/T012 concluídas | T013: autorização de commit/push e CI do SHA final |
| 2026-11-17 | Phase 4 / T013 | Autorização recebida; commit 0f8972f e PR #8 criados; CI PR 44141146329 e push 44141132271 aprovados, quality/secrets verdes; 17/17 itens | Conferir CI do checkpoint documental e executar sdd-converge posteriormente; PR sem merge |

**PRÓXIMO**: conferir os checks do checkpoint documental no PR #8 e executar sdd-converge posteriormente. T013 concluída com CI da implementação final documentado; PR aberto sobre feature/005-importacao-idealista-manual, sem merge ou publicação.

## Arquivos Principais
- pipelines/collectors/idealista/report.py; tests/unit/test_idealista_report.py; tests/integration/test_idealista_build.py
- .docs/reports/idealista-2026-11*; .data/idealista-review-202611/phase4-20261117/{before,after}.json

## Cuidados para Retomada
- Ambiente foi movido de C: para J:; entrypoints uv antigos foram regenerados por uv sync --locked --reinstall-package dbt-core --reinstall-package pytest --reinstall-package ruff. Nenhuma alteração de lock.

### Descoberta na T007
58 pares de nomes completos foram revisados contra CAOP vigente (uniões de freguesias, pontuação, preposições e ordem de nome). A seed idealista_metadata_parish_synonyms.csv é aplicada somente no formato novo e cada código consultado é validado na dimensão municipal. Nenhum matching aproximado é executado pelo pipeline. regional_stats.csv detalha os grupos sem município.

## Evidência operacional
- Importação changed: 20261117T151513906158Z-d5bd7111; repetição unchanged: 20261117T151553000823Z-155917ac.
- Snapshot SHA-256: 3d57043b54e30e3ab1143d8e0ddeccd9a2097a566833f2fb1edf7e41b705e0a4; 74 JSON/19.531.665 bytes.
- `.data/idealista-review-202611/{before,after}.json`; backup previous-202508 e preparação legacy-regression. 74 origem/raw novos, 324 raw antigos e 25 arquivos de outras fontes verificados. Dez contagens do legado mantidas.
- 24 passos dbt reais aprovados. Cobertura, totais municipais/regionais e por tipologia reconciliados; quartis municipais conferidos com statistics.quantiles inclusive.
- `.docs/reports/idealista-2026-11.md` e quatro extratos agregados. Sem dados pessoais, publicação, AWS, CI remoto ou commit.
- Lint do código de produção e testes adicionais é validado separadamente; dois achados I001/PIE804 no contrato 007 não são ignorados. Foi solicitada aprovação explícita para correção estritamente de estilo e atualização da trava (regra da skill execute 5b).

### Fechamento autorizado
O autor respondeu "autorizado" para os dois ajustes de estilo e a atualização do hash. Foram alterados somente a formatação dos imports e o unpack de um keyword literal no contrato 007. Nenhuma asserção, dado, código de produção ou estatística mudou. Suíte geral anterior preservada como evidência (434 testes); revalidação proporcional após esta mudança: 41 testes Idealista aprovados em 25,52 s, ruff geral limpo, sete travas íntegras e git diff --check aprovado.
