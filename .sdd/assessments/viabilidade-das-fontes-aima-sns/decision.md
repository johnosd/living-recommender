# Assessment Decision: Viabilidade das fontes AIMA e SNS

- **Slug**: viabilidade-das-fontes-aima-sns
- **Decidido**: 2026-11-20
- **Problem**: ./problem.md
- **Evidências**: ./explora.md
- **Veredito**: needs-clarification
- **Fase a revisitar**: explora

## Scorecard

| Critério | Avaliação | Notas |
| --- | --- | --- |
| Validade do problema | strong | Comunidades migrantes e acesso a médico de família respondem a dimensões explícitas do produto; os recortes foram confirmados pelo autor. |
| Força da evidência | adequate | Pordata nacionalidade conferido no bruto/lake; dois PDFs AIMA lidos, incluindo inspeção visual; API SNS real e export completo auditados; metadados INE consultados. Não há prova de nacionalidade municipal direta AIMA nem de todos os vínculos ULS/CAOP. |
| Valor vs. custo de inação | adequate | Reaproveitar brasileiros em 308 DICO evita duplicação. SNS acrescenta informação de acesso ausente; adiar mantém a lacuna, mas evita herança territorial incorreta. AIMA acrescentaria atualidade do total, não o cruzamento pretendido. |
| Viabilidade / apetite | unknown | Acesso e consistência SNS comprovados; o autor aceitou ULS/ausências e a exceção robots. Licença específica segue nula no endpoint e não especificada no catálogo. O autor foi consultado e manteve licença como gate separado; sua resposta não concede direitos de terceiros. Correspondência territorial ainda exige levantamento. |
| Fit estratégico | strong | Preserva CAOP, proveniência, dado ausente explícito, coleta local e bruto imutável; não exige serviço pago ou backend de consulta. |

`unknown` acima é reconhecido como pendência real. O acesso público e o
HTTP 200 não foram usados como prova de licença. Não há estimativa de custo
de nuvem aprovada; a pesquisa não criou infraestrutura nem credenciais.

## Abordagens Candidatas

### 1. Reaproveitar Pordata; SNS nativo por ULS; AIMA opcional

- Caminho escolhido pelo autor. Para comunidades brasileiras, a ingestão já
  entrega os 308 valores de 2023; falta definir uso/atualização em etapa própria.
- INE 0013219 permite conferência estruturada, mas sua última referência também
  é 2023. Não prometer atualização temporal nem CPLP completa com essa série.
- SNS entra como observação por período/ULS/nacionalidade agrupada, com
  correspondência CAOP documentada. Municípios divididos conservam os vínculos;
  não recebem média inventada nem uma ULS escolhida arbitrariamente.
- AIMA pode ser uma fonte separada do total administrativo mais atual. Só
  especificar após demonstrar valor incremental suficiente para OCR/curadoria;
  não é requisito para aproveitar o Pordata existente.
- **Recomendada**: sim, após resolver o enquadramento de reutilização SNS.

### 2. Exigir nova fonte AIMA para brasileiros/CPLP por município

- Não recomendada com a evidência atual. RMA 2025 e adenda 2024 não publicam
  o cruzamento identificado na proposta original. Cruzar marginais produziria
  estimativas sem suporte e duplicaria parte do que já foi coletado.
- Não foi declarada inexistência universal desse dado: um novo produto oficial
  ou esclarecimento da AIMA pode justificar revisitar a fonte.

### 3. Incluir somente SNS quando houver dado municipal direto nos 308

- Não corresponde à decisão do autor. O universo atual é continental e a
  granularidade é ULS; esse requisito descartaria dados úteis antes de avaliar
  a correspondência e a apresentação honesta das ausências.

## Veredito

**needs-clarification para iniciar a entrega conjunta das novas fontes.**
Há viabilidade técnica comprovada para SNS: 234/234 registros únicos e
consistentes, 39 ULS, duas nacionalidades, julho–setembro/2026. As três
escolhas do autor resolveram a direção do produto e a exceção robots. Ainda
falta fechar o enquadramento de reutilização/publicação do dataset e registrar
essa condição de uso antes de criar um coletor, conforme constitution IV.
Não foi inferida CC BY a partir de outro dataset ou do catálogo genérico.

Isso não reabre ingestões entregues: o recorte brasileiro no Pordata está
disponível, sem necessidade de um novo coletor AIMA. AIMA permanece complemento
opcional, com universo administrativo preservado e sem substituir silenciosamente
a série INE/Pordata. A cobertura municipal SNS completa não foi demonstrada;
o escopo aceito admite ausências explícitas, mas não mascarar trabalho de
correspondência ainda não realizado como ausência da fonte.

### Se needs-clarification — Perguntas Bloqueantes

1. Qual é o enquadramento documentado de reutilização deste dataset SNS:
   condições aplicáveis dos termos/LADA, licença específica ou esclarecimento
   do detentor? Os metadados e o registro oficial ainda não especificam licença.
   O [rascunho de consulta](./consulta-reutilizacao-sns.md) está pronto para revisão;
   nenhuma mensagem foi enviada e contato externo exige instrução explícita.

**Fase a revisitar**: explora. A dúvida é de evidência da fonte; não pede ao
autor para escolher uma licença que não tem poder de conceder. Após resolver,
reavaliar o scorecard antes de entregar handoff `go` ao sdd-specify. Até lá,
não há feature nova numerada nem autorização inferida para implementação.

## Direção já confirmada para uma eventual especificação

Este registro não é handoff `go`; evita repetir as decisões já respondidas.

- Coleta/preparo local da série SNS vigente; preservar observações nativas,
  metadados, revisão, contagens, taxas e definição do denominador.
- Histórico anterior a julho/2026 separado, se vier a ser incluído; não
  misturar métodos/denominadores em uma única série contínua.
- Cobertura enumera 308 municípios e distingue próprio, herdado, compartilhado,
  fora do universo e pendência técnica. Associar por evidência territorial,
  com validade temporal; ilhas não recebem zero.
- R-001 aceito somente para API oficial SNS, leitura, identificação e baixa
  taxa serial; respeitar 403/429/Retry-After e não contornar bloqueios.
- Registrar licença/condições verificadas no catálogo antes do coletor.
- Reaproveitar a nacionalidade já preservada em Pordata; não gerar indicadores,
  ranking ou agregações CPLP incompletas dentro de uma entrega de ingestão.
