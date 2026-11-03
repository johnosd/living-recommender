# ADR-[NNN]: [Título da Decisão]

<!--
  COMO USAR ESTE TEMPLATE

  Uma ADR (Architecture Decision Record) documenta uma decisão arquitetural
  fundamental do projeto — stack, plataforma, banco de dados, framework — com
  o raciocínio completo, não só a conclusão. Diferente da constitution.md
  (regras normativas, terso) e diferente das Decisões Invariantes de uma
  feature (locais, descartáveis com a feature), a ADR é:

  - Projeto-inteiro, não de uma feature específica.
  - Permanente — não é apagada quando fica desatualizada, é EMENDADA.
  - Escrita com alternativas rejeitadas explícitas, não só a decisão final.

  EMENDA, NÃO REESCRITA: se uma ADR posterior invalida parte desta, NÃO
  reescreva o texto original. Adicione uma nota inline no ponto afetado:

      **Atualização (ADR-0XX):** [o que mudou e por quê, resumido]. Ver
      ADR-0XX para o raciocínio completo.

  Isso preserva o histórico de decisão em vez de apagar o contexto de por
  que algo foi escolhido originalmente.

  Nem toda ADR precisa virar regra na constitution.md — só as que devem ser
  um gate obrigatório em todo plano futuro (ex: "DEVE usar Postgres") valem
  a promoção. Uma decisão de biblioteca específica, por exemplo, normalmente
  fica só documentada aqui, sem virar princípio da constitution.

  Apague os comentários HTML (como este) depois de preencher.
-->

## Status

<!-- Proposta | Aceita | Superada por ADR-0XX | Depreciada -->

[STATUS]

## Data

[AAAA-MM-DD]

## Contexto

<!--
  O problema que motivou a decisão: requisitos concretos, restrições,
  constraints de custo/operação/equipe. O suficiente pra alguém sem contexto
  nenhum entender por que essa decisão precisava ser tomada.
-->

[CONTEXTO]

## Decisão

<!--
  O que foi escolhido. Inclua detalhe suficiente pra orientar implementação
  — trecho de código/config quando ajuda a fixar o "como", não só o "o quê".
-->

[DECISÃO]

## Alternativas Consideradas

<!--
  Cada alternativa real que foi avaliada, com o motivo concreto da rejeição
  (ou aceitação, se for a escolhida). "Rejeitada por ser pior" não é motivo
  concreto; "rejeitada porque o free tier expira em 14 dias" é.
-->

### [Alternativa 1]

- [Descrição]
- **Rejeitada:** [motivo concreto]

## Consequências

### Positivas

- [Consequência]

### Negativas

- [Consequência — inclua o que foi conscientemente aceito como trade-off]

### Caminho de Migração / Evolução Futura

<!--
  Sob quais condições esta decisão seria revisitada, e como migrar se isso
  acontecer. Não precisa ser um plano detalhado — só o suficiente pra uma
  sessão futura saber por onde começar.
-->

[CAMINHO DE MIGRAÇÃO]
