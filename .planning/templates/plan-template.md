# Implementation Plan: [FEATURE]

**Slug**: `[NNN-feature-slug]` | **Date**: [DATE] | **Spec**: `sdd/specs/[NNN-feature-slug]/spec.md`

**Nota**: Este template é preenchido pelo skill `sdd-plan`; a definição do skill
descreve o fluxo de execução completo.

## Summary

[Extraído da spec: requisito principal + abordagem técnica]

## Technical Context

**Language/Version**: [ex: JavaScript no Chrome Manifest V3, ou NEEDS CLARIFICATION]

**Primary Dependencies**: [ex: APIs da extensão Chrome, Web Audio API, Webpack]

**Storage**: [ex: chrome.storage.local para configuração, ou N/A]

**Testing**: [ex: Jest e validação manual da extensão carregada no Chrome]

**Target Platform**: [ex: extensão Chrome Manifest V3]

**Performance Goals**: [se aplicável, ou N/A pra MVP]

**Constraints**: [restrições específicas do domínio]

**Scale/Scope**: [escala relevante, ou N/A para gravação local]

## Decisões Invariantes

<!--
  Axiomas/regras travadas desta feature específica, definidas agora e
  referenciadas por todas as fases em tasks.md. Diferente da Constitution
  (projeto inteiro) e diferente de Riscos e Decisões (log evolutivo) — aqui
  são decisões que não devem ser revisitadas sem reabrir o design.
-->

- [Decisão travada 1]

## Constitution Check

*GATE: deve passar antes da Fase 0. Reavaliado após o design da Fase 1.*

| Princípio | Pré-Design | Pós-Design | Notas |
| --- | --- | --- | --- |
| I. Segurança por Padrão | | | |
| II. Fronteiras Sustentáveis | | | |
| III. Qualidade Verificável | | | |
| IV. Disciplina de Escopo do MVP | | | |
| V. Corretude Operacional | | | |

## Project Structure

### Documentation (this feature)

```text
sdd/specs/[NNN-feature-slug]/
├── spec.md              # Saída do sdd-specify
├── plan.md               # Este arquivo (saída do sdd-plan)
├── research.md            # Fase 0, condicional
├── data-model.md          # Fase 1, condicional
├── quickstart.md          # Fase 1, condicional
├── contracts/             # Fase 1, condicional
├── tasks.md               # Saída do sdd-plan (fase de tasks)
└── history.md              # Condicional, criado pelo sdd-execute quando arquiva
```

### Source Code (repository root)

<!--
  ACTION REQUIRED: Substituir pela árvore REAL deste repositório, descoberta
  na exploração do sdd-plan (não um placeholder genérico, mas também não uma
  estrutura fixa de outro projeto — cada repo onde este skill rodar tem a
  sua). Remover as opções não usadas.
-->

```text
# [EXEMPLO — SUBSTITUIR PELA ÁRVORE REAL] Extensão Chrome
src/
recorder.html
popup.html
manifest.json
webpack.config.js
```

**Structure Decision**: [documentar a estrutura escolhida e referenciar os caminhos reais tocados por esta feature, como encontrados no repositório — nunca copiar de outro projeto]

## Complexity Tracking

> **Preencher SOMENTE se o Constitution Check tiver violações que precisam ser justificadas**

| Violação | Por que é necessária | Alternativa mais simples rejeitada porque |
| --- | --- | --- |

## Estratégia de Testes

<!--
  Filosofia/prioridade de teste no nível da feature inteira. Complementa, sem
  substituir, os "Testes da fase"/"Registro da Fase" específicos de cada fase
  em tasks.md.
-->

Prioridade: unitário → contrato/integração → E2E → manual (último recurso).

Comandos-base:

```powershell
[comando de build real do projeto]
[comando de teste real do projeto]
```

### Testes de Contrato

<!--
  Escritos e travados pelo sdd-plan (passo 7.5), máximo 5 casos de teste.
  O sdd-execute só pode fazê-los passar, nunca editá-los. Se a feature não
  tem nenhum, troque a tabela por uma linha dizendo por quê.
-->

Arquivos travados em `contract-tests.lock`: `[caminho real do arquivo de contrato]`

Comando: `[comando exato que roda só os arquivos de contrato]`

| Teste | Origem | Fase | Vermelho esperado (antes do execute) |
| --- | --- | --- | --- |
| [nome do teste] | [FR-### / US1-AC1 / Constitution: ...] | [Fase N] | [ex: `Error: not implemented` / asserção X] |

Stubs criados pelo plan (ponto de partida do execute, não travados): `[caminhos]`

## Estado Atual

<!-- Sobrescrita a cada checkpoint pelo sdd-execute. Vazia na criação. -->

| Área | Estado |
| --- | --- |

## Riscos e Decisões

<!--
  IDs estáveis (R-001, R-002...), nunca deletados. Item resolvido ganha
  prefixo "Resolvido:" na célula de Mitigação em vez de sumir da tabela.
-->

| ID | Risco/Decisão | Impacto | Mitigação/Encaminhamento |
| --- | --- | --- | --- |

## Execution Notes

<!--
  Tabela append-only, mantida pelo sdd-execute. Quando passar de ~40 linhas,
  arquivar as mais antigas (exceto as ~10 mais recentes) em history.md,
  substituindo por uma linha de resumo consolidado aqui.
-->

| Data | Fase/Story | Resumo | Pendência Principal |
| --- | --- | --- | --- |

**PRÓXIMO**: —

## Arquivos Principais

<!-- Sobrescrita a cada checkpoint — foco da etapa atual, não a árvore inteira. -->

- (nenhum ainda)

## Cuidados para Retomada

<!-- Armadilhas operacionais específicas desta feature, anexadas conforme descobertas. -->

- (nenhum ainda)
