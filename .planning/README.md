# Sistema SDD (`sdd-assess` + `sdd-adr` + `sdd-bugfix` + `sdd-specify` → `sdd-plan` → `sdd-execute` → `sdd-converge`)

Sistema próprio de Spec-Driven Development, evoluído do skill `plan-feature`
usando ideias estruturais do GitHub spec-kit (constitution como gate, spec
separada de plano separada de tasks, tasks por user story, o extension opt-in
de bug fixing assess→fix→test, e o extension opt-in de validação de ideias
intake→research→define→shape→decide). Corrige seis lacunas que o
`plan-feature` original tinha: dificuldade em planos grandes (resolvida
separando spec/plan/tasks/history), documentação que ficava pra trás do
código (resolvida com atualização estrutural a cada checkpoint), falta de um
backlog (resolvida com `.planning/backlog.md`), falta de um lugar pra
registrar decisões arquiteturais fundamentais do projeto, com alternativas
rejeitadas e consequências assumidas, feitas antes ou entre features
(resolvida com `sdd-adr` + `sdd/adr/`), falta de um fluxo disciplinado pra bugs
relatados fora do contexto de uma feature ativa, com veredito nunca
superestimado (resolvida com `sdd-bugfix` + `sdd/bugs/`), e falta de um
checkpoint de "vale a pena construir isso?" antes de comprometer com uma spec
inteira (resolvida com `sdd-assess` + `sdd/assessments/`).

Este documento explica como usar o sistema, o que cada peça faz, como a
documentação se mantém viva, e como retomar trabalho entre sessões.

## 1. Passo a passo de uso

Não existem comandos de linha de comando pra invocar as skills — as 8 skills
são solicitadas em **linguagem natural** ao agente que carrega
`.agents/skills/` ou `.claude/skills/`. Os scripts PowerShell são usados
internamente nas etapas do fluxo.

-1. **Validar a ideia** (opcional, antes de comprometer com uma spec):
   "avalia essa ideia" / "vale a pena construir X?" → dispara `sdd-assess`.
   Produz `sdd/assessments/<slug>/{explora,problem,decision}.md`, terminando num
   veredito `go`/`needs-clarification`/`kill`. Matar uma ideia com razão
   documentada é sucesso, não falha. Só em `go` o handoff segue pro
   `sdd-specify`.
0. **Decidir arquitetura** (opcional, tipicamente antes da primeira feature):
   "documenta essa decisão de arquitetura" / "vamos decidir e registrar qual
   banco de dados usar" → dispara `sdd-adr`. Produz
   `sdd/adr/ADR-NNN-slug.md`. Não faz parte da pipeline de uma feature
   — pode rodar a qualquer momento, inclusive antes de qualquer `sdd/specs/`
   existir.
1. **Especificar**: "especifica a feature de X" / "cria uma spec pra X" →
   dispara `sdd-specify`. Produz `sdd/specs/<NNN-slug>/spec.md`. Se vier de um
   handoff `go` do `sdd-assess`, usa o resumo já pronto em vez de entrevistar
   do zero.
2. **Planejar**: "planeja essa spec" / "desenha a arquitetura da feature
   <NNN>" → dispara `sdd-plan`. Produz `plan.md` + `tasks.md` (+ artefatos
   condicionais). Lê `sdd/adr/` na exploração, se existir.
3. **Implementar**: "implementa a feature <NNN>" / "continua a feature X" →
   dispara `sdd-execute`. Constrói o código, mantendo a documentação viva.
   Bugs achados durante essa fase são tratados inline (ver seção 6).
4. **Convergir**: "checa se a feature <NNN> está completa" / "converge a
   feature X" → dispara `sdd-converge`. Fecha o ciclo, aponta lacunas ou
   sincroniza o status final (inclusive o `README.md` do projeto, se
   existir).
5. **Corrigir bug relatado** (a qualquer momento, fora de uma feature
   ativa): "avalia esse bug" / "corrige o bug X" / "verifica se o bug foi
   resolvido" → dispara `sdd-bugfix`. Produz
   `sdd/bugs/<slug>/{assessment,fix,test}.md`, um por fase.
6. **Ajuste pequeno e de baixo risco** (a qualquer momento): "ordena essa
   lista" / "limita a quantidade mostrada" / "troca esse texto" → dispara
   `sdd-adhoc`. Nada quebrado (senão é `sdd-bugfix`), valor óbvio (senão é
   `sdd-assess`), escopo pequeno e sem ambiguidade (senão é `sdd-specify`).
   Não cria pasta em `sdd/` — o único rastro é uma linha em
   `.planning/backlog.md` → `## Melhorias Ad-hoc`. Os gates de qualidade
   (lint, type-check, testes, build) continuam valendo.

Recomendado: até você ganhar confiança de que a invocação automática está
acertando o skill certo, prefira pedir de forma explícita por etapa
("avalia essa ideia...", "especifica...", "planeja...", "implementa...",
"converge...", "documenta essa decisão...", "avalia esse bug...") em vez de
frases genéricas tipo só "trabalha nessa feature".

## 2. Fluxo de cada skill

### Visão geral (macro)

```mermaid
flowchart LR
    ASSESS["sdd-assess\n(Explora → Define → Decide)"]
    KILL(["kill / needs-clarification\n(fim, sem próximo passo\nou revisita fase)"])
    ADR["sdd-adr\n(decisões de arquitetura,\nprojeto inteiro)"]
    BACKLOG[(".planning/backlog.md\nIdeias Futuras")]
    SPEC["sdd-specify"]
    PLAN["sdd-plan"]
    EXEC["sdd-execute"]
    CONV["sdd-converge"]
    DONE(["Feature convergida"])
    BUGFIX["sdd-bugfix\n(Assess → Fix → Test)"]
    BUGDONE(["Bug verificado"])

    BACKLOG -->|"ideia a validar"| ASSESS
    ASSESS -->|"veredito: go"| SPEC
    ASSESS -->|"veredito: kill /\nneeds-clarification"| KILL
    ADR -. "consultado por\n(evita relitigar decisão)" .-> PLAN
    BACKLOG -->|"ideia já clara\nvira spec direto"| SPEC
    SPEC -->|spec.md| PLAN
    PLAN -->|"plan.md + tasks.md"| EXEC
    EXEC -->|"código + docs vivas"| CONV
    CONV -->|"achou lacuna:\nanexa tasks novas"| EXEC
    CONV -->|"convergiu limpo"| DONE
    EXEC -. "bug fora de escopo,\nlogado pra depois" .-> BACKLOG
    BACKLOG -->|"entrada de bug\nescolhida pra resolver"| BUGFIX
    BUGFIX -->|"reproduz, ainda falha"| BUGFIX
    BUGFIX -->|verified| BUGDONE
```

`sdd-assess`, `sdd-adr` e `sdd-bugfix` não fazem parte da pipeline linear —
rodam a qualquer momento, independentes de qualquer `sdd/specs/` existir. Os
outros 4 formam o ciclo de vida de uma feature específica, do início ao
fechamento.

### `sdd-assess`

Independente da pipeline de feature — não exige nenhuma `sdd/specs/` existente.
Discovery ("vale a pena construir isso?") antes de Delivery ("como
construímos?"). Uma única invocação continua da fase certa automaticamente.

| Fase | Obrigatória? | O que faz | Escreve em |
|---|---|---|---|
| 0. Resolve | — | `resolve-assessment.ps1` cria/acha `sdd/assessments/<slug>/` e diz qual fase rodar (`define`/`decide`/`complete`) — Explora nunca é auto-detectada, é oferecida à parte | — |
| **Explora** | Não — pule se a ideia já chegou clara | Captura a ideia (texto/URL), evidência a favor **e contra obrigatória** (marca `ASSUMPTION` o que não tem fonte) | `explora.md` |
| **Define** | Sim — estágio mínimo viável | Problem statement, usuários afetados, goals/non-goals, métricas de sucesso, custo de inação | `problem.md` |
| **Decide** | Sim (exige `problem.md`) | Scorecard (`strong`/`adequate`/`weak`/`unknown` por critério — `unknown` precisa ser reconhecido, não varrido pra baixo do tapete), 1-3 abordagens candidatas, veredito | `decision.md` |

**Veredito nunca inflado**: `go` exige problema válido + evidência
`adequate`+ em todos os critérios centrais; senão desce pra
`needs-clarification`. Matar (`kill`) uma ideia com razão documentada é
sucesso, não falha.

**Artefatos**: `sdd/assessments/<slug>/{explora,problem,decision}.md` — sem
numeração sequencial, só o slug, igual `sdd/bugs/`.

**Diagrama interno**:

```mermaid
flowchart TD
    A([Início]) --> B["resolve-assessment.ps1\nresolve slug + fase"]
    B --> C{"NEXT_PHASE?"}
    C -->|"define (Explora\né opcional, oferecida à parte)"| D["Problem statement,\ngoals/non-goals,\nmétricas, custo de inação"]
    D --> E["Escreve problem.md"]
    E --> F(["Relata + próximo passo: Decide"])
    C -->|decide| G["Preenche scorecard\n(unknown deve ser reconhecido)"]
    G --> H["Lista 1-3 abordagens\ncandidatas"]
    H --> I{"Evidência adequate+\nem critérios centrais?"}
    I -->|Não| J["Veredito: needs-clarification"]
    I -->|Sim| K["Veredito: go"]
    I -->|"Problema não\nse sustenta"| L["Veredito: kill"]
    J --> M["Escreve decision.md"]
    K --> M
    L --> M
    M --> N{"Veio de entrada\nno backlog?"}
    N -->|"go ou kill"| O["Remove a entrada\n(decision.md é o registro agora)"]
    N -->|needs-clarification| P["Mantém a entrada\n(ainda é 'futuro')"]
    O --> Q(["Relata veredito + próximo passo"])
    P --> Q
    C -->|complete| R(["Informa veredito já\nregistrado, pergunta se reabre"])
```

### `sdd-adr`

Independente da pipeline de feature — não exige nenhuma `sdd/specs/` existente.

| Etapa | O que faz |
|---|---|
| 1. Confere ADRs existentes | Se a discussão se relaciona a uma ADR já registrada, é emenda, não ADR nova |
| 2. Discussão aberta | Trade-offs técnicos reais — mais livre que a entrevista do `sdd-specify`, não é um checklist fixo |
| 3. Nova ou emenda? | Decide o caminho a seguir |
| 4a. Cria a ADR | `new-adr.ps1` → `sdd/adr/ADR-NNN-slug.md`; Status/Contexto/Decisão/Alternativas Consideradas (com motivo concreto de rejeição)/Consequências/Caminho de Migração |
| 4b. Emenda | **Nunca reescreve** a ADR antiga — adiciona nota inline `**Atualização (ADR-0XX):** ...` no ponto afetado; cria ADR nova só se a emenda for substancial |
| 5. Considera promoção | Pergunta se a decisão deveria virar `Restrição do Projeto` na constitution (a maioria não precisa) |
| 6. Relata | Caminho salvo, se emendou algo, se recomendou promoção |

**Artefatos**: `sdd/adr/ADR-NNN-slug.md`, e possivelmente uma nota
inline numa ADR anterior.

**Diagrama interno**:

```mermaid
flowchart TD
    A([Início]) --> B{"ADR relacionada\njá existe?"}
    B -->|Não| C["Discussão aberta:\ntrade-offs, alternativas,\nrequisitos reais"]
    B -->|Sim, é emenda| G["Nota inline:\n'Atualização (ADR-0XX)'\nna ADR antiga"]
    C --> D["new-adr.ps1\ncria ADR-NNN-slug.md"]
    D --> E["Escreve Contexto / Decisão /\nAlternativas Consideradas /\nConsequências / Migração"]
    E --> F{"Deveria virar regra\nde constitution?"}
    F -->|Sim| H["Sugere ao usuário\n(não edita sozinho)"]
    F -->|Não| I([Relata])
    G --> I
    H --> I
```

### `sdd-specify`

| Etapa | O que faz |
|---|---|
| 1. Gate | `check-prerequisites.ps1 -Stage specify` — só avisa se a constitution não existir, não bloqueia |
| 2. Entrevista leve | 3-5 perguntas: objetivo, ponto de entrada, não-objetivos, critérios de aceite, edge cases |
| 3. Rascunho em memória | Escopo, User Stories P1/P2/P3, FR-###, SC-###, Assumptions |
| 4. Clarify | Varre 8 categorias de ambiguidade, até +5 perguntas com opção Recomendada, só onde há dúvida real |
| 5. Cria a pasta | `new-feature.ps1` → `sdd/specs/<NNN-slug>/` com numeração sequencial |
| 6. Escreve a spec | Sobrescreve `spec.md` com o conteúdo final |
| 7. Atualiza o backlog | `update-feature-status.ps1 -Status Especificada` |
| 8. Relata | Caminho salvo + próximo passo |

**Artefatos**: `sdd/specs/<NNN-slug>/spec.md`, linha nova/atualizada em
`.planning/backlog.md`.

**Diagrama interno**:

```mermaid
flowchart TD
    A([Início]) --> B["Gate: check-prerequisites\n-Stage specify (só avisa)"]
    B --> C["Entrevista leve\n(3-5 perguntas)"]
    C --> D["Rascunho em memória:\nEscopo / Stories / FR-### / SC-###"]
    D --> E["Clarify: 8 categorias\nde ambiguidade,\naté +5 perguntas"]
    E --> F["new-feature.ps1\ncria sdd/specs/NNN-slug/"]
    F --> G["Escreve spec.md final"]
    G --> H["update-feature-status.ps1\nStatus: Especificada"]
    H --> I(["Relata + próximo passo\n(rodar sdd-plan)"])
```

### `sdd-plan`

| Etapa | O que faz |
|---|---|
| 1. Gate | Exige `spec.md` + constitution. Se só a constitution faltar, o próprio skill faz um bootstrap curto (entrevista de 3-5 perguntas) antes de continuar |
| 2. Exploração dirigida | Descobre a estrutura real do repositório, busca só o que a spec exige, lê `sdd/adr/` se existir (nunca relitiga uma decisão já registrada) |
| 3. Síntese de contexto | Resumo compacto antes de escrever qualquer coisa |
| 4. Technical Context + Decisões Invariantes | Stack, storage, testes + axiomas travados desta feature |
| 5. Constitution Check (pré-design) | Cada princípio avaliado contra o plano emergente — viola sem justificativa, pára e pergunta |
| 6. `research.md` (condicional) | Só se houver incerteza técnica real |
| 7. `data-model.md` / `contracts/` / `quickstart.md` (condicionais) | Conforme a feature envolver dados/API/verificação manual |
| 8. Constitution Check (pós-design) | Reavalia contra o design final |
| 9. Escreve `plan.md` | Summary, Technical Context, Decisões Invariantes, Constitution Check, Project Structure real, Estratégia de Testes + 5 seções vazias (só o `sdd-execute` preenche) |
| 10. Gera `tasks.md` | Fases por user story, template de 5 blocos, Checklist de Release na fase final |
| 11. Analyze | Cruza spec/plan/tasks/constitution — acha duplicação/ambiguidade/lacunas, relata **só no chat**, nunca em arquivo |
| 12. Atualiza o backlog | `Status: Planejada` |
| 13. Relata | O que foi escrito + resultado do Analyze |

**Artefatos**: `plan.md`, `tasks.md`, e condicionalmente `research.md`,
`data-model.md`, `contracts/*.md`, `quickstart.md`.

**Diagrama interno**:

```mermaid
flowchart TD
    A([Início]) --> B["Gate: check-prerequisites\n-Stage plan"]
    B --> C{"Constitution\nexiste?"}
    C -->|Não| D["Bootstrap: entrevista curta\ncria constitution.md"]
    D --> B
    C -->|Sim| E["Exploração dirigida\n+ lê sdd/adr/"]
    E --> F["Technical Context +\nDecisões Invariantes"]
    F --> G["Constitution Check\n(pré-design)"]
    G -->|"Viola sem\njustificativa"| H(["Pára e pergunta"])
    G -->|OK| I["research.md / data-model.md /\ncontracts/ / quickstart.md\n(condicionais)"]
    I --> J["Constitution Check\n(pós-design)"]
    J --> K["Escreve plan.md"]
    K --> L["Gera tasks.md\n(5 blocos por fase)"]
    L --> M["Analyze\n(só no chat, não grava)"]
    M --> N["update-feature-status.ps1\nStatus: Planejada"]
    N --> O(["Relata"])
```

### `sdd-execute`

| Etapa | O que faz |
|---|---|
| 1. Gate | Exige `spec.md` + `plan.md` + `tasks.md` |
| 2. Carrega contexto | Lê tudo — tasks, plan, spec, constitution, docs condicionais |
| 3. Primeira execução | Marca `Status: Em Execução` no backlog |
| 4. Próxima task | Respeita ordem: Setup → Foundational → User Stories em prioridade → Polish |
| 5. Implementa | Roda build/teste real por task, marca `[x]` imediatamente |
| 6. Bugs | Cerimônia proporcional ao tamanho (ver seção 4 abaixo) |
| 7. Checkpoint | Atualiza `Registro da Fase`, `Estado Atual`, `Arquivos Principais`, `Execution Notes` + `PRÓXIMO`, `Riscos e Decisões`, `Cuidados para Retomada` — obrigatório, não condicional |
| 8. Arquivamento | Se `Execution Notes` passar de ~40 linhas, move o excedente pra `history.md` |
| 9. Atualiza progresso | `update-feature-status.ps1` recalcula `N/M tasks` no backlog |
| 10. Reporta | O que foi feito, testes rodados, próximo passo |
| 11. Pausa ou segue | **Padrão**: pára ao fim de cada fase e pergunta se continua. **Contínuo**: só se você pedir explicitamente ("sem parar", "modo contínuo") |
| 12. Sugere commits | Nunca commita sozinho |
| 13. Conflito de critério de aceite | Pára e pergunta, não adivinha |
| 14. Última task | `Status: Implementada` |

**Artefatos**: código-fonte real, `tasks.md` atualizado, `plan.md`
atualizado, `history.md` (condicional), `backlog.md` atualizado.

**Diagrama interno**:

```mermaid
flowchart TD
    A([Início]) --> B["Gate: check-prerequisites\n-Stage execute"]
    B --> C["Carrega contexto:\ntasks/plan/spec/constitution"]
    C --> D{"Primeira\nexecução?"}
    D -->|Sim| E["Status: Em Execução"]
    D -->|Não| F["Identifica próxima task"]
    E --> F
    F --> G["Implementa + roda testes"]
    G --> H{"Bug\nencontrado?"}
    H -->|"Bloqueia a task"| I["Corrige inline"]
    H -->|"Fora do escopo"| J(["Pára: corrigir agora\nou logar em backlog?"])
    H -->|Não| K["Marca task concluída"]
    I --> K
    J --> K
    K --> L{"Fase\ncompleta?"}
    L -->|Não| F
    L -->|Sim| M["Checkpoint: Registro da Fase,\nEstado Atual, Execution Notes\n+ PRÓXIMO, Riscos, Arquivos"]
    M --> N["Arquivamento\n(se necessário)"]
    N --> O["update-feature-status.ps1"]
    O --> P["Reporta progresso"]
    P --> Q{"Última\nfase?"}
    Q -->|"Não — modo pausado"| R(["Pára, pergunta\nse continua"])
    R -->|Confirma| F
    Q -->|"Não — modo contínuo"| F
    Q -->|Sim| S["Status: Implementada"]
```

### `sdd-converge`

| Etapa | O que faz |
|---|---|
| 1. Gate | Exige `spec.md` + `plan.md` + `tasks.md`; avisa se 0 tasks marcadas |
| 2-3. Mapeia intenção → código | Compara o que foi declarado com o que existe de verdade, sem inferir além disso |
| 4-5. Classifica e prioriza | `missing`/`partial`/`contradicts`/`unrequested`, severidade CRITICAL/HIGH/MEDIUM/LOW |
| 6. Apresenta achados | Tabela no chat, antes de escrever qualquer coisa |
| 7a. Se achar lacuna | Anexa `## Phase N: Convergence` no final de `tasks.md` (nunca reescreve o que já existe) |
| 7b. Se convergir limpo | `tasks.md` fica intocado; atualiza `Status` em `spec.md`; anexa `Resultado Final` em `plan.md`; marca riscos sem violação como `Resolvido:`; **se existir `README.md` do projeto e algo relevante mudou, edita cirurgicamente só a parte afetada** |

**Regra de ouro**: nunca edita código, nunca reescreve conteúdo existente —
só anexa ou atualiza campos de status pontuais. O `README.md` do projeto é a
única exceção a "nunca edita corpo de texto", e mesmo assim só quando há
mudança real visível pra quem lê (cerimônia proporcional) — nunca cria um
README que não existia.

**Diagrama interno**:

```mermaid
flowchart TD
    A([Início]) --> B["Gate: check-prerequisites\n-Stage converge"]
    B --> C["Carrega spec/plan/tasks/\nconstitution"]
    C --> D["Mapeia intenção → código real"]
    D --> E["Classifica: missing / partial /\ncontradicts / unrequested"]
    E --> F(["Apresenta Convergence\nFindings no chat"])
    F --> G{"Achou\nlacuna?"}
    G -->|Sim| H["Anexa 'Phase N: Convergence'\nem tasks.md"]
    H --> I["Status: Convergência Pendente"]
    I --> J(["Recomenda rodar\nsdd-execute de novo"])
    G -->|Não| K["tasks.md fica intocado"]
    K --> L["Status em spec.md → Convergida"]
    L --> M["Anexa 'Resultado Final'\nem plan.md"]
    M --> N["Riscos sem violação\n→ 'Resolvido:'"]
    N --> P{"README.md existe\ne mudou algo\nrelevante?"}
    P -->|Sim| Q["Edita só a parte\nafetada do README"]
    P -->|Não| O(["Relata: Convergido"])
    Q --> O
```

### `sdd-bugfix`

Independente da pipeline de feature — não exige nenhuma `sdd/specs/` existente.
Uma única invocação continua da fase certa automaticamente, com base no que
já existe em `sdd/bugs/<slug>/`.

| Fase | Pode editar código? | O que faz | Escreve em | Veredito |
|---|---|---|---|---|
| 0. Resolve | — | `resolve-bug.ps1` cria/acha `sdd/bugs/<slug>/` e diz qual fase rodar (`assess`/`fix`/`test`/`complete`) | — | — |
| **Assess** | Não | Ingere o report (texto/URL), resume sintoma, localiza código suspeito, avalia mérito/severidade, propõe remediação | `assessment.md` | `valid` / `likely valid, needs reproduction` / `invalid` |
| **Fix** | **Sim — só esta fase** | Confirma o plano, aplica a remediação (fica dentro dos arquivos do assessment, desvios registrados), adiciona testes, roda checagens locais | `fix.md` | `applied` / `partial` / `not-applied` |
| **Test** | Não | Replaneja e roda a validação (reprodução + testes + regressão + lint), julga o resultado sem superestimar | `test.md` | `verified` / `partial` / `failed` |

**Artefatos**: `sdd/bugs/<slug>/{assessment,fix,test}.md`, um por fase
— sem numeração sequencial, só o slug.

**Diagrama interno**:

```mermaid
flowchart TD
    A([Início]) --> B["resolve-bug.ps1\nresolve slug + fase"]
    B --> C{"NEXT_PHASE?"}
    C -->|assess| D["Ingere report,\nlocaliza código suspeito"]
    D --> E["Avalia mérito/severidade,\npropõe remediação"]
    E --> F["Escreve assessment.md"]
    F --> F2["update-bug-status.ps1\n(painel ## Bugs)"]
    F2 --> G(["Relata veredito +\npróximo passo: Fix"])
    C -->|fix| H{"Veredito era\ninvalid?"}
    H -->|Sim| I(["Pára — nada a corrigir"])
    H -->|Não| J["Confirma plano,\naplica remediação"]
    J --> K{"Ficou dentro do\nescopo do assessment?"}
    K -->|Não| L["Registra em\n'Deviations from Assessment'"]
    K -->|Sim| M["Adiciona testes,\nroda checagens locais"]
    L --> M
    M --> N["Escreve fix.md"]
    N --> N2["update-bug-status.ps1\n(painel ## Bugs)"]
    N2 --> O(["Relata status +\npróximo passo: Test"])
    C -->|test| P["Replaneja validação:\nreprodução + testes + regressão"]
    P --> Q["Executa checagens\n(nunca inventa resultado)"]
    Q --> R{"Reprodução foi\nde fato executada?"}
    R -->|Não| S["verified NÃO permitido\n→ partial/not-run"]
    R -->|Sim| T["Julga: verified /\npartial / failed"]
    S --> U["Escreve test.md"]
    T --> U
    U --> U2["update-bug-status.ps1\n(painel ## Bugs)"]
    U2 --> V(["Relata resultado +\nrecomendação"])
    C -->|complete| W(["Informa status final,\npergunta se reabre"])
```

## 3. Scripts auxiliares (`.planning/scripts/powershell/`)

| Script | Pra que serve |
|---|---|
| `common.ps1` | Funções compartilhadas: acha a raiz do repo (marcador `.planning/`), resolve caminhos de feature, gera slug, lê template |
| `new-feature.ps1` | Cria `sdd/specs/<NNN-slug>/` com numeração sequencial + `spec.md` semeado |
| `new-adr.ps1` | Cria `sdd/adr/ADR-NNN-slug.md` com numeração sequencial + conteúdo semeado do template |
| `check-prerequisites.ps1` | Gate por estágio (specify/plan/execute/converge) — bloqueia com mensagem específica de qual arquivo falta e qual skill rodar |
| `update-feature-status.ps1` | Recalcula progresso, atualiza `backlog.md` e a linha `**Status**:` de `spec.md`; autocria `backlog.md` se não existir |
| `resolve-bug.ps1` | Cria/acha `sdd/bugs/<slug>/` (sem numeração, só slug) e reporta qual fase (assess/fix/test/complete) rodar a seguir, baseado em quais relatórios já existem |
| `update-bug-status.ps1` | Recalcula fase/veredito/próximo passo a partir de `sdd/bugs/<slug>/*.md` e atualiza o painel `## Bugs` em `backlog.md`; autocria `backlog.md` se não existir |
| `check-contract-tests.ps1 -Slug <slug> [-Write [-Paths <arquivos>]] [-Json]` | Trava caminhos + SHA256 dos contratos; conta e filtra testes apenas nos arquivos JS/TS reconhecidos, registra contagem desconhecida nos demais e confere integridade sem `-Write` |
| `resolve-assessment.ps1` | Cria/acha `sdd/assessments/<slug>/` (sem numeração, só slug) e reporta qual fase (define/decide/complete) rodar a seguir — Explora é opcional e nunca entra nessa resolução automática |

Os scripts são agnósticos ao tipo de aplicativo e à stack de execução; dependem apenas da convenção SDD (.planning, sdd/ e Markdown). O verificador de contratos faz análise sintática somente quando reconhece JS/TS; nos demais runtimes, a contagem deve ser registrada pelo plano.

## 4. Como a documentação se mantém atualizada

Esse é o mecanismo central que resolve "a doc fica pra trás do código":

- **`## Estado Atual`** (em `plan.md`) — **sobrescrita** a cada checkpoint.
  Reflete o estado real agora, não o histórico.
- **`## Execution Notes`** (em `plan.md`) — tabela **append-only**
  (Data\|Fase\|Resumo\|Pendência), com uma linha `PRÓXIMO:` **sobrescrita**
  logo abaixo apontando a única próxima ação concreta.
- **`Registro da Fase`** (em `tasks.md`, um por fase) — escrito quando
  aquela fase fecha, fica embutido perto do checklist dela (não centralizado
  num log só).
- **`## Riscos e Decisões`** (em `plan.md`) — tabela com IDs estáveis
  (`R-001`...), nunca deletados; item resolvido ganha `Resolvido:` na
  célula em vez de sumir.
- **`## Arquivos Principais`** (em `plan.md`) — **sobrescrita**, foco da
  etapa atual.
- **`Checklist de Release`** (em `tasks.md`) — marcado conforme cada fase
  fecha.
- **Arquivamento automático** — se `Execution Notes` crescer demais (~40
  linhas), o excedente vai pra `sdd/specs/<slug>/history.md`, deixando só um
  resumo consolidado no `plan.md` ativo. Isso existe porque um plano real
  de outro projeto (não gerido por este sistema) chegou a 2902 linhas antes
  de alguém separar o histórico manualmente — aqui isso é embutido no fluxo.
- **`sdd-converge`** fecha o ciclo: quando tudo bate, sincroniza
  `spec.md`/`plan.md`/`backlog.md` com a realidade final, não só aponta o
  que falta.

Tudo isso é **obrigatório**, não uma sugestão de prosa — faz parte do fluxo
numerado de cada skill, não depende do agente "lembrar".

## 5. Retomada entre sessões

Os skills não têm memória entre sessões — cada invocação relê os arquivos do
zero. É por isso que a documentação viva importa: ela É a memória.

Pra retomar uma feature numa sessão nova:

1. Olhe `.planning/backlog.md` → `## Features` pra ver o status geral de
   tudo (`Especificada`/`Planejada`/`Em Execução`/`Implementada`/
   `Convergida`/`Convergência Pendente`) e o progresso (`N/M tasks`).
2. Abra `sdd/specs/<slug>/plan.md` → `## Estado Atual` (visão geral) e a linha
   `PRÓXIMO:` (ação concreta seguinte) — é o resumo mais rápido de onde
   parou.
3. Se precisar de mais detalhe, `## Execution Notes` (o que aconteceu
   recentemente) e `## Cuidados para Retomada` (armadilhas já descobertas,
   pra não repetir erro).
4. Peça ao skill certo pra continuar ("continua a implementação da feature
   X") — ele mesmo roda o gate, relê tudo e identifica a próxima task
   incompleta em `tasks.md`.

Você não precisa reconstruir contexto manualmente — só apontar a feature e
deixar o skill reler o que já está documentado.

## 6. Outros aspectos importantes

### Modo de execução do `sdd-execute`

Por padrão pausa ao fim de cada fase pra confirmação. Peça "sem parar" /
"modo contínuo" pra desativar. Independente do modo, 3 gatilhos sempre param
de verdade: bug fora de escopo, conflito de critério de aceite, ou fim das
tasks.

### Tratamento de bugs (cerimônia proporcional)

- Bloqueia a task atual → corrige inline, sem cerimônia.
- Dentro do escopo, não previsto → vira task ad-hoc em `tasks.md`.
- Fora do escopo → nunca corrige calado; pergunta corrigir agora ou logar em
  `backlog.md` → `## Ideias Futuras` com prefixo `[Bug]`.
- Bug relatado fora de qualquer feature ativa (independente do
  `sdd-execute`) → `sdd-bugfix`, com disciplina de teste de regressão
  obrigatório e veredito nunca superestimado (`verified` só se a reprodução
  foi de fato executada).

### Constitution como gate

`.planning/memory/constitution.md` guarda os princípios não-negociáveis do
projeto inteiro (não de uma feature). O `sdd-plan` checa contra ela duas
vezes por feature (pré e pós-design). Se não existir ainda, o próprio
`sdd-plan` bootstrapa com uma entrevista curta na primeira vez que alguém
tenta planejar algo — não precisa existir de antemão.

### Backlog com três propósitos

`.planning/backlog.md` combina: `## Ideias Futuras` (features/bugs ainda sem
spec), `## Features` (painel de status de tudo que já tem
`sdd/specs/<slug>/`) e `## Bugs` (painel de status de tudo que já tem
`sdd/bugs/<slug>/`, mantido por `update-bug-status.ps1` ao final de cada
fase do `sdd-bugfix`). Mantido automaticamente, nunca editado à mão pras
colunas de status.

### ADRs vs constitution vs Decisões Invariantes

Três lugares diferentes pra decisão técnica, cada um com um papel distinto —
não são intercambiáveis:

| | Escopo | Natureza | Quem mantém |
|---|---|---|---|
| `constitution.md` | Projeto inteiro | Regra `DEVE`, gate formal, terso | `sdd-plan` (bootstrap) |
| ADR (`sdd/adr/`) | Projeto inteiro | Decisão + raciocínio completo + alternativas rejeitadas, permanente, emendável | `sdd-adr` |
| `plan.md` → Decisões Invariantes | Uma feature | Local, descartável quando a feature converge | `sdd-plan` |

Uma ADR pode eventualmente "virar" uma regra de constitution (quando a
decisão deve bloquear qualquer feature futura que a viole), mas a maioria
fica só documentada como ADR, sem promoção — nem toda decisão de arquitetura
precisa ser um gate obrigatório.

### Por que ter ADRs

- **Evita relitigar decisões já tomadas.** Sem ADR, cada feature nova que
  toca uma área técnica corre o risco de reabrir uma discussão já resolvida
  — ou pior, o agente nem sabe que ela já foi resolvida e propõe algo
  inconsistente. É por isso que o `sdd-plan` lê `sdd/adr/` antes de
  decidir Technical Context.
- **Preserva o porquê, não só o o quê.** Código mostra o que foi
  implementado; a constitution mostra a regra. Nenhum dos dois guarda o
  raciocínio nem as alternativas descartadas.
- **Evita inconsistência silenciosa entre features.** Sem um registro
  central, a feature A pode assumir uma coisa e a feature B assumir o
  oposto, sem ninguém perceber.
- **Documenta trade-offs conscientemente aceitos.** A seção de Consequências
  Negativas registra limitações aceitas de propósito — evita que uma
  feature futura "descubra" isso como se fosse bug.
- **Caminho de migração pronto.** Quando a decisão precisar mudar, já existe
  "sob quais condições reconsiderar e como migrar".
- **Retomada/onboarding rápido.** O jeito mais rápido de entender decisões
  estruturais sem vasculhar histórico de conversa ou commit.

**Quando vale menos**: o ganho é proporcional ao tamanho da decisão — em
projetos pequenos/MVP com poucas decisões de arquitetura genuinamente
grandes, você provavelmente vai gerar poucas ADRs, e está tudo bem. Não
force uma ADR pra escolha trivial — mesma lógica de "cerimônia proporcional"
que já vale pra bugs no `sdd-execute`.

### O que este sistema deliberadamente não faz

- Não tem um mecanismo de checklist de qualidade de requisitos (rejeitado
  conscientemente).
- Não reimplementa o motor de override/preset/extension de templates do
  speckit — templates são arquivos literais, simples.
- Os scripts e templates deste fluxo vivem em `.planning/`; os artefatos de
  trabalho gerados ficam em `sdd/`.
- Não promove as skills para um diretório global do agente automaticamente —
  isso é uma decisão separada, depois de validar o fluxo neste projeto.

## 7. Perguntas Frequentes

**Preciso digitar `/sdd-specify` ou algo assim?**
Não. Descreva o que quer em português normal ("especifica uma melhoria na
gravação") para o agente que carrega as skills. Você também pode nomear
`sdd-specify` explicitamente.

**O `sdd-specify` só entende a ideia e esclarece, ou faz mais que isso?**
Faz mais — a entrevista e o clarify são só as etapas 2-4 de 8. No final ele
**escreve um `spec.md` de verdade**, estruturado (Escopo, User Stories,
Functional Requirements, Success Criteria), e atualiza o backlog. Não fica
só na conversa.

**Como chamo o `sdd-execute`? Que parâmetro escrevo?**
Nenhum parâmetro de linha de comando — só diga qual feature em linguagem
natural ("implementa a feature 002" ou "implementa a melhoria de exportação").
Internamente isso vira um `-Slug` pros scripts, resolvido por nome completo
ou prefixo.

**Se eu pedir pra executar uma feature, ele vai do início ao fim sem
parar?**
Por padrão, não — pausa ao fim de cada fase e pergunta se continua (peça
"modo contínuo" se quiser sem pausas). Independente disso, ele sempre pára
de verdade se achar um bug fora de escopo, um conflito de critério de
aceite, ou quando as tasks acabarem.

**O que é a `constitution.md` e o que devo colocar nela?**
São os princípios não-negociáveis do projeto inteiro, checados como gate
pelo `sdd-plan`. Cada princípio deve ser verificável (testável contra um
plano real), não aspiracional — o teste é "o sdd-plan conseguiria dizer
PASS ou FLAG disso?". Ver `.planning/templates/constitution-template.md`
pros comentários-guia.

**O que são `quickstart.md` e os arquivos em `contracts/`?**
`quickstart.md` é o roteiro de verificação manual (condicional, só quando a
feature precisa de confirmação além dos testes automatizados). `contracts/`
documenta o shape de request/response de uma API que a feature expõe ou
muda (também condicional, só se houver superfície de API).

**Como inicio isso num repositório novo?**
Copie `.agents/skills/sdd-*/` (as 8 skills) e `.planning/scripts/` +
`.planning/templates/`. Se o outro ambiente também usa `.claude/skills/`,
sincronize as cópias das skills. Não copie `constitution.md`,
`backlog.md` nem a pasta `sdd/` (específicos deste projeto) — eles se
recriam sozinhos ou vazios: `backlog.md` autocria na primeira chamada, a
`constitution.md` é bootstrapada pelo `sdd-plan` na primeira vez que alguém
planejar algo, e `sdd/specs/`, `sdd/adr/`, `sdd/bugs/`, `sdd/assessments/`
só existem depois da primeira vez que você rodar o skill correspondente.

**Por que `sdd/specs/`, `sdd/adr/`, `sdd/bugs/` e `sdd/assessments/` ficam
na raiz do repo em vez de dentro de `.planning/`?**
Porque são **produto de trabalho** (conteúdo gerado, um por feature/decisão/
bug/ideia, pra navegar e revisar), diferente de `.planning/` que é só
**maquinário compartilhado** (templates, scripts, constitution, backlog —
painel de controle, não conteúdo em si). Misturar as duas coisas no mesmo
dot-folder ficaria confuso e menos descobrível. As 4 subpastas ficam
agrupadas dentro de uma única `sdd/` visível (em vez de soltas direto no
root, como era antes) porque o root do projeto já acumula muitas outras
pastas não relacionadas ao sistema SDD — uma pasta só, com nome descritivo,
é mais fácil de reconhecer e não some no meio do resto.

**Qual a diferença entre `sdd-assess`, `sdd-adr` e `sdd-specify`?**
`sdd-assess` responde "vale a pena construir isso?" — roda **antes** de
qualquer compromisso, pode terminar em `kill`. `sdd-adr` documenta **como**
resolver uma decisão de arquitetura fundamental já assumida como necessária
(qual banco, qual stack). `sdd-specify` já assume que a feature **vai** ser
construída e define o **quê** dela. Numa ideia grande e incerta, o caminho
completo seria `sdd-assess` (decide se vale a pena) → `sdd-specify` (o quê)
→ `sdd-plan`, que pode incluir seu próprio `sdd-adr` se surgir uma decisão
de arquitetura no meio.

**Qual a diferença entre o tratamento de bug do `sdd-execute` e o
`sdd-bugfix`?**
`sdd-execute` trata bugs achados **durante** a implementação de uma feature
— já tem o contexto carregado (plan/tasks/spec), então corrige inline ou
vira task ad-hoc sem sair do fluxo. `sdd-bugfix` é pra bugs relatados
**independentemente** de qualquer feature ativa — um usuário reportou algo,
ou você pegou uma entrada `[Bug]` do backlog pra resolver agora. Ele roda em
3 fases (Assess → Fix → Test), cada uma com um contrato de leitura/escrita
diferente, e nunca marca um fix como `verified` se a reprodução não foi de
fato executada.

**Preciso rodar as 3 fases do `sdd-bugfix` de uma vez?**
Não — cada fase é sua própria invocação, e o skill descobre automaticamente
qual rodar a seguir (via `resolve-bug.ps1`, olhando quais arquivos já
existem em `sdd/bugs/<slug>/`). Dá pra assessar vários bugs sem se
comprometer a corrigir na hora, ou re-rodar só o Test depois de mexer em
algo manualmente.

**Quando devo usar `sdd-adr` em vez de simplesmente deixar o `sdd-plan`
decidir a stack de uma feature?**
`sdd-adr` é pra decisões que **outlivem** a feature atual — ex: qual banco
de dados, qual framework, qual plataforma de deploy — coisas que outras
features vão herdar e não devem redecidir cada uma por conta própria.
Se a decisão só faz sentido dentro do escopo desta feature específica (ex:
"essa tela usa paginação client-side"), isso é uma Decisão Invariante local
em `plan.md`, não uma ADR.

**Uma ADR errada foi criada — como corrijo?**
Não edite/reescreva o arquivo original diretamente por fora do fluxo — peça
`sdd-adr` de novo, descrevendo o que mudou; ele reconhece que é uma emenda
e adiciona uma nota `**Atualização (ADR-0XX):**` inline na ADR antiga (ou
cria uma nova que a supera, se for uma mudança substancial). Isso preserva
o histórico de por que a decisão original foi tomada.

**Posso editar `spec.md`/`plan.md`/`tasks.md` manualmente entre uma etapa e
outra?**
Sim, são arquivos Markdown normais. Só tome cuidado com o que os scripts
esperam achar por regex (a linha `**Status**:` em `spec.md`, o formato da
tabela de `backlog.md`) — não quebre esses formatos ao editar à mão.

**O que acontece se eu fechar a sessão no meio de uma fase do
`sdd-execute`?**
Nada se perde: cada task marca `[x]` imediatamente (não em lote), e o
checkpoint da fase só fecha quando ela termina de verdade. Na pior hipótese
você perde o trabalho de uma fase parcialmente feita, não o progresso já
marcado. Ao retomar, o skill relê `tasks.md` e continua do último `[x]`.

**Posso rodar `sdd-plan` de novo numa spec que já tem `plan.md`?**
O comportamento não foi projetado pra isso especificamente — o skill não
tem uma instrução de "replanejar". Se `plan.md`/`tasks.md` já existem e
você quer mudanças, é mais seguro editar diretamente ou pedir uma alteração
pontual, explicando que já existe conteúdo a preservar.

**Posso pular etapas, tipo pedir `sdd-execute` sem ter rodado `sdd-plan`?**
Não — o gate de pré-requisito bloqueia (`check-prerequisites.ps1 -Stage
execute` exige `plan.md` e `tasks.md`) e te diz explicitamente pra rodar
`sdd-plan` primeiro.

**O `sdd-converge` pode rodar mais de uma vez na mesma feature?**
Sim, e é o uso normal quando ele acha lacuna: ele anexa uma nova fase de
tasks, você roda `sdd-execute` pra cobri-las, e roda `sdd-converge` de novo
— quantas vezes precisar até convergir limpo.

**O sistema atualiza o `README.md` da aplicação sozinho?**
Só se ele já existir, e só o `sdd-converge` faz isso — quando a feature
converge limpa, ele confere se algo que mudou deveria estar refletido no
README (lista de features, instruções de setup, portas, comandos) e edita
cirurgicamente só a parte afetada, nunca uma reescrita geral. Se o README
não existir, nenhum skill cria um — isso é decisão sua. Se nada relevante
mudou, o README fica intocado (mesma lógica de "cerimônia proporcional" que
já vale pra bugs no `sdd-execute`).

**Este fluxo depende de uma instalação anterior do spec-kit?**
Não. Ele usa as skills em `.agents/skills/` ou `.claude/skills/`, os scripts e
templates em `.planning/` e os artefatos gerados em `sdd/`.

**Os scripts funcionam fora do Windows?**
São PowerShell (`.ps1`), então rodam em qualquer SO com PowerShell 7+
instalado (`pwsh`), não só Windows — mas não foram testados em Linux/Mac
ainda.

**Como faço uma emenda na `constitution.md` depois que ela já existe?**
Hoje isso é manual (nenhum skill edita a constitution depois de criada) —
edite o arquivo direto, atualize `**Versão**`/`**Última Emenda**` seguindo
as regras de versionamento semântico que já estão na seção Governança.

**Quando devo promover as skills para um diretório global do agente?**
Só depois de validar o fluxo neste projeto. Hoje elas vivem em
`.agents/skills/` e `.claude/skills/` deste repositório; mantenha as duas
cópias sincronizadas enquanto ambas forem usadas.
