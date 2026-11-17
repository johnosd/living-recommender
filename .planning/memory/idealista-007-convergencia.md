# Convergência Idealista 007 — 2026-11-17

A auditoria encontrou duas pendências e anexou `Phase 4: Convergence`, T011–T013,
em `.sdd/specs/007-idealista-formato-atual-relatorio/tasks.md`.

- FR-005 exige Markdown, JSON e CSV por município e município/tipologia.
  `report.py:68-70` não serializa os dois recortes municipais no JSON;
  o Markdown apresenta tipologias do lote e municípios, remetendo o cruzamento
  município/tipologia somente ao CSV. Completar formatos e testes sem enfraquecer
  ou editar os contratos travados; regenerar os agregados entregues.
- O Quality Gate 1 da constitution exige lint/testes no CI. O plano registra
  apenas validação local; falta evidência remota do SHA final da feature 007.
  Não confundir CI anterior da 006 com prova das mudanças atuais, nem executar
  commit/push automaticamente para fechar o gate.

Verificação atual: 41 testes Idealista aprovados em duas chamadas (39 + 2),
ruff geral e sete travas aprovados. Hashes da origem (74), raw novo (74), raw
antigo (324), manifests antigos (2), outras fontes (25) e saídas operacionais
(11) conferidos. Totais e quartis dos 308 municípios reconciliados; quatro
extratos entregues idênticos aos operacionais; 24 resultados dbt existentes
aprovados. Não foi repetida a suíte geral nem refeito o build no lake vigente.

Status resultante: **Convergência Pendente**. Código, contratos, README,
plan.md e fases anteriores de tasks.md preservados. Retomar com sdd-execute
e depois sdd-converge. Evidências: Phase 4, `report.py`, `statistics.json`
local e `.data/idealista-review-202611/{before,after}.json`.

## Retomada execute — Phase 4

T011/T012 foram implementadas: `statistics.json` agora inclui
`municipality_stats` e `municipality_typology_stats`; o Markdown apresenta os
grupos município/tipologia. Dois testes adicionais não travados reproduziram
o problema antes da mudança; regressão dirigida final 43 passed/26,46 s.
Integração verifica a promoção dos arrays e a ausência de grupos artificiais
em snapshot vazio. Nenhum contrato ou trava foi alterado.

Build real regenerado com 24 passos dbt aprovados. Conferência independente
reconciliou 308 municípios e 225 grupos nos três formatos, preservando as
estatísticas anteriores e os bytes dos CSV municipais. Os 501 arquivos
protegidos mantiveram os hashes. Backup anterior ao build e provas novas:
`.data/idealista-review-202611/phase4-20261117/{before,after}.json`.
Os cinco agregados de `.docs/reports/` foram atualizados.

T013 permanece aberta até haver CI do SHA final pelo fluxo de entrega
autorizado. Revisão concreta em `delivery-review.md` da feature; preservar
`.sdd/assessments/` e a ideia geográfica no backlog separadamente. Sem
commit/push automático. A suíte geral desta retomada passou: 437 testes em
493,04 s; ruff geral e sete travas aprovados. Progresso final local: 16/17;
T013 continua aberta. Consultar `plan.md`/Registro da Phase 4 para os comandos.
