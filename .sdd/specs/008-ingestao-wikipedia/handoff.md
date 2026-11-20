# Handoff — Wikipedia 008

## Contexto

Repositório `J:/living-recommender`, branch
`feature/007-idealista-formato-atual-relatorio`, HEAD `42a5f598`.
Stack: Python 3.12, uv, httpx, Parquet e dbt/DuckDB.
Backlog: **Planejada**, sete fases; progresso 0/43 corresponde a 36 tasks
e sete checkboxes de release, nenhum concluído.
Próximo comando: **`/sdd-execute 008-ingestao-wikipedia`**.
Sem commit/push/PR autorizado. Preservar os dois relatórios preexistentes em
`.docs/reports/` e reler alterações externas à feature antes de executar.

## O que a feature entrega

- **US1/P1:** artigos portugueses dos 308 municípios com identidade/revisão validadas e originais imutáveis.
- **US2/P2:** introdução e texto completo por seções, sem perda de blocos ou mistura de entidades.
- **US3/P2:** verificação de atualizações, histórico, idempotência e retomada.
- **US4/P2:** cobertura nacional e prontidão; ausência comprovada pode ser aceita, erro técnico não.

EN/QID são só metadados. TXT antigos ficam no projeto legado. Sem imagens,
declarações Wikidata, IA, site, publicação, agendamento ou AWS.

## Leitura obrigatória, em ordem

Na pasta `.sdd/specs/008-ingestao-wikipedia/`:

1. `spec.md`: escopo e 31 requisitos/7 critérios.
2. `plan.md`: decisões D1–D13, constitution pré/pós, testes e riscos.
3. `tasks.md`: T001–T036, fases e gates; registros ainda vazios.
4. `research.md`: API atual, licença, parser e exceção autorizada.
5. `logic/coleta-e-texto.md`: identidade, DOM, histórico e recuperação.
6. `data-model.md`: snapshots, estados, schemas e caminhos.
7. `contracts/wikipedia-cli.md`: interfaces públicas e comandos.
8. `quickstart.md`: aceite offline/real e limites de prova.
9. `.planning/memory/constitution.md`, na raiz: gates do projeto.

## Testes de contrato

`tests/contracts/test_wikipedia_contract.py`: **5 casos** — dois US1/fase 3,
um US2/fase 4, um US3/fase 5 e um US4/fase 6.
Helper travado: `tests/fixtures/wikipedia/responses.py`.
Ambos são imutáveis no execute; MemoryStorage reutilizado é protegido pela 003.

```powershell
uv run --locked python -m pytest tests/contracts/test_wikipedia_contract.py -q --basetemp .data/tmp/wiki-contracts
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .planning/scripts/powershell/check-contract-tests.ps1 -Slug 008-ingestao-wikipedia
```

Vermelho confirmado: cinco NotImplementedError, sem erro de importação.
Oito travas íntegras; verificar também as features 001–007 após alterações.
O verificador não conta Python: pytest/AST confirmam cinco casos sem desabilitações.

## Stubs criados

Em `pipelines/collectors/wikipedia/`:

- `handler.py`: collect_wikipedia e WikipediaError; coleta ainda não implementada.
- `extract.py`: extract_article; extração ainda não implementada.
- `coverage.py`: assess_wikipedia_coverage; prontidão ainda não implementada.

Os três corpos levantam NotImplementedError; stubs podem ser implementados,
contratos/fixture travados não. Demais CLIs, modelos e dependência BS4 são tarefas futuras.

## Armadilhas já mapeadas

- **R-001 já autorizado:** exceção pontual ao robots para query/parse oficiais; não perguntar novamente pelo mesmo escopo. Sem contorno de bloqueios.
- API atual usa **tocdata**; sections é compatibilidade de leitura, não parâmetro novo de produção.
- Nome/QID não provam município; T010 exige curadoria real dos 308, sem transformar pendência em ausência.
- Não reutilizar v2/api_json genérico: exige indicador e não distingue ausência editorial.
- Congelar contexto; separar última tentativa do conteúdo válido. Mesmo revid pode renderizar HTML diferente.
- Não usar find_next global ou varrer descendentes de tabelas como células da mesma entidade.
- promote_paths sozinho não recupera morte do processo: implementar journal/lock/hashes e proteger vizinhos.
- Usar uv sem --active; fixtures fora da raiz real; dbt só na tag wikipedia.

## Pendências do Analyze

Nenhuma acionável: 38 requisitos/critérios rastreados, quatro stories e sete
princípios cobertos. Pré/pós-design conformes, com exceção aprovada R-001.

## Gate de pronto

Cinco contratos verdes, oito travas íntegras e comandos abaixo aprovados:

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .data/tmp/wiki-final
uv run --locked python -m tests.fixtures.wikipedia.ci_seed --root .data/ci-wikipedia
uv run --locked python -m pipelines.cli.build_wikipedia --local --root .data/ci-wikipedia
```

No planejamento: Ruff global e 63 testes existentes passaram; cinco contratos
novos vermelhos são intencionais. A suíte completa e o novo build ainda são
gates futuros. Completar quickstart real/repetição, preservação de dados e CI
do SHA final no fluxo autorizado. Atualizar inventário, runbook e README em
T030. Hardware/browser não são gates; execução local não prova AWS/publicação.

## Checkpoint de execução — 2026-11-20

O planejamento acima é histórico. A implementação local está concluída, com
543 testes, Ruff, cinco contratos e oito travas íntegros e dbt
fixture/nacional aprovados. Coleta `20261120T185614436452Z-061ad950` e repetição `20261120T190030045538Z-077e4eb3`:
308 valid; 308 unchanged na repetição; zero novos raw e lake idêntico.
616 referências conferidas; 1.319 arquivos anteriores preservados.

Tarefas: 43/43 checkboxes; T035 e checklist concluídos, status Implementada.
O autor autorizou branch/commit/push/PR em 2026-11-20. A branch
`feature/008-ingestao-wikipedia` está publicada no
[PR #9](https://github.com/johnosd/living-recommender/pull/9), baseado em
feature/007 (`42a5f59`), preservando as dependências de Censos/Idealista.

Implementação `5f8c72f6307d66c12afa4c2315aa86e6b16f91e7` aprovada no
[run 44809254508](https://github.com/johnosd/living-recommender/actions/runs/44809254508):
quality e secrets verdes, 542 testes/1 skip específico de Windows no Linux,
Ruff e sete builds isolados aprovados, gitleaks sem segredos encontrados.
O CI do fechamento documental fica nos checks do head final do PR.
Próxima etapa: sdd-converge, mediante solicitação. Os contratos travados
continuam sem alteração; oito travas reconferidas íntegras após a entrega.
Recibos privados e números finais: `.data/receipts/wikipedia-proof/` e plan.md.

## Retomada após auditoria — fase 8

O checkpoint 43/43 acima é histórico. A convergência sobre 87903e9 anexou
T037–T039: corrida no lock órfão, nome CAOP ausente da cobertura e exceção
pública divergente. As três correções estão implementadas; 46/46 checkboxes,
Implementada após aprovação da suíte completa, repetição e CI do código corrigido.

Área: 112 testes; cinco contratos e oito travas íntegros; Ruff; fixture dbt
com 36 resultados aprovados. Build nacional 20261120T225853282336Z-1a5fa083:
308 valid, nomes CAOP verificados em Parquet/CSV, textos preservados e 1.938
arquivos protegidos idênticos. Guard persistente do SO em .locks/wikipedia.guard;
não remover. Recibos phase8-*.json, plan.md e Registro da Fase 8 são o contexto
atual. O PR #9 recebeu o código corrigido; nova sdd-converge é a próxima etapa.

Gates concluídos: 554 testes locais/473,34 s; repetição do build
20261120T230129034273Z-909ab812 unchanged/107,599 s, bytes/mtime vigentes iguais.
Código 3574232 aprovado no run 44833850654: quality/secrets, 553 testes/1 skip
Windows no Linux e sete builds isolados. O fechamento documental segue no
mesmo PR, com checks do head final. Próximo: nova sdd-converge.
