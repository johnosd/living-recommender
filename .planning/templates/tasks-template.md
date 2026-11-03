---
description: "Template de lista de tasks para implementação de feature"
---

# Tasks: [FEATURE NAME]

**Input**: Documentos de design de `sdd/specs/[NNN-feature-slug]/`

**Prerequisites**: plan.md (obrigatório), spec.md (obrigatório para user stories), research.md, data-model.md, contracts/ (condicionais)

**Organization**: Tasks agrupadas por user story pra permitir implementação e teste independentes de cada uma.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Pode rodar em paralelo (arquivos diferentes, sem dependência)
- **[Story]**: A qual user story esta task pertence (ex: US1, US2)
- Incluir caminhos de arquivo exatos nas descrições

## Path Conventions

<!--
  ACTION REQUIRED: substituir pelos caminhos REAIS deste repositório
  (mesma "Structure Decision" registrada em plan.md), descobertos na
  exploração do sdd-plan — nunca copiar de outro projeto.
-->

- [Convenção de caminho 1, ex: lógica em `src/`]
- [Convenção de caminho 2, se houver, ex: interface em `recorder.html` e configuração em `manifest.json`]

<!--
  IMPORTANT: as tasks abaixo são um EXEMPLO ilustrativo. O sdd-plan DEVE
  substituir por tasks reais baseadas em spec.md/plan.md/data-model.md/
  contracts/. Cada fase de user story segue o template de 5 blocos:
  Goal/Objetivo → Implementation/Checklist → Tests/Testes da fase →
  Critério de Conclusão → Registro da Fase (deixado vazio aqui; só o
  sdd-execute preenche, conforme a fase avança).
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialização do projeto e estrutura básica, se necessário.

- [ ] T001 [Descrição]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestrutura que DEVE estar pronta antes de qualquer user story.

**⚠️ CRITICAL**: Nenhuma user story pode começar antes desta fase terminar.

- [ ] T002 [Descrição]

**Checkpoint**: Fundação pronta - user stories podem começar.

---

## Phase 3: User Story 1 - [Título] (Priority: P1) 🎯 MVP

**Objetivo**: [O que esta story entrega]

**Independent Test**: [Como verificar que esta story funciona isoladamente]

### Contrato da Fase

<!--
  Testes de contrato (sdd-plan passo 7.5) que esta fase deve deixar verdes.
  Já existem e estão TRAVADOS em contract-tests.lock — o sdd-execute não os
  escreve nem edita. Omita este bloco se a fase não tem contrato.
-->

- `[nome do teste]` — [origem: FR-### / US1-AC1]
- Comando: `[comando exato que roda só os contratos]`

### Implementation

- [ ] T003 [P] [US1] [Descrição] em `[caminho real do repositório]` → contrato: `[nome do teste]`
- [ ] T004 [US1] [Descrição] em `[caminho real do repositório]`

### Testes da Fase

<!-- Testes ADICIONAIS escritos pelo sdd-execute, fora dos arquivos de contrato. -->

- [ ] T005 [P] [US1] Teste de [comportamento] em `[caminho real do repositório]`

**Critério de Conclusão**: [Começa pelo contrato, como comando verificável — ex: "`<comando>` → N/N verdes e `check-contract-tests.ps1` íntegro" — depois o resto do que "pronto" significa nesta story]

**Checkpoint**: User Story 1 funcional e testável isoladamente.

**Registro da Fase**:

- Status: (vazio — preenchido pelo sdd-execute ao fechar o checkpoint)
- Feito:
- Contrato:
- Testes executados:
- Pendências:

---

[Adicionar mais fases de user story conforme necessário, seguindo o mesmo padrão]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Melhorias que afetam múltiplas user stories.

- [ ] TXXX Limpeza de código
- [ ] TXXX Rodar validação de `quickstart.md`

### Checklist de Release

<!--
  Itens marcados pelo sdd-execute conforme cada fase fecha, mais gates
  cross-cutting da feature. Ecoa o pre-acceptance checklist da constitution.md.
-->

- [ ] Fase 3 (User Story 1) concluída
- [ ] Testes de contrato todos verdes na suíte completa e `check-contract-tests.ps1` íntegro (omita se a feature não tem contrato)
- [ ] Testes aplicáveis executados com `npm test`
- [ ] Build gerado com `npm run build`, sem editar `dist/` manualmente
- [ ] Extensão recarregada no Chrome e fluxo afetado validado manualmente (quando aplicável)
- [ ] Permissões, captura, áudio e transcrição validados separadamente quando tocados pela feature
- [ ] `quickstart.md` executado com sucesso

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — BLOQUEIA todas as user stories
- **User Stories (Phase 3+)**: dependem do Foundational; podem rodar em paralelo ou em ordem de prioridade (P1 → P2 → P3)
- **Polish (fase final)**: depende de todas as user stories desejadas estarem completas

### Parallel Opportunities

- Tasks marcadas `[P]` na mesma fase podem rodar em paralelo
- User stories diferentes podem ser trabalhadas em paralelo depois do Foundational

---

## Parallel Example: User Story 1

```bash
# Tasks marcadas [P] na Fase 3 podem rodar juntas
Task: "T003 [P] [US1] ..."
Task: "T004 [P] [US1] ..."
```

---

## Implementation Strategy

### MVP First (User Story 1 apenas)

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (bloqueia todas as stories)
3. Completar Fase 3: User Story 1
4. **PARAR E VALIDAR**: testar User Story 1 isoladamente

### Incremental Delivery

1. Setup + Foundational → fundação pronta
2. User Story 1 → testar isoladamente → considerar entrega (MVP)
3. Repetir para as próximas stories, sempre sem quebrar as anteriores

## Notes

- `[P]` = arquivos diferentes, sem dependência
- `[Story]` mapeia a task pra uma user story específica
- Commitar após cada task ou grupo lógico coerente
- Parar em qualquer checkpoint pra validar a story isoladamente

<!-- sdd-converge anexa "## Phase N: Convergence" abaixo desta linha -->
