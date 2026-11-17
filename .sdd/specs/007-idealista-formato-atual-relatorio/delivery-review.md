# Revisão para entrega — feature 007

## Alteração proposta

Título de commit/PR: `Support current Idealista exports and complete descriptive reports`

A feature aceita a hierarquia explícita Região/Sub-região/Município/Freguesia,
preservando a interpretação legada. Município vazio permanece regional; os
sinônimos explícitos de freguesia são restritos ao município CAOP e ao formato
novo. A importação mantém bytes, hashes e manifests privados e imutáveis.

O build local inclui relatório agregado Markdown/JSON/CSV. Os recortes por
município e município/tipologia compartilham as mesmas estatísticas, excluem
preços ausentes ou conflitantes e suprimem quartis quando n elegível <10.
O relatório real 2026-11 contém 18.059 anúncios únicos, 54 municípios com amostra,
42 com amostra suficiente e 6.371 anúncios regionais.

## Conteúdo da revisão

- Código Idealista: `snapshot.py`, `territory.py`, `prepare.py`, `report.py` e
  `pipelines/cli/build_idealista.py`.
- Seeds: `idealista_file_localities.csv` e `idealista_metadata_parish_synonyms.csv`.
- Testes: contratos 007 já autorizados na execução inicial, unitários Idealista,
  `test_idealista_report.py` e integração de build.
- Documentação: README, fontes, runbook, `config/sources.yml`, cinco agregados
  `idealista-2026-11*`, artefatos desta feature e memória Idealista do projeto.
- Backlog: incluir apenas o status/progresso da feature 007 na revisão.

Há trabalho de avaliação geográfica posterior em `.sdd/assessments/` e uma ideia
correspondente no backlog. Preservar esse trabalho separadamente; ele não faz
parte do commit proposto da 007. Os dados em `.data/` permanecem privados.

## Validação local

Regressão dirigida: 43 testes aprovados em 26,46 s; suíte geral: 437 testes
aprovados em 493,04 s; ruff geral aprovado; sete travas íntegras.
Build real: 24 passos dbt aprovados. Reconciliação independente dos três formatos:
308 municípios e 225 grupos município/tipologia; CSV municipais e estatísticas
anteriores idênticos. Hashes dos 501 arquivos protegidos preservados.
Backup e evidências: `.data/idealista-review-202611/phase4-20261117/`.
Comandos completos: `plan.md` e Registro da Phase 4 em `tasks.md`.

## Gate de entrega

O trabalho continua local, na branch `feature/005-importacao-idealista-manual`
(HEAD observado antes desta revisão: `912ad12`). Não houve commit, push ou PR
nesta execução. Antes de fechar T013, criar uma branch da 007 pelo fluxo
autorizado, revisar e commitar apenas o escopo acima, enviar ao remoto e obter
CI aprovado para o SHA que contenha a implementação final. Se houver PR, conferir
também o job de segredos. Não fazer merge ou publicação automaticamente.

O gate remoto fica aberto até haver URL, SHA e resultados dos jobs. Depois,
executar sdd-converge novamente.

## Autorização de entrega — 2026-11-17

O autor respondeu "autorizo" para branch, commit, push e PR da 007. Branch nova:
`feature/007-idealista-formato-atual-relatorio`; base de revisão:
`feature/005-importacao-idealista-manual`, porque o PR #7 dessa base para main
ainda está aberto. Assim o novo PR contém somente as mudanças adicionais da 007.
Preservar a avaliação geográfica e sua ideia de backlog fora do commit. Merge e
publicação continuam fora desta autorização.
