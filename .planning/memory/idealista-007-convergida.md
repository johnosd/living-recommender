# Idealista 007 — convergida em 2026-11-17

Segunda passada de sdd-converge: nenhuma lacuna remanescente em FR-001–FR-007,
SC-001–SC-004 ou nas stories P1. CF-001 foi fechada pelos recortes municipais
em JSON e município/tipologia em Markdown; CF-002 foi fechada pelo CI atual.
Status local: **Convergida, 17/17 itens**. Esta nota sucede os estados históricos
pendentes/Implementada das notas anteriores.

Verificação atual: 43 testes Idealista passaram em 33,99 s; ruff e sete travas
aprovados. Os 308 registros municipais e 225 grupos município/tipologia foram
reconciliados nos três formatos, com conferência independente de quartis,
exclusão de conflitos e supressão para n elegível <10. Conferidos 501 hashes
protegidos, os quatro extratos entregues e os 24 resultados dbt reais existentes;
nenhum novo build no lake vigente. Os 58 aliases novos conferidos na dimensão
CAOP. Não foi repetida a suíte geral anterior de 437 testes.

PR #8 continua aberto sobre feature/005-importacao-idealista-manual, HEAD
`555f67e23ee0b98fed3e312119d2ad1fe115a329`. CI PR `44142662361` e push
`44142652092` confirmados com sucesso no mesmo SHA; quality/secrets verdes,
436 passed/1 skip Windows/1 warning preexistente, seis builds dbt aprovados e
gitleaks sem vazamentos em 30 commits. Logs em `.data/idealista-review-202611/phase4-20261117/ci-final.*`.

Sincronização desta convergência é local: status da spec e backlog, uma seção
Resultado Final no plano e prefixos Resolvido nos riscos mitigados. tasks.md
permaneceu byte-idêntico (SHA-256
`a26d81c59f403fdcdfd1fa53a4d02b3b39f202ae8f2b8eadf5f4ea5f4b834456`);
README já descrevia a entrega e não mudou. Nenhum código, contrato ou dado
alterado; sem novo commit/push, merge ou publicação. Preservar a avaliação
geográfica e sua ideia no backlog fora do escopo desta feature.

Evidências: spec/plan/tasks 007, Resultado Final e checks atuais do PR #8.
