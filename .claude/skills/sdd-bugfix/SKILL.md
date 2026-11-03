---
name: sdd-bugfix
description: Avalia, corrige e verifica bugs reportados fora de uma feature ativa, em fases Assess, Fix e Test registradas em sdd/bugs/. Use para triar, corrigir ou verificar um bug. Bugs descobertos durante sdd-execute são tratados nessa execução; features novas usam sdd-specify.
---

# sdd-bugfix

Skill independente, inspirado no extension "bug" (assess → fix → test) do
GitHub spec-kit, adaptado pra uma única skill com 3 fases internas em vez de
3 comandos separados — cada fase tem um contrato de leitura/escrita
diferente, e nenhuma fase superestima o que não verificou de verdade.

Complementa o tratamento de bugs já embutido no `sdd-execute` (passo 6):
aquele é pra bugs achados **durante** a implementação de uma feature; este é
pra bugs relatados **independentemente** — um usuário reportou algo, ou uma
entrada `[Bug]` do `.planning/backlog.md` foi escolhida pra resolver agora.

## Contrato por fase

| Fase | Pode editar código? | Escreve em | Veredito |
|---|---|---|---|
| **Assess** | Não — só lê o repositório | `assessment.md` | `valid` / `likely valid, needs reproduction` / `invalid` + severidade |
| **Fix** | **Sim — só esta fase** | `fix.md` | `applied` / `partial` / `not-applied` |
| **Test** | Não — só reroda checagens | `test.md` | `verified` / `partial` / `failed` |

Os 3 arquivos vivem em `sdd/bugs/<slug>/` — pasta própria, separada de
`sdd/specs/`, sem numeração sequencial (o slug é o único identificador, igual ao
design original).

Cada fase termina rodando `update-bug-status.ps1`, que atualiza o painel
`## Bugs` em `.planning/backlog.md` (fase atual, veredito/status, próximo
passo). É o análogo do `## Features` que `update-feature-status.ps1` mantém
pras features — sem isso, um bug em andamento não deixava rastro em lugar
nenhum fora da própria pasta. Antes de rodar Assess num bug novo, olhe esse
painel: se já existir uma linha pro mesmo assunto, é retomar a fase indicada
em vez de recomeçar do zero.

## Fluxo

### 1. Resolve o bug e a fase

```powershell
.\.planning\scripts\powershell\resolve-bug.ps1 -Title "<resumo do bug>" -Json
# ou, se já tem um slug de uma fase anterior na mesma conversa:
.\.planning\scripts\powershell\resolve-bug.ps1 -Slug <slug> -Json
```

Isso cria/resolve `sdd/bugs/<slug>/` e reporta `NEXT_PHASE`
(`assess`/`fix`/`test`/`complete`) baseado em quais arquivos já existem. Rode
a fase indicada — não pule fase nem adivinhe o slug se houver mais de um
candidato em `sdd/bugs/` (liste e pergunte ao usuário qual é).

Se a fase resolvida for `complete`, informe o status final (veredito do
`test.md`) e pergunte se o usuário quer reabrir (rodar Assess de novo com
evidência nova) ou se está satisfeito.

### 2. Fase Assess (read-only)

1. **Ingere o report** — texto colado ou URL. Se for URL, busque o conteúdo
   (título, descrição, stack trace, passos de reprodução) antes de
   prosseguir.
2. **Resume o sintoma** em 1-2 frases: o que acontece vs. o que era
   esperado.
3. **Localiza os caminhos de código suspeitos** — busque no repositório por
   símbolos, mensagens de erro, nomes de rota/componente citados no report.
   Liste candidatos com justificativa curta; não exceda o que a evidência
   sustenta.
4. **Avalia mérito e severidade**: `valid` (reproduzível ou claramente
   fundamentado no código) / `likely valid, needs reproduction` (plausível,
   não verificado) / `invalid` (não é bug — declare por quê). Severidade:
   `critical`/`high`/`medium`/`low`.
5. **Propõe uma remediação**: abordagem preferida + alternativas (se
   houver), arquivos que provavelmente vão mudar, testes a adicionar. Não
   escreva o patch ainda — isso é da fase Fix.
6. Escreve `assessment.md` a partir de
   `.planning/templates/bug-assessment-template.md`.
7. Se a origem for uma entrada `[Bug]` de `.planning/backlog.md`, remova
   essa entrada (o bug agora está sendo rastreado em `sdd/bugs/`).
8. Rode
   `.\.planning\scripts\powershell\update-bug-status.ps1 -Slug <slug>` —
   atualiza o painel `## Bugs` em `backlog.md` com fase/veredito/próximo
   passo, pra dar pra retomar de relance sem abrir a pasta do bug.
9. Relata: slug, caminho do `assessment.md`, veredito, severidade, próximo
   passo ("rode a fase Fix nesse bug").

### 3. Fase Fix (única fase que edita código)

1. **Pré-requisito**: `assessment.md` deve existir — senão, pare e peça pra
   rodar a fase Assess primeiro.
2. Leia `assessment.md` por inteiro. Trate **Proposed Remediation**, **Files
   likely to change**, **Tests to add or update** e **Risks &
   Considerations** como o contrato desta fase.
3. Se o veredito foi `invalid`, pare — não há o que corrigir. Informe o
   usuário.
4. Se o veredito foi `likely valid, needs reproduction` com
   `[NEEDS CLARIFICATION]` não resolvido, confirme com o usuário antes de
   prosseguir.
5. **Confirme o plano** em 3-6 bullets antes de mexer em código.
6. **Aplique a remediação** — fique dentro dos arquivos listados no
   assessment, a menos que evidência nova exija mais; nesse caso, **pare de
   editar**, registre a descoberta em `fix.md` → **Deviations from
   Assessment**, e recomende rodar a fase Assess de novo em vez de
   continuar sobre uma premissa errada.
7. Adicione/atualize os testes que o assessment apontou, pra travar o bug
   contra regressão.
8. Mudança mínima — não refatore código não relacionado.
9. Rode os testes locais relevantes às mudanças (comandos reais do
   projeto). Não rode suites destrutivas/dependentes de rede sem
   consentimento explícito.
10. Escreve `fix.md` a partir de `.planning/templates/bug-fix-template.md`.
11. Rode
    `.\.planning\scripts\powershell\update-bug-status.ps1 -Slug <slug>` —
    atualiza o painel `## Bugs` em `backlog.md`.
12. Relata: slug, caminho do `fix.md`, status, próximo passo ("rode a fase
    Test").
13. Sugere ponto de commit — nunca commita sozinho.

### 4. Fase Test (read-only)

1. **Pré-requisito**: `fix.md` deve existir — senão, pare e peça pra rodar
   a fase Fix primeiro.
2. Releia o sintoma/reprodução original (`assessment.md`) e o que foi
   mudado (`fix.md`).
3. **Planeje a validação**: rerrode a reprodução original (ou equivalente
   automatizado), rode os testes adicionados no fix, rode suite de
   regressão relevante, lint/type-check se o projeto usar.
4. **Execute as checagens**. Se uma checagem for destrutiva/cara/dependente
   de rede, pule e registre como `skipped` com o motivo — não rode sem
   consentimento. Se não conseguir rodar algo (ferramenta ausente), registre
   como `not-run` com o motivo — **nunca invente um resultado**.
5. **Julgue o resultado**:
   - `verified` — todas as checagens críticas passam e o sintoma original
     não reproduz mais.
   - `partial` — sintoma sumiu mas há regressão não relacionada, ou alguma
     checagem foi inconclusiva.
   - `failed` — sintoma ainda reproduz, ou a suite de regressão quebrou com
     o fix.
   - **Nunca marque `verified` se a reprodução não foi de fato executada**
     — desça pra `partial` e diga isso explicitamente.
6. Escreve `test.md` a partir de `.planning/templates/bug-test-template.md`.
7. Rode
   `.\.planning\scripts\powershell\update-bug-status.ps1 -Slug <slug>` —
   atualiza o painel `## Bugs` em `backlog.md` com o resultado final.
8. Relata: slug, caminho do `test.md`, resultado, recomendação (fechar /
   segurar / reabrir). Se `failed`, recomende rodar a fase Assess de novo
   com a evidência nova capturada em `test.md`.

## Guardrails

- Assess e Test **nunca editam código-fonte** — só leem o repositório e
  escrevem dentro de `sdd/bugs/<slug>/`.
- Fix é a única fase que edita código, e fica dentro dos arquivos listados
  no assessment a menos que evidência nova exija expandir — expansão é
  sempre registrada, nunca silenciosa.
- Nunca sobrescreve um relatório de fase já existente sem confirmar com o
  usuário.
- Vereditos e resultados de verificação nunca são superestimados — uma
  reprodução não executada é `partial`/`not-run`, nunca `verified`.
- Nenhuma fase commita sozinha.

## Handoff

Não se conecta à pipeline `sdd-specify → sdd-plan → sdd-execute →
sdd-converge` — é standalone, como o `sdd-adr`. Um bug que, na fase Assess,
revelar-se grande o bastante pra precisar de decisão de design de verdade
(não só um fix pontual) deveria virar uma feature própria via `sdd-specify`
em vez de seguir por aqui — mencione isso ao usuário se perceber esse
tamanho.
