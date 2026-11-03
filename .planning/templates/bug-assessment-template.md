# Bug Assessment: [Título Curto]

<!--
  Preenchido pela fase Assess do sdd-bugfix. Este arquivo é o CONTRATO que a
  fase Fix trabalha em cima — ela fica travada aos arquivos listados em
  "Files likely to change" a menos que descubra evidência nova (o que precisa
  ser registrado em fix.md, nunca reescrito aqui).
-->

- **Slug**: [SLUG]
- **Criado**: [AAAA-MM-DD]
- **Origem**: [URL ou "texto colado"]
- **Veredito**: valid | likely valid, needs reproduction | invalid
- **Severidade**: critical | high | medium | low

## Report

<!-- Conteúdo citado/condensado do report original. Se veio de URL, inclua título + trecho curto e o link. -->

[REPORT]

## Symptom

<!-- 1-2 frases: comportamento observado vs. esperado. -->

[SYMPTOM]

## Reproduction

1. [passo]
2. [passo]

<!-- Marque incertezas como [NEEDS CLARIFICATION: ...] em vez de adivinhar. -->

## Suspected Code Paths

- `caminho/arquivo.ext:linha` — [por quê]

## Root Cause Hypothesis

<!-- Um parágrafo. Declare a confiança: high / medium / low. -->

[ROOT_CAUSE_HYPOTHESIS]

## Proposed Remediation

**Preferida**: [descrição da mudança]

**Alternativas** (opcional):
- [alternativa + trade-off]

**Files likely to change**:
- `caminho/arquivo.ext`

**Tests to add or update**:
- [descrição do teste]

## Risks & Considerations

- [risco]

## Open Questions

- [NEEDS CLARIFICATION: ...]
