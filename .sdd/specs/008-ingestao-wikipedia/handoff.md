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

Tarefas: 41/43 checkboxes; restam T035 e o item de release que exige CI remoto
e secrets do SHA final. O status permanece Em Execução. O autor autorizou
branch/commit/push/PR em 2026-11-20. A entrega parte de feature/007, HEAD
42a5f59, também presente no remoto; ela contém dependências de Censos/Idealista
ainda à frente de origin/main. Entrega autorizada: branch própria 008 e PR
com base em feature/007, preservando a pilha e os commits existentes.

Executar a entrega autorizada e conferir quality/secrets do SHA final;
então marcar T035/checklist e atualizar status. sdd-converge pode auditar a
feature com esse checkpoint. Os contratos travados continuam sem alteração.
Recibos privados e números finais: `.data/receipts/wikipedia-proof/` e plan.md.
