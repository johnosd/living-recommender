<!--
Relatório de Impacto de Sincronização
- Mudança de versão: [versão anterior] -> [nova versão]
- Princípios modificados: [lista]
- Seções adicionadas: [lista]
- Seções removidas: [lista]
- Pendências: [lista, ou "nenhuma"]
-->

# Constitution do [NOME_DO_PROJETO]

<!--
  COMO USAR ESTE TEMPLATE

  A constitution é o único documento deste sistema que é checado como GATE
  formal pelo sdd-plan (duas vezes por feature: antes e depois do design).
  Por isso o teste de qualidade de cada princípio é sempre o mesmo:

      "o sdd-plan conseguiria checar isso contra um plano concreto e
      responder PASS ou FLAG?"

  Se a resposta for não — se o princípio é vago/aspiracional demais pra dar
  pra checar — reescreva até ficar verificável.

  Ruim (não dá pra checar):  "O código deve ter boa qualidade."
  Bom (dá pra checar):        "Toda feature DEVE ter critérios de aceite
                                ligados a comportamento visível ao usuário e
                                DEVE passar nas checagens de build/teste
                                antes de integrar."

  Prefira poucos princípios bons a muitos genéricos. 3-5 costuma bastar.
  Apague todos os comentários HTML (como este) depois de preencher — eles
  são só andaime, não fazem parte da constitution final.
-->

## Princípios Fundamentais

<!--
  Categorias que costumam valer um princípio próprio — nem todo projeto
  precisa de todas, e a lista não é exaustiva:

  - Segurança: o que é tratado como não-confiável por padrão; o que nunca
    pode vazar/ser commitado.
  - Fronteiras de arquitetura: quem é dono de quê (ex: service worker para
    captura da tela e janela do gravador para apresentação e ciclo de vida da
    gravação) — evita lógica duplicada ou na camada errada.
  - Qualidade verificável: o que toda mudança precisa ter pra ser
    considerada testada.
  - Disciplina de escopo: o que NÃO deve ser construído ainda — é o que
    mais evita scope creep silencioso entrando feature por feature.
  - Corretude operacional: o que precisa estar coordenado pra funcionar
    (permissões do manifesto, build, recarga da extensão e integrações externas).

  Cada princípio deve ser escrito como statement DEVE/NÃO DEVE, testável.
-->

### [PRINCÍPIO_1_NOME]

[PRINCÍPIO_1_DESCRIÇÃO]

### [PRINCÍPIO_2_NOME]

[PRINCÍPIO_2_DESCRIÇÃO]

### [PRINCÍPIO_3_NOME]

[PRINCÍPIO_3_DESCRIÇÃO]

## [SEÇÃO_2_NOME]
<!--
  Ex: Restrições do Projeto, Requisitos de Segurança, Padrões de Performance.
  Diferente dos Princípios acima (regras de qualidade/comportamento), esta
  seção costuma guardar FATOS travados do projeto: stack obrigatória,
  plataforma alvo, permissões da extensão, escopo de usuários e
  requisitos de privacidade aplicáveis. Coisas que não são "boa prática", são decisão já
  tomada e não deve ser revisitada sem emenda.
-->

[SEÇÃO_2_CONTEÚDO]

## [SEÇÃO_3_NOME]
<!--
  Ex: Fluxo de Desenvolvimento, Processo de Revisão, Quality Gates.
  O que precisa ser verdade antes de uma mudança ser considerada "pronta"
  — checklist de pré-aceite, o que uma revisão precisa checar. É o que o
  sdd-execute/sdd-converge vão usar como referência de "definition of done"
  no nível do projeto, além do Critério de Conclusão de cada fase.
-->

[SEÇÃO_3_CONTEÚDO]

## Governança
<!--
  O parágrafo de versionamento semântico abaixo é boilerplate reutilizável
  — raramente precisa mudar de projeto pra projeto. [REGRAS_DE_GOVERNANÇA]
  é o lugar pra regra específica deste projeto, se houver (ex: quem precisa
  aprovar uma emenda, se é revisão obrigatória com o dono do produto).
-->

[REGRAS_DE_GOVERNANÇA]

A constitution usa versionamento semântico. Uma versão MAJOR denota remoção ou
redefinição incompatível de um princípio. Uma versão MINOR denota um novo
princípio ou expansão material da governança. Uma versão PATCH denota
esclarecimentos, correções ou mudanças de texto não semânticas.

**Versão**: [VERSÃO] | **Ratificada**: [DATA_RATIFICAÇÃO] | **Última Emenda**: [DATA_ÚLTIMA_EMENDA]
