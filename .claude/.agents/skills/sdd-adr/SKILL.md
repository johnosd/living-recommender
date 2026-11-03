---
name: sdd-adr
description: Documenta ou emenda uma decisão arquitetural fundamental do projeto (stack, plataforma, banco de dados, framework) como ADR em sdd/adr/, com contexto, alternativas rejeitadas e consequências assumidas. Use quando o usuário pedir para documentar uma decisão de arquitetura, registrar um ADR, discutir e decidir entre opções técnicas antes de começar a implementar, ou atualizar uma decisão já tomada. Diferente de sdd-specify/sdd-plan/sdd-execute/sdd-converge — não pertence à pipeline de uma feature específica, pode rodar antes de qualquer sdd/specs/ existir. NÃO use para decisões técnicas locais de uma única feature (isso vai em Decisões Invariantes de plan.md, via sdd-plan).
---

# sdd-adr

Skill independente da pipeline `sdd-specify → sdd-plan → sdd-execute →
sdd-converge` — não exige nenhuma feature existente, e pode (deve, quando
fizer sentido) rodar antes da primeira feature ser especificada, durante a
discussão inicial de arquitetura do projeto.

Diferença de escopo pros outros artefatos do sistema:

| Artefato | Escopo | Natureza |
|---|---|---|
| `constitution.md` | Projeto inteiro | Regras `DEVE`, gate formal, terso |
| ADR (`sdd/adr/`) | Projeto inteiro | Decisão + raciocínio completo + alternativas rejeitadas, permanente |
| `plan.md` → Decisões Invariantes | Uma feature | Local, descartável quando a feature converge |

Uma ADR registra **por que** uma decisão foi tomada e o que foi
conscientemente rejeitado — não só a conclusão.

## Fluxo

### 1. Confere ADRs existentes

Liste `sdd/adr/` (se existir). Se a discussão que o usuário está
propondo se relaciona a uma ADR já registrada, isso é uma **emenda**, não uma
ADR nova — vá pro passo 4. Caso contrário, é uma ADR nova — siga normalmente.

### 2. Discussão aberta

Diferente da entrevista mais fechada do `sdd-specify`, aqui a conversa é
sobre **trade-offs técnicos**: requisitos e constraints reais (custo,
operação, equipe, prazo), opções candidatas, prós/contras de cada uma.
Explore de verdade — pergunte o que for preciso pra entender o contexto,
proponha alternativas que o usuário não tenha mencionado se forem
relevantes, questione suposições. Isso não é um checklist de 5 perguntas, é
uma discussão técnica real.

### 3. Determina o resultado da discussão

- **Decisão nova, sem ADR relacionada**: siga pro passo 4a.
- **Emenda a uma ADR existente** (a decisão antiga ficou errada, incompleta,
  ou foi substituída): siga pro passo 4b — **nunca** reescreva a ADR
  original.

### 4a. Cria a ADR

```powershell
.\.planning\scripts\powershell\new-adr.ps1 "<título da decisão>" -Json
```

Escreva o conteúdo completo a partir de `.planning/templates/adr-template.md`:
Status (`Aceita`, salvo se ficou em aberto), Data, Contexto, Decisão (com
detalhe de implementação quando ajudar), Alternativas Consideradas (cada uma
com motivo concreto de rejeição — nunca "pior", sempre o porquê real),
Consequências (Positivas/Negativas, incluindo trade-offs conscientemente
aceitos), Caminho de Migração (sob quais condições isso seria revisitado).

### 4b. Emenda uma ADR existente

**Nunca reescreva o texto original.** Adicione uma nota inline no ponto
afetado da ADR antiga:

```markdown
**Atualização (ADR-0XX):** [o que mudou e por quê, resumido]. Ver ADR-0XX
para o raciocínio completo.
```

Se a emenda for substancial o bastante pra merecer seu próprio raciocínio
completo (não só uma correção pontual), crie também uma ADR nova (passo 4a)
que a nota aponta, com `## Status` mencionando que supera/atualiza a
anterior. Se for só uma correção factual pequena, a nota inline sozinha
basta — não force uma ADR nova pra tudo.

### 5. Considera promoção pra constitution

Pergunte ao usuário: essa decisão deveria ser um **gate obrigatório** em
todo plano futuro (ex: "toda feature DEVE usar X", não só "hoje usamos X")?
Se sim, sugira adicionar como `Restrição do Projeto` em
`.planning/memory/constitution.md` — mas não edite a constitution
diretamente por este skill; é mais seguro deixar isso pro usuário confirmar
explicitamente ou pro próximo `sdd-plan` incorporar. A maioria das ADRs
**não** precisa virar regra de constitution — só as que devem bloquear
qualquer feature futura que as violar.

### 6. Relata

Caminho salvo, se emendou alguma ADR anterior (e qual), e se recomendou
promoção pra constitution.

## Handoff

`sdd-plan` lê `sdd/adr/` durante a exploração de toda feature nova —
as decisões registradas aqui não devem ser relitigadas silenciosamente
dentro do planejamento de uma feature específica.
