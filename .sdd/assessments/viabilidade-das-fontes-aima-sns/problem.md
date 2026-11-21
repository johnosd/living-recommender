# Assessment Problem: Comunidades migrantes e acesso a médico de família

- **Slug**: viabilidade-das-fontes-aima-sns
- **Criado**: 2026-11-20
- **Explora**: ./explora.md
- **Escopo em avaliação**: fontes condicionais do inventário; opções de adaptação ainda não aprovadas.

## Problem Statement

Pessoas que comparam municípios portugueses precisam de informação territorial
rastreável sobre comunidades migrantes e acesso a médico de família. O projeto
ainda não confirmou uma fonte nova que acrescente os dois recortes com cobertura,
atualidade e significado compatíveis com a geografia municipal vigente.

## Usuários / Partes Afetadas

- Pessoas que pretendem morar em Portugal, incluindo brasileiros: precisam
  comparar territórios sem confundir comunidade residente com entradas anuais,
  nem taxa de uma área de saúde com atendimento garantido no município.
- Mantenedor: precisa de coleta reproduzível, brutos imutáveis, licença e
  correspondência territorial verificáveis, sem duplicar dados já ingeridos.

## Goals

- Verificar o valor incremental e a viabilidade de AIMA e SNS separadamente.
- Recuperar a cobertura de nacionalidade já existente no Pordata; avaliar INE
  como candidato estruturado para atualização, sem presumir sua cobertura.
- Para AIMA, confirmar se o recorte nacionalidade × município é público;
  explicitar se uma proposta diferente seria apenas total municipal mais atual.
- Para SNS, verificar série vigente, exportação, unidade territorial,
  elegibilidade, cobertura, direitos de uso e compatibilidade com robots.
- Entregar veredito fundamentado e perguntas reais antes de uma spec.

## Non-Goals

- Implementar coletores, alterar catálogo, promover dados ou criar infraestrutura.
- Calcular ranking, percentuais finais ou um indicador de lusofonia incompleto.
- Tratar estrangeiros como sinônimo de brasileiros, CPLP como língua falada,
  novas autorizações como entradas no país ou elegibilidade como garantia de consulta.
- Transformar total nacional por nacionalidade em valores municipais estimados.
- Completar ilhas ou municípios com múltiplas ULS usando zeros ou médias inventadas.
- Obter informação individual de utentes, contactar entidades ou assumir licença.

## Success Metrics

- Duas fontes avaliadas, cada uma com formato, referência, território,
  atualização, direitos de uso e limitação identificados por evidência.
- Baseline Pordata medido no lake: DICO únicos, valores e ausências por
  nacionalidade/ano; nenhuma categoria nula interpretada como zero.
- Para autorizar uma futura implementação: endpoint/arquivo de leitura testado
  dentro das regras aprovadas; condições de reutilização verificadas; todas as
  unidades publicadas classificadas como associáveis ou explicitamente ausentes.
- Relatório futuro deve enumerar os 308 municípios, distinguir dado próprio,
  herdado, compartilhado ou ausente e nunca declarar 308 valores sem prova.
- Veredito por fonte e conjunto sem converter lacunas técnicas em aceite.

## Cost of Inaction

A avaliação anterior pode gerar um coletor AIMA redundante para brasileiros,
enquanto o Pordata já contém 308 observações municipais de 2023. No SNS,
implementar a descrição antiga sem revisão pode produzir uma série falsamente
contínua ou uma taxa municipal incorreta. Adiar a inclusão mantém essas
dimensões sem novos dados; isso é preferível a publicar valores sem suporte.

## Clarificações aprovadas durante a avaliação

As três respostas estruturadas de 2026-11-20 fixaram o caminho: reutilizar
Pordata e verificar INE; AIMA opcional. SNS mantém observações por ULS,
correspondência municipal somente com evidência e ausências explícitas.
A exceção específica para leitura identificada/limitada da API SNS foi
aceita; licença permanece gate separado. Nenhuma autorização de implementação,
publicação, contato com terceiros ou mudança da constitution foi inferida.
