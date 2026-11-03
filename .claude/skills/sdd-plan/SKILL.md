---
name: sdd-plan
description: Transforma uma spec existente em plan.md e tasks.md, com checagem contra a constitution do projeto. Use para planejar uma feature, desenhar sua arquitetura ou dividir a spec em tasks. Exige spec.md em sdd/specs/; para criar a spec use sdd-specify, e para implementar use sdd-execute.
---

# sdd-plan

Segundo estágio do sistema SDD. Lê uma spec já escrita, explora o código real
**deste** repositório, desenha a abordagem técnica sob o gate da constitution,
e produz `plan.md` + `tasks.md`. Termina com uma checagem de consistência
somente-leitura (Analyze).

Este skill é agnóstico de projeto — não assuma nenhuma linguagem, framework ou
estrutura de pastas específica. Tudo sobre a estrutura real (backend/frontend
separados? monorepo? projeto único?) vem da exploração do passo 2, nunca de
um exemplo memorizado de outro projeto.

## Fluxo

### 1. Gate de pré-requisito

```powershell
.\.planning\scripts\powershell\check-prerequisites.ps1 -Stage plan -Slug <NNN-slug> -Json
```

Isso **bloqueia** se `spec.md` ou `.planning/memory/constitution.md` não
existirem, com instrução explícita do que rodar antes. Guarde o `FEATURE_DIR`
retornado — os passos seguintes usam esse caminho.

**Se `spec.md` não existir**: pare e diga pra rodar `sdd-specify` primeiro —
não tente contornar.

**Se só a constitution não existir** (mensagem específica "constitution não
existe. Crie a constitution antes de planejar"): este projeto ainda não tem
`.planning/memory/constitution.md`. Não é bloqueio definitivo — faça o
bootstrap agora, antes de continuar:

1. Verifique se existe uma constitution equivalente já escrita em outro lugar
   deste repositório (ex: um `.specify/memory/constitution.md` de uma
   instalação do speckit, um `CONTRIBUTING.md`, um documento de princípios de
   engenharia). Se existir algo aproveitável, pergunte ao usuário se quer
   portar esse conteúdo (traduzindo pra português se for o caso) em vez de
   partir do zero.
2. Se não houver nada pra portar, faça uma entrevista pra levantar os
   princípios. **Sem teto artificial de perguntas** — pode passar de 10 se o
   projeto justificar. Quando as alternativas puderem ser enumeradas, use a
   ferramenta de perguntas estruturadas disponível no ambiente ou apresente
   as opções no chat, **da mais recomendada para a menos recomendada**, com
   a primeira explicitamente marcada como recomendada. Para perguntas abertas
   (ex: "quais princípios?"), colete em texto livre. Cubra pelo menos:
   - Que tipo de projeto é este e qual a stack principal?
   - Quais são os 3-5 princípios não-negociáveis pra como o código deste
     projeto deve ser construído (ex: segurança, fronteiras de
     responsabilidade entre camadas, disciplina de escopo, qualidade
     verificável — dê exemplos assim pra ajudar o usuário a responder rápido)?
   - Alguma restrição forte de projeto (stack travada, alvo de deploy,
     compliance, single-user vs multi-tenant)?
   - O que precisa ser verdade antes de uma mudança ser considerada "pronta"
     (revisão, checagens obrigatórias)?
3. Escreva `.planning/memory/constitution.md` a partir de
   `.planning/templates/constitution-template.md`, preenchendo Princípios
   Fundamentais (3-5, statements DEVE) a partir das respostas, `##
   Restrições do Projeto` e `## Fluxo de Desenvolvimento` (ou nomes de seção
   equivalentes que façam sentido pro projeto). A seção `## Governança` pode
   reusar o texto padrão de versionamento semântico (MAJOR/MINOR/PATCH) sem
   precisar perguntar — isso não varia por projeto.
4. Rode `check-prerequisites.ps1 -Stage plan` de novo pra confirmar que
   passa, e só então continue pro passo 2.

Isso mantém o bootstrap dentro do `sdd-plan` (sem virar um 5º skill) — a
constitution só é criada quando alguém efetivamente tenta planejar a primeira
feature de um projeto novo, nunca antes disso ser necessário.

### 2. Exploração dirigida

Leia `spec.md` primeiro. Depois descubra a estrutura real deste repositório —
manifestos de projeto/dependências, config de framework, convenções de pastas
já em uso — e busque, guiado pelos termos da spec, os componentes/serviços/
rotas/entidades existentes que a feature vai tocar ou de que vai depender.
Prefira buscas focadas de arquivos e texto a um dump do diretório inteiro. Leia testes
existentes da mesma área, se houver, pra entender o padrão de teste do
projeto.

Se `sdd/adr/` existir, liste os títulos das ADRs lá dentro e leia por
inteiro qualquer uma cujo tema se relacione com esta feature (stack, banco de
dados, framework tocados). São decisões de arquitetura já tomadas e
justificadas — **não as relitigue silenciosamente**; a Technical Context e as
Decisões Invariantes desta feature devem ser consistentes com elas. Se a
feature exige contrariar uma ADR existente, trate como uma violação a
justificar no Constitution Check (passo 5) e sugira ao usuário rodar
`sdd-adr` pra emendar a decisão formalmente, em vez de só ignorá-la aqui.

### 3. Síntese de contexto

Antes de escrever qualquer arquivo, monte um resumo compacto pra você mesmo:
arquitetura real deste repositório, padrões existentes a seguir, arquivos que
importam e por quê, constraints/riscos já conhecidos. Isso vira a base do
Technical Context e das Decisões Invariantes.

### 4. Technical Context + Decisões Invariantes

Preencha, no `plan.md` (a partir de `.planning/templates/plan-template.md`):

- Technical Context: linguagem/versão, dependências, storage, testes,
  plataforma, performance, constraints, escala — tudo baseado no que foi
  encontrado na exploração do passo 2. Marque `NEEDS CLARIFICATION` onde não
  houver informação suficiente em vez de inventar.
- `## Decisões Invariantes`: axiomas/regras travadas desta feature específica
  (ex: "remoção é síncrona, sem soft-delete nesta fase"). Diferente da
  constitution (projeto inteiro) e diferente de Riscos e Decisões (log
  evolutivo) — aqui são decisões que não devem ser revisitadas sem reabrir o
  design.

### 5. Constitution Check — gate pré-design

Leia `.planning/memory/constitution.md`. Para cada princípio que ela definir,
avalie se o plano emergente até aqui é compatível. Preencha a tabela `##
Constitution Check` (coluna Pré-Design) com uma linha por princípio real da
constitution deste projeto — a tabela do template é só um exemplo de forma,
não uma lista fixa de princípios. Se houver violação:

- **Justificável** (ex: complexidade genuinamente necessária): registre em
  `## Complexity Tracking` (Violação | Por que é necessária | Alternativa
  mais simples rejeitada porque).
- **Não justificável**: **pare e pergunte ao usuário** — não prossiga
  silenciosamente. Isso é um gate real, não um carimbo. Prefira
   a ferramenta de perguntas estruturadas disponível ou apresente as
   alternativas no chat (ex: redesenhar, aceitar como complexidade
   justificada, abrir `sdd-adr`) da mais recomendada para a menos recomendada.

Riscos ou decisões técnicas identificados aqui já entram em `## Riscos e
Decisões` com um novo ID (`R-001`, `R-002`...).

### 6. Fase 0 — research.md (condicional)

Só crie `research.md` se restarem incertezas técnicas genuínas (ex: qual
biblioteca usar, formato de dados desconhecido). Formato por item: Decisão /
Justificativa / Alternativas consideradas. Se não houver incerteza, pule este
arquivo.

### 7. Fase 1 — design (condicional)

- `data-model.md`: só se a feature envolve entidades/dados novos ou
  alterados.
- `contracts/<superfície>.md`: só se a feature expõe ou altera uma superfície
  de API.
- `logic/<nome>.md`: só se a feature possuir lógicas de negócio complexas, algoritmos não-triviais ou regras onde o executor poderia tomar decisões arquiteturais ruins (inclua pseudocódigos ou assinaturas de interfaces para delimitar estritamente o "como").
- `quickstart.md`: passos de verificação manual — prerrequisitos, checagens
  automatizadas, cenário ponta a ponta, e os itens cross-cutting do
  pre-acceptance checklist da constitution deste projeto, se ela definir um
  (ex: disponibilidade de serviços, configuração, conectividade).

Preencha `## Project Structure` com a árvore **real** deste repositório,
exatamente como encontrada no passo 2 — nunca com um exemplo genérico nem com
a estrutura de outro projeto.

### 7.5. Testes de contrato — executáveis, vermelhos, travados

O `sdd-execute` costuma rodar num modelo mais barato. Em vez de descrever em
prosa os testes que ele deveria escrever (e deixar que ele interprete, e
depois valide o próprio código), este passo escreve **o código dos testes
que definem "pronto"**. O executor só pode fazê-los passar, nunca editá-los.

**Orçamento:** no máximo 5 casos de contrato quando o runner do projeto permitir contagem confiável; a seleção deve priorizar os cenários P1.
O script de trava recusa mais que isso. Com 5, cada teste precisa valer a
pena — priorize nesta ordem e pare quando o orçamento acabar:

1. O cenário de aceite central de cada story **P1** (o que prova que a
   story existe).
2. O caso traiçoeiro onde um executor errar é mais provável e mais caro:
   corridas/reentrância, estado intermediário, a regra de `logic/*.md` que
   parece contraintuitiva.
3. Um invariante da constitution que esta feature toca de fato (ex: foco em
   estado vazio/erro, restauração por id e não por índice, identidade lógica
   em vez de URL, segredo fora de log/erro).

**Fica de fora**: estilo, fiação trivial, stories P2+ que não são arriscadas,
E2E (fica no Polish do `sdd-execute`), e tudo que só é verificável em
hardware real/manualmente — isso vai pro `quickstart.md`. Se a feature for
pequena ou puramente visual, **zero testes de contrato é uma resposta
válida**: registre o porquê em `## Estratégia de Testes` e pule o resto
deste passo.

Regras de escrita:

- **Só pela interface pública** — API pública, CLI, retorno de função/export, props e DOM quando houver UI, ou colaboradores injetados. Nunca estado interno, nome de variável privada ou ordem de chamadas irrelevante.
- **Arquivo dedicado à feature**, seguindo a convenção de nomes e extensão do runner deste repositório; nunca copie extensão ou framework de outro projeto.
- **Reuse helpers/fakes/fixtures que já existem** nos testes da mesma área
  (achados no passo 2). Se precisar de um helper novo, ele também é
  entregue aqui e fica travado junto — o executor não deve inventar
  infraestrutura de teste.
- **Stubs em vez de só pseudocódigo**: crie os arquivos/assinaturas que os
  testes importam (tipos, props novas, funções exportadas com corpo
  `throw new Error('not implemented')` ou equivalente idiomático), pra que
  o teste compile. Isso fixa o "como" melhor que markdown; `logic/*.md`
  continua explicando o porquê. Os stubs **não** são travados — são o ponto
  de partida do executor.
- **Restrições do runner:** não use mecanismos que desabilitem ou reduzam o contrato (por exemplo, skip/only/todo quando o framework oferecer esses recursos); aplique somente regras verificáveis no runner real.
- Cada teste cita no nome ou num comentário de uma linha a origem que
  cobre (`FR-###`, `US1/AC3`, `Constitution: <princípio>`).

Prove que os contratos falham pelo motivo esperado usando o comando real do runner deste repositório, registrado no plan.md; nunca por import, sintaxe ou tipo. Rode também a suíte da área tocada para confirmar que os stubs não quebraram testes existentes.
Se o verificador existir neste repositório, use o comando abaixo; caso contrário use o mecanismo de lock definido pelo runner real.
Trave:

```powershell
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug <NNN-slug> -Write -Paths <arquivo1>,<arquivo2>
```

Isso grava o contract-tests.lock (caminho + SHA256). Contagem e testes desabilitados dependem do adaptador do runner; sem adaptador, registre a limitação explicitamente no plano.
Registre em `## Estratégia de Testes` de `plan.md`: os arquivos de
contrato, o comando exato pra rodá-los, a saída vermelha esperada (1 linha
por teste) e o mapeamento teste → origem.

### 8. Constitution Check — gate pós-design

Reavalie os princípios contra o design final (coluna Pós-Design da mesma
tabela). Mesma disciplina do passo 5: violação não justificável para o skill.

### 9. Escreve plan.md

Neste ponto, `plan.md` deve ter: Summary, Technical Context, Decisões
Invariantes, Constitution Check (completo), Project Structure, Complexity
Tracking, e `## Estratégia de Testes` (prioridade unitário → contrato/
integração → E2E → manual como último recurso, mais os comandos-base de
build/test copy-paste-prontos — descobertos na exploração, ex. `dotnet test`,
`npm test`, `pytest`, o que for real neste repositório).

As cinco seções finais do template (`Estado Atual`, `Riscos e Decisões` já com
os itens do passo 5, `Execution Notes`, `Arquivos Principais`, `Cuidados para
Retomada`) ficam como estão no template — **só o `sdd-execute` preenche/edita
essas depois**. Não as reescreva nem as remova.

### 10. Gera tasks.md

A partir de `.planning/templates/tasks-template.md`. Preencha `## Path
Conventions` com os caminhos reais descobertos no passo 2 (mesma Structure
Decision de `plan.md`). Organize por user story (P1, P2, P3... em ordem de
prioridade), cada fase seguindo o template de 5 blocos:

1. **Goal/Objetivo** — 1 frase.
2. **Contrato da fase** (se houver teste de contrato nela) — os testes do
   passo 7.5 que esta fase deve deixar verdes, pelo nome, e o comando exato
   pra rodá-los. Esses testes já existem e estão travados: **não** viram
   task de escrita.
3. **Implementation/Checklist** — tasks com `[TaskID] [P?] [Story?]` e
   caminho de arquivo real (nunca um placeholder). Cada task que contribui
   pra um contrato cita qual (`→ contrato: <nome do teste>`). Se a task envolver lógica complexa, referencie aqui o arquivo `logic/<nome>.md` criado no passo 7 ou o stub criado no passo 7.5.
4. **Tests/Testes da fase** — checklist **separado** dos itens de
   implementação, só com testes **adicionais** que o executor escreve (em
   arquivos que não são de contrato) — cobertura complementar, não a
   definição de pronto.
5. **Critério de Conclusão** — prosa explícita do que "pronto" significa
   nesta fase/story. Se a fase tem contrato, o critério começa por ele,
   como comando verificável (ex: "`<comando>` → 3/3 verdes, e
   `check-contract-tests.ps1` íntegro").
6. **Registro da Fase** — deixe o bloco vazio (`Status:` / `Feito:` /
   `Contrato:` / `Testes executados:` / `Pendências:`); só o `sdd-execute`
   preenche.

A fase final Polish inclui o **Checklist de Release**: um item por fase
concluída, mais os gates cross-cutting relevantes a este projeto, mais (se
houver contrato) "todos os testes de contrato verdes e
`check-contract-tests.ps1` íntegro".

### 11. Analyze — checagem final, estritamente read-only

Cruze `spec.md`, `plan.md`, `tasks.md` e a constitution procurando:

- **Duplicação** — requisitos ou tasks repetidos sem necessidade.
- **Ambiguidade** — termos vagos que deveriam ter virado `[NEEDS CLARIFICATION]`.
- **Subespecificação** — user story sem task correspondente, ou vice-versa.
- **Alinhamento com a Constitution** — qualquer princípio dela não coberto.
- **Lacunas de Cobertura** — todo `FR-###`/`SC-###` deveria ter pelo menos uma task rastreável.
- **Inconsistência** — terminologia divergente entre os 3 arquivos.
- **Contrato** — a story P1 central sem teste de contrato nem justificativa
  registrada; teste de contrato sem origem citada; teste de contrato que
  depende de detalhe interno; nenhuma task apontando pra um contrato.

Apresente uma tabela de achados (ID | Categoria | Severidade | Local | Resumo
| Recomendação, no máximo 50 linhas) com severidade CRITICAL (viola a
constitution) / HIGH / MEDIUM / LOW, **só no chat**. Nunca grave isso em
arquivo. Sugira correções, não as aplique sozinho.

### 12. Atualiza o backlog

```powershell
.\.planning\scripts\powershell\update-feature-status.ps1 -Slug <NNN-slug> -Status Planejada
```

### 13. Relata

O que foi escrito, resultado do Constitution Check (pré e pós), os testes de
contrato (quantos de 5, o que cada um cobre, a saída vermelha confirmada — ou
por que a feature não tem nenhum), resumo do Analyze, e uma recomendação
explícita: resolver achados CRITICAL antes de
rodar `sdd-execute`, ou seguir em frente se estiver tudo limpo.

### 14. Handoff para execução em outra sessão — sempre

O `sdd-execute` costuma rodar em outra sessão (às vezes noutro modelo), sem
nada desta conversa. Ao concluir, **sempre** escreva um resumo de handoff
autossuficiente, em português, e:

1. grave-o em `sdd/specs/<NNN-slug>/handoff.md` (sobrescreve o anterior, se
   houver — o `sdd-plan` pode rodar de novo na mesma feature);
2. mostre o mesmo conteúdo no chat, como fechamento do relato do passo 13.

Tudo que o executor precisa saber e que **não é óbvio** relendo os
documentos na ordem certa — nunca uma cópia da spec ou do plano. Seções,
nesta ordem:

- **Contexto**: repositório/branch, stack em uma linha, próximo comando
  exato (`/sdd-execute <NNN-slug>`), status no backlog, e qualquer arquivo
  que tenha mudado em disco fora desta sessão e precise ser relido.
- **O que a feature entrega**: uma linha por user story (prioridade +
  essência), incluindo decisões do usuário que contrariam a expectativa
  óbvia (ex.: "a tela X **mantém** Y").
- **Leitura obrigatória, em ordem**: `spec.md`, `plan.md`, `tasks.md`,
  cada `logic/*.md`/`data-model.md`/`contracts/*.md` criado, `quickstart.md`,
  constitution — com uma frase do que cada um tem.
- **Testes de contrato**: caminho de cada arquivo travado com contagem e
  fase, o comando exato para rodá-los, o comando de integridade da trava, e
  as travas de **outras** features que esta pode quebrar (se houver). Se não
  há contrato, diga por quê.
- **Stubs criados**: arquivo → o que existe nele e o que é provisório (ex.:
  prop opcional só até a task T0NN remover).
- **Armadilhas já mapeadas**: restrições descobertas na exploração que um
  executor erraria sem saber (tipos presos por contratos travados, regra de
  CSS/plataforma, constante que não pode mudar, "nunca rede aqui", arquivo
  que não existe e precisa ser criado, flakes conhecidos, caminhos de E2E).
  Cada item com o porquê em meia frase.
- **Pendências do Analyze**: uma linha por achado **não resolvido**
  (ID, severidade, resumo, recomendação). Esta é a única forma de o
  resultado do Analyze sobreviver à sessão — a tabela completa continua só
  no chat (passo 11).
- **Gate de pronto**: contratos verdes + travas íntegras, comandos de
  tsc/lint/testes/build/E2E do projeto, quickstart, docs a atualizar no
  Polish, e se a passada em hardware real é gate ou recomendação.

Seja específico (caminhos, nomes de função, IDs de task/decisão/risco) e
curto: é um mapa para o executor, não um segundo plano.

## Handoff

`sdd-execute` exige `spec.md` + `plan.md` + `tasks.md`. Se existir
`contract-tests.lock`, ele herda os testes travados como definição de pronto
— e é proibido de editá-los. O Analyze não deixa rastro em arquivo além da
seção "Pendências do Analyze" de `handoff.md` (passo 14) — é por ali que um
CRITICAL/HIGH não resolvido chega a uma sessão futura do `sdd-execute`, que
deve ler `handoff.md` quando ele existir.
