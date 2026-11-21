# Rascunho de esclarecimento de reutilização — SNS

**Estado**: rascunho local, não enviado. Destinatário proposto: apoio técnico
indicado nos termos do Portal da Transparência SNS; eventual encaminhamento
ao detentor ACSS. Enviar somente mediante instrução explícita do autor.

**Assunto**: Condições de reutilização do dataset Inscritos em Cuidados de Saúde Primários

Pretendemos reutilizar os dados estatísticos agregados do conjunto
`inscritoscuidadosdesaudeprimarios`, publicado pela ACSS no Portal da
Transparência do SNS, em um projeto de comparação de territórios portugueses.

A consulta seria feita pela API oficial de leitura, com identificação do
projeto, baixa frequência e respeito a limites e bloqueios. Pretendemos
guardar as respostas e a proveniência para auditoria, preservando período,
unidade territorial ULS, nacionalidade agrupada e definição das variáveis.
Uma etapa futura poderá exibir contagens/taxas agregadas com identificação
da fonte, data de referência e sinalização clara de eventual herança territorial.
Não pretendemos obter ou divulgar dados individuais nem usar logótipos.

O campo de licença está vazio na API, e o dados.gov.pt identifica o conjunto
como de licença não especificada. Os termos do portal remetem à legislação
aplicável e às condições de reutilização. Solicitamos esclarecer:

1. Quais condições/licença regem armazenamento e reutilização/publicação dos
   dados deste conjunto, incluindo se há diferenças entre uso não comercial
   e eventual uso comercial?
2. Qual atribuição deve acompanhar os dados e suas transformações?
3. É permitido automatizar leituras periódicas pela API oficial para esse uso,
   considerando a regra genérica `/api/` do robots.txt? Quais limites devem ser observados?
4. Há fonte oficial e versionada para a abrangência territorial de cada ULS,
   incluindo municípios divididos entre unidades?

Referências: [dataset](https://transparencia.sns.gov.pt/explore/assets/inscritoscuidadosdesaudeprimarios/),
[catálogo](https://dados.gov.pt/pt/datasets/inscritos-em-cuidados-de-saude-primarios),
[termos](https://transparencia.sns.gov.pt/pages/termos-e-condicoes/).
