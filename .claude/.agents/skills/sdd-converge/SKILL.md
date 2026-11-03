---
name: sdd-converge
description: Compara a implementação real de uma feature contra sua spec/plano/tasks e a constitution do projeto, aponta lacunas (como novas tasks, nunca reescrevendo o que já existe) e, quando tudo bate, sincroniza o status final da documentação — incluindo o README.md do projeto, se existir e se algo relevante mudou. Use quando o usuário pedir para checar se uma feature está completa, achar o que falta antes de entregar, convergir uma feature, ou auditar a implementação. Exige pelo menos uma passada anterior do sdd-execute. NÃO edita código nem reescreve conteúdo existente de spec/plan/tasks — só anexa e atualiza campos de status.
---

# sdd-converge

Quarto estágio do sistema SDD, e o único não-linear: fecha o ciclo comparando
código real contra intenção declarada, e é o mecanismo que garante que a
documentação não fique desatualizada em relação ao que foi de fato construído
(a segunda metade do problema que motivou este sistema — a primeira metade é
o `sdd-execute` atualizar a doc a cada checkpoint).

## Fluxo

### 1. Gate de pré-requisito

```powershell
.\.planning\scripts\powershell\check-prerequisites.ps1 -Stage converge -Slug <NNN-slug> -Json
```

Exige `spec.md` + `plan.md` + `tasks.md`; avisa (não bloqueia) se `tasks.md`
tiver zero itens marcados.

### 2. Carrega o contexto de intenção

- `spec.md`: `FR-###`, `SC-###`, user stories, acceptance scenarios, edge
  cases.
- `plan.md`: arquitetura, Decisões Invariantes, Execution Notes acumuladas
  pelo `sdd-execute` (mostram o que foi de fato feito e quando).
- `tasks.md`: IDs existentes (pra saber o próximo ID livre, se precisar
  anexar), Registro da Fase de cada fase.
- `.planning/memory/constitution.md`: princípios que governam o projeto.

### 2b. Confere os testes de contrato

Se existir `contract-tests.lock` no diretório da feature:

```powershell
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug <NNN-slug>
```

- `FAIL` (arquivo alterado/removido) sem um `R-00X` em `## Riscos e
  Decisões` que registre a emenda aprovada → achado **CRITICAL**
  (`contradicts`, origem `plan: contrato`). Com a emenda registrada mas a
  trava não regravada → **HIGH**.
- Rode os arquivos de contrato (comando de `## Estratégia de Testes`).
  Qualquer um vermelho → achado **CRITICAL** se cobre uma story P1, **HIGH**
  caso contrário.
- Leia o código que faz os contratos passarem procurando atalhos: lógica
  que só funciona pros valores exatos do teste, mock da própria unidade,
  comportamento condicionado a ambiente de teste. Encontrado → **CRITICAL**.

### 3. Mapeia intenção → código real

Baseado nos arquivos/componentes que os artefatos acima realmente nomeiam
(mais uma busca direcionada pelos mesmos termos, se necessário) — **sem
inferir escopo além do que está documentado**. Isso não é uma auditoria geral
do repositório, é uma checagem de fidelidade desta feature específica.

### 4. Classifica lacunas

Para cada requisito/critério/decisão não confirmado no código:

- `missing` — não foi implementado.
- `partial` — implementado parcialmente.
- `contradicts` — o código faz algo diferente do que a spec/plano diz.
- `unrequested` — o código faz algo que não está em nenhum artefato (pode ser
  intencional e só não documentado, ou pode ser scope creep — reporte, não
  presuma).

Cada achado precisa de evidência (arquivo/linha ou trecho).

### 5. Severidade

- **CRITICAL**: viola um princípio da constitution, ou lacuna que bloqueia
  uma user story P1.
- **HIGH** / **MEDIUM** / **LOW**: conforme o impacto real.

### 6. Apresenta os achados

Tabela **Convergence Findings** (ID | Tipo de Lacuna | Severidade | Origem |
Evidência | Trabalho Restante) **no chat**, antes de escrever qualquer coisa.

### 7a. Se houver achado acionável

Acrescente uma única seção nova `## Phase N: Convergence` ao **final** de
`tasks.md` (N = próxima fase livre), com tasks `T{max+1:03d}` em diante,
CRITICAL/HIGH primeiro, cada uma citando sua origem (`FR-###` / `SC-###` /
`US n / AC n` / `plan: <decisão>` / `Constitution <princípio>`). **Nunca
toca em tasks ou fases já existentes** — só anexa.

```powershell
.\.planning\scripts\powershell\update-feature-status.ps1 -Slug <NNN-slug> -Status "Convergência Pendente"
```

Recomende rodar `sdd-execute` de novo pra cobrir as tasks novas, e depois
`sdd-converge` outra vez até não sobrar achado.

### 7b. Se não houver achado (convergiu limpo)

Este é o passo que sincroniza a documentação com a realidade ao final:

1. `tasks.md` fica **byte-idêntico** — não escreva nada nele.
2. Em `spec.md`, atualize **só** a linha `**Status**:` para `Convergida` —
   não toque no resto do corpo.
3. Em `plan.md`, **anexe** uma seção única `## Resultado Final` (nunca
   reescreva o que já existe): resuma o que foi de fato construído, os
   desvios acumulados nas Execution Notes, e decisões técnicas que ficaram
   diferentes do plano original.
4. Em `plan.md` → `## Riscos e Decisões`: qualquer item ainda sem
   `Resolvido:` que este convergence não achou evidência de violação recebe
   `Resolvido:` (mitigação confirmada pela auditoria). Itens que continuam
   abertos ficam registrados tal qual — não apague nada.
5. **Se existir um `README.md` do projeto** (tipicamente na raiz do
   repositório — não crie um se não existir, isso está fora do escopo deste
   skill): confira se algo que esta feature mudou deveria estar refletido
   nele — lista de features/capacidades, instruções de setup/execução,
   pré-requisitos, portas, comandos. Cerimônia proporcional, mesma lógica do
   tratamento de bugs no `sdd-execute`: só edite se houver uma mudança real
   e visível pra quem lê o README (não para refactors internos, não para
   detalhes de implementação que não aparecem lá). Edite cirurgicamente —
   só a seção afetada, nunca uma reescrita geral do arquivo. Se nada mudar,
   não toque nele.
6. `.\.planning\scripts\powershell\update-feature-status.ps1 -Slug <NNN-slug> -Status Convergida`
7. Relate "Convergido" ao usuário, incluindo se o `README.md` do projeto foi
   atualizado (e o quê) ou se não havia nada a mudar nele.

## Restrições importantes

- Nunca edita código-fonte.
- Nunca reescreve o conteúdo de `tasks.md` — só anexa uma fase nova, ou não
  toca nele.
- Nunca reescreve o corpo de `spec.md` ou `plan.md` — só a linha de Status
  (spec.md) e a seção `## Resultado Final` por anexação (plan.md).
- A exceção é o `README.md` do projeto, se existir: pode receber uma edição
  cirúrgica e pontual (não uma reescrita), e só quando a feature convergida
  mudou algo que um leitor do README precisaria saber. Nunca cria um
  `README.md` que não existia.
- Se não achar evidência suficiente pra confirmar ou negar algo (não achou o
  arquivo relevante, por exemplo), reporte como achado de severidade a
  julgar — não presuma que está tudo certo.
