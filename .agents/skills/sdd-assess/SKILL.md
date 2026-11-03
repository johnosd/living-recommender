---
name: sdd-assess
description: Valida uma ideia antes de comprometer com uma spec — Explora (opcional) → Define → Decide, terminando num veredito go/needs-clarification/kill nunca inflado, com handoff pro sdd-specify só quando for go. Use quando o usuário pedir para avaliar/validar uma ideia, decidir se vale a pena construir algo, ou triar uma ideia do backlog antes de especificar. NÃO use quando já está claro que a feature vai ser construída (aí é direto sdd-specify) nem para decisões de arquitetura (use sdd-adr) nem para bugs (use sdd-bugfix).
---

# sdd-assess

Skill independente, inspirado no extension "assess" (intake→research→define→
shape→decide) do GitHub spec-kit, condensado em 3 fases internas: **Explora**
(fusão enxuta de intake+research, opcional) → **Define** (estágio mínimo
viável) → **Decide** (scorecard + veredito). Sem o estágio Shape separado do
original — abordagens candidatas ficam como uma seção leve dentro de Decide,
não um artefato próprio.

**Discovery responde "vale a pena construir isso?" — Delivery (`sdd-specify`
em diante) responde "como construímos?"**. Matar uma ideia com razão
documentada é um resultado bom, não uma falha — a maioria das ideias que
passam por aqui deveria ser descartada ou pedir mais clareza antes do
`Decide` dar `go`.

## Contrato por fase

| Fase | Obrigatória? | Escreve em | Produz |
|---|---|---|---|
| **Explora** | Não — pule se a ideia já chegou clara | `explora.md` | Ideia capturada + evidência a favor **e contra** |
| **Define** | Sim — estágio mínimo viável | `problem.md` | Problema, usuários afetados, goals/non-goals, métricas de sucesso |
| **Decide** | Sim (exige `problem.md`) | `decision.md` | Scorecard + veredito `go`/`needs-clarification`/`kill` |

Os 3 arquivos vivem em `sdd/assessments/<slug>/` — pasta própria na raiz do
repositório (sem numeração, só o slug), igual a `sdd/bugs/`.

## Fluxo

### 1. Resolve a ideia e a fase

```powershell
.\.planning\scripts\powershell\resolve-assessment.ps1 -Title "<resumo da ideia>" -Json
# ou, com slug já conhecido de uma fase anterior na mesma conversa:
.\.planning\scripts\powershell\resolve-assessment.ps1 -Slug <slug> -Json
```

Isso cria/resolve `sdd/assessments/<slug>/` e reporta `NEXT_PHASE`
(`define`/`decide`/`complete`) — `explora` nunca é reportado automaticamente
porque é opcional; ofereça rodá-la você mesmo se a ideia parecer precisar de
mais evidência antes do `Define`, mas não trave nisso.

Se a fase resolvida for `complete`, informe o veredito já registrado e
pergunte se o usuário quer reabrir (rodar Define ou Decide de novo com
informação nova) ou está satisfeito.

### 2. Fase Explora (opcional, read-only sobre código)

1. **Captura a ideia bruta** — texto colado, URL, ou "ideia do backlog". Se
   for URL, busque o conteúdo antes de prosseguir.
2. **Reúne evidência a favor**: dados, precedente, sinal de demanda — o que
   houver disponível. Marque afirmações sem fonte como `ASSUMPTION`.
3. **Reúne evidência contra, sempre** — essa seção é obrigatória mesmo que
   curta. Força considerar o lado cético antes de continuar. "Nenhuma
   encontrada" é válido, mas precisa ser uma conclusão ativa, não uma seção
   vazia deixada em branco.
4. Escreve `explora.md` a partir de
   `.planning/templates/assessment-explora-template.md`.
5. Relata: slug, próximo passo ("rode a fase Define").

### 3. Fase Define (mínimo viável)

1. Pode rodar direto sobre a entrada do usuário, sem exigir `explora.md` —
   se ele existir, leia e incorpore; se não, tudo bem.
2. Se o Problem Statement, usuários afetados, goals/non-goals ou métricas de
   sucesso ficarem ambíguos a partir do que o usuário deu, **pergunte
   diretamente em vez de assumir** — sem teto artificial de perguntas (numa
   ideia pouco clara, passar de 10 é normal). Quando houver alternativas,
   use a ferramenta de perguntas estruturadas disponível no ambiente; se não
   houver, apresente as opções no chat. Ordene-as **da mais recomendada para a
   menos recomendada** e marque a primeira explicitamente como recomendada.
3. **Problem Statement**: 1-2 frases, o problema real, não a solução.
4. **Usuários/partes afetadas**: quem sente isso e como.
5. **Goals** e **Non-Goals**: tão importante um quanto o outro — non-goals
   evita que o escopo infle silenciosamente depois.
6. **Success Metrics**: como saber que resolveu, de forma mensurável.
7. **Cost of Inaction**: o que acontece se isso não for feito — ajuda a
   julgar prioridade de verdade.
8. Escreve `problem.md` a partir de
   `.planning/templates/assessment-problem-template.md`.
9. Relata: slug, próximo passo ("rode a fase Decide").

### 4. Fase Decide

1. **Pré-requisito**: `problem.md` deve existir — senão, pare e peça pra
   rodar Define primeiro.
2. **Preencha o scorecard** — cada critério (validade do problema, força da
   evidência, valor vs. custo de inação, viabilidade/apetite, fit
   estratégico) avaliado como `strong`/`adequate`/`weak`/`unknown`. Antes de
   marcar um critério como `unknown` só porque a informação não foi dada,
   **pergunte ao usuário** — sem teto artificial de perguntas. Quando houver
   alternativas, use a ferramenta de perguntas estruturadas disponível ou
   apresente-as no chat, da mais recomendada para a menos recomendada. O
   `unknown` que sobrar depois de perguntar precisa ser
   **reconhecido explicitamente**, nunca varrido pra baixo do tapete pra
   fechar o veredito mais rápido.
3. **Liste 1-3 abordagens candidatas** em nível de conceito (não design de
   implementação) e recomende uma, se o veredito parecer `go`.
4. **Aplique o veredito**:
   - **go** — exige problema válido no scorecard e evidência
     `adequate`+ em todos os critérios centrais (nunca `weak`/`unknown`
     nos críticos). Se não atingir isso, **desça pra `needs-clarification`**
     em vez de inflar.
   - **needs-clarification** — liste as perguntas bloqueantes e qual fase
     revisitar (`explora` ou `define`).
   - **kill** — registre o motivo. Isso é um resultado bom, não uma falha;
     relate sem tom de desculpa.
5. Escreve `decision.md` a partir de
   `.planning/templates/assessment-decision-template.md`. Na seção "Se go —
   Handoff", resuma problema/abordagem/escopo/métricas/perguntas em aberto
   de um jeito que o `sdd-specify` consiga usar como contexto de entrada.
6. Se a ideia veio de uma entrada em `.planning/backlog.md` → `## Ideias
   Futuras`: remova essa entrada em `go` ou `kill` (o registro permanente
   agora é `decision.md`); mantenha a entrada se `needs-clarification`
   (ainda é "futuro", pendente).
7. Relata: slug, caminho do `decision.md`, veredito, próximo passo por
   veredito:
   - **go** → recomende rodar `sdd-specify`, usando o handoff de
     `decision.md` como contexto (não repita a entrevista do zero se a
     informação já está ali).
   - **needs-clarification** → recomende revisitar a fase indicada.
   - **kill** → nenhum próximo passo; o registro fica pra referência futura.

## Guardrails

- Nenhuma fase edita código-fonte — só leem o repositório/web e escrevem
  dentro de `sdd/assessments/<slug>/`.
- Evidência nunca é superestimada — afirmação sem fonte é `ASSUMPTION`,
  não fato.
- Veredito nunca é inflado — `go` tem barra alta (evidência `adequate`+,
  problema válido); dúvida vira `needs-clarification`, não um `go` otimista.
- Nunca sobrescreve um relatório de fase já existente sem confirmar com o
  usuário.
- Não insere hooks nem se auto-invoca a partir de `sdd-specify` — é um
  funil que se entra deliberadamente.

## Handoff

Não se conecta automaticamente à pipeline `sdd-specify → sdd-plan →
sdd-execute → sdd-converge` — é standalone, como `sdd-adr` e `sdd-bugfix`.
O único acoplamento é por escolha: um veredito `go` de Decide entrega seu
resumo de handoff pro `sdd-specify`, que o usuário decide quando rodar.
