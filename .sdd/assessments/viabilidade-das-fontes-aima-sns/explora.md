# Assessment Explora: Viabilidade das fontes AIMA e SNS

- **Slug**: viabilidade-das-fontes-aima-sns
- **Criado**: 2026-11-20
- **Origem**: pedido do autor: "vamos avaliar AIMA e SNS juntos"; fontes condicionais em [.docs/fontes_de_dados.md](../../../.docs/fontes_de_dados.md).
- **Natureza da prova**: consulta pública e leitura do lake local; nenhuma fonte nova implementada, nenhum dado promovido e nenhuma API SNS chamada.

## Ideia Bruta

Verificar se as duas fontes podem acrescentar contexto territorial confiável
sobre comunidades migrantes e acesso a médico de família aos 308 municípios
CAOP. A avaliação é conjunta; cada fonte precisa passar seus próprios gates.

## Evidência a Favor

### E01 — Nacionalidade já capturada no Pordata

O inventário anterior subestimou o dataset Pordata 354. O CSV local e
`.data/lake/bronze/stg_observation/data.parquet` preservam a nacionalidade em
`filter_1`. Para `dataset_id=populacao_estrangeira_residente`, ano 2023,
`filter_1=2.1. Brasil`: **308 DICO únicos, 308 valores**, soma 368.391.
Lisboa/DICO 1106: 33.407. Fonte/run `20261111T192324457144Z-7064a1de`.
O dataset municipal vigente tem 103.488 observações e anos 2008–2023.
É possível atender o recorte brasileiro reaproveitando a ingestão existente;
a evidência não demonstra um indicador ou interface já construídos.

Angola, Cabo Verde, Guiné-Bissau e São Tomé e Príncipe também têm 308 valores
em 2023. Moçambique tem 308 linhas com valor nulo; Timor-Leste e Guiné
Equatorial não aparecem como categorias próprias. Uma soma dessas categorias
nunca deve ser apresentada como CPLP completa ou número de falantes de português.

### E02 — AIMA publica dados municipais atuais, com atribuição

A [página oficial de relatórios](https://aima.gov.pt/pt/a-aima/relatorios-de-migracoes-e-asilo)
liga o [RMA 2025](https://aima.gov.pt/docs/Relatorio_de_Migracoes_e_Asilo_2025.pdf),
71 páginas, setembro de 2026, e a
[adenda municipal 2024](https://aima.gov.pt/media/pages/documents/65870eae21-1761164556/populacao-estrangeira-residente-2024_distrito_concelho.pdf),
nove páginas. Ambos foram baixados integralmente para a pasta privada de provas.
No RMA 2025, página física 2, a AIMA permite usar a informação estatística com
identificação clara da fonte; não foi presumida uma licença Creative Commons.
O robots consultado permite os caminhos desses documentos e veda pesquisas.

RMA 2025: seção 7.1, página física 54, população/concessões por nacionalidade
e gênero; seção 7.3, páginas físicas 61–70, população por concelho e gênero.
Páginas 61 e 62 foram renderizadas e inspecionadas visualmente: há total,
masculino e feminino, sem coluna de nacionalidade. A adenda 2024 tem distrito,
concelho e total, com texto extraível. **Não foi encontrado o cruzamento
nacionalidade × concelho nessas publicações.** Isso não prova que ele inexista
em todos os produtos da AIMA.

### E03 — Alternativa oficial estruturada para nacionalidade

O [catálogo público do INE no dados.gov.pt](https://dados.gov.pt/pt/datasets/populacao-estrangeira-com-estatuto-legal-de-residente-n-o-2/)
identifica **0013219**, população estrangeira com estatuto legal de residente
por local de residência/NUTS 2024 e nacionalidade, anual, CC BY 4.0.
É candidato a atualizar/complementar o Pordata; a cobertura municipal efetiva,
os anos e as nacionalidades precisam ser confirmados nos metadados/dados.
Não confundir com 0013193: esse indicador mede solicitações de estatuto,
um fluxo diferente do estoque de residentes.

### E04 — SNS oferece série nova e exportação declarada

O [novo dataset oficial](https://transparencia.sns.gov.pt/explore/assets/inscritoscuidadosdesaudeprimarios/)
é `inscritoscuidadosdesaudeprimarios`, autoria ACSS. O HTML contém metadados
JSON-LD e links oficiais para CSV/JSON/XLSX na Explore API v2.1.
As dimensões visíveis são período, região, ULS e nacionalidade agrupada em
portuguesa/estrangeira. Inclui inscritos, elegíveis/não elegíveis, com/sem
médico atribuído e sem médico por opção. A
[ACSS confirma o lançamento e os diferentes universos](https://www.acss.min-saude.pt/2026/09/30/portal-da-transparencia-do-sns-disponibiliza-novos-indicadores-sobre-o-rnu-e-sobre-a-atividade-assistencial-do-setor-social-e-privado-prestada-para-o-sns/).
Há oportunidade de comparar acesso por nacionalidade agrupada; isso não
identifica brasileiros nem mede diretamente qualidade clínica ou tempo de espera.

## Evidência Contra

1. **AIMA não satisfaz ainda o recorte nacionalidade × município.** As duas
   tabelas separadas não permitem cruzamento estatístico; não multiplicar
   percentuais nacionais pelos totais municipais. O total municipal atual
   pode ter valor como complemento, mas é um objetivo diferente.
2. **Extração AIMA 2025 tem custo adicional.** As tabelas do anexo são imagens
   no PDF: extração textual não devolve as linhas. OCR/curadoria exige controle
   de somas, identidades/homônimos e revisão. Ainda não foi executado OCR nacional.
3. **Universos migratórios diferentes.** A nota da seção 7.1 do RMA inclui
   títulos válidos, processos em regularização e instrumentos específicos.
   A série de estatuto legal do INE/Pordata não deve ser substituída nem ligada
   diretamente a esses totais sem preservar definição, versão e referência.
4. **SNS mudou em julho de 2026.** O
   [dataset antigo](https://transparencia.sns.gov.pt/explore/assets/utentes-inscritos-em-cuidados-de-saude-primarios/)
   declara descontinuação e quebra da série. O denominador atual é elegibilidade;
   a descrição tem nota específica sobre exclusão de ausência por opção.
   Preservar contagens e taxas nativas e validar a fórmula antes de derivar índices.
5. **ULS não equivale a município.** O
   [relatório oficial da ULS Santa Maria](https://www.ulssm.min-saude.pt/wp-content/uploads/2025/06/Relatorio_e_contas_2024.pdf)
   descreve freguesias de Lisboa e Mafra; a
   [ULS Lisboa Ocidental](https://www.ulslo.min-saude.pt/index.php/comunicacao/destaques/461-contactos-dos-cuidados-de-saude-primarios-da-ulslo)
   integra Lisboa Ocidental/Oeiras e Cascais. Um município pode envolver mais
   de uma ULS. Não atribuir uma taxa municipal única por nome, sede, média
   simples ou peso populacional inventado. Exige correspondência oficial
   versionada e definição específica para casos divididos.
6. **Cobertura SNS continental.** A
   [infografia oficial ACSS](https://www.acss.min-saude.pt/wp-content/uploads/2026/09/Infografias_RNU_agosto.pdf)
   identifica Portugal Continental como universo. Ausência de Açores/Madeira
   não significa zero nem cobertura nacional de 308 municípios.
7. **Gate operacional SNS não resolvido.** O
   [robots.txt](https://transparencia.sns.gov.pt/robots.txt), consultado diretamente,
   contém `User-agent: * / Disallow: /api/`; não foi chamada a API nem usado outro
   host/User-Agent para contornar. A exceção aprovada para Wikipedia não se estende
   ao SNS. Constitution IV exige resolução explícita antes de implementar.
8. **Licença SNS não comprovada por dataset.** JSON-LD novo não declara licença.
   Os [termos do portal](https://transparencia.sns.gov.pt/pages/termos-e-condicoes/),
   seção 7, remetem à legislação e às condições aplicáveis. Não transferir CC BY
   de outro dataset antigo para esta série. Falta confirmar as condições exatas
   de reutilização/publicação e acesso anônimo/cotas na API.

## Perguntas em Aberto

- Priorizar o problema de comunidade migrante usando Pordata/INE, deixando AIMA
  como complemento independente, ou manter a exigência de coleta direta AIMA?
- Aceitar observações SNS nativas por ULS no Continente, com ausências e casos
  municipais divididos explícitos, ou exigir dado municipal direto nos 308?
- Autorizar exceção pontual para leitura identificada/limitada da API oficial
  SNS, como risco registrado, sem contorno, e mantendo licença como gate separado?

## Reprodutibilidade e limites

Provas privadas em `.data/receipts/aima-sns-assessment/`: PDFs, imagens,
HTML/robots; fora do Git. SHA-256 RMA 2025:
`b3ad31f81ba837e3a46d86641d719d9164722a442e93409e52f90eb8722584e9`;
adenda 2024:
`0e11ba1007f0839fe7f1ae1224186b52ae836747159df21738eda2309f7478b3`.
A consulta ao Parquet foi somente leitura; não houve recoleta Pordata/INE,
promoção, alteração de catálogo ou acesso a dados pessoais.

Consulta de documentação da Explore API via Context7, biblioteca
`/websites/help_opendatasoft_apis_ods-explore-v2`, confirmou endpoints de
[records/exports e limites](https://help.opendatasoft.com/apis/ods-explore-v2/explore_v2.1.html).
Documentação de API não comprova funcionamento, acesso anônimo ou licença
deste dataset; esses pontos permanecem sem prova de execução.

## Decisões do autor — após a exploração inicial

Em 2026-11-20, por três respostas estruturadas, o autor escolheu:

1. Reaproveitar Pordata e avaliar atualização pelo INE; AIMA como complemento opcional.
2. Preservar dados SNS por ULS, associar municípios somente com evidência e
   explicitar ausências; nenhuma exigência de inventar dados para as ilhas.
3. **R-001 — risco aceito específico SNS:** exceção à regra `/api/` do
   robots somente para leitura da API oficial do portal, identificada,
   serial e limitada, respeitando bloqueios e sem contorno. A licença
   continua como gate separado. Não altera a constitution, não herda a
   exceção da Wikipedia nem autoriza outros serviços.

Os bloqueios e perguntas acima descrevem o estado inicial; somente os itens
explicitamente respondidos foram resolvidos. A prova da API será anexada a
seguir, sem substituir o registro original.

## Prova posterior às decisões — API SNS e metadados INE

Após R-001, três leituras SNS identificadas/seriais, sem chave, retornaram
HTTP 200: metadados, cinco registros e exportação JSON completa. Não houve
403/429, retentativa nem mudança de host. O resultado foi guardado apenas
na pasta privada de pesquisa, não no raw/lake operacional do projeto.

- **SNS**: 234 registros/234 chaves únicas (`período`, `ULS`, `nacionalidade`),
  39 ULS × 2 nacionalidades × 3 meses; julho, agosto e setembro de 2026,
  78 registros em cada mês. Produto cartesiano completo no universo publicado;
  isso não demonstra correspondência com todos os municípios continentais.
- Contagens conferem em todos os registros: inscritos = elegíveis + não
  elegíveis; elegíveis = com médico + sem médico atribuído + sem médico por opção.
  As duas taxas conferem com denominador **elegíveis menos sem médico por opção**,
  tolerância de 0,00051 ponto percentual para arredondamento a três casas.
  Não usar a redação simplificada da fórmula sem considerar essa exclusão.
- Metadados reais: frequência `MONTHLY`, universo `Portugal Continental`,
  `data_processed=2026-11-02T17:30:50.057Z`, referência setembro/2026.
  `modified=2026-08-11` não é a última referência da série; não usar esse campo
  sozinho para frescor. Campos de licença, URL de licença e atribuição estão nulos.
- O [registro exato no dados.gov.pt](https://dados.gov.pt/pt/datasets/inscritos-em-cuidados-de-saude-primarios)
  confirma ACSS e **Licença não especificada**. A política genérica CC BY do
  catálogo não substitui essa marcação específica. Os termos SNS permitem
  reutilização conforme condições/legislação aplicáveis, mas não declaram CC BY.
  A [Lei 26/2016 consolidada](https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2016-106603618),
  artigos 19–23, é uma base possível a examinar; não foi convertida nesta
  avaliação em autorização irrestrita ou licença inventada do dataset.
- **INE 0013219**: metadados oficiais consultados confirmam 308 categorias
  municipais, anos 2021–2023, atualização de 2024-09-20. Nacionalidades:
  Total, BR, UA, CV, RO, AO, GW, GB, MD, CN, ST e Outros países.
  Portanto, não há ganho temporal demonstrado sobre o Pordata local e ainda
  não há decomposição completa da CPLP. Nenhuma consulta nacional de dados
  INE foi executada nem atualização foi promovida.
- **Adenda AIMA 2024**: extração exploratória do texto produziu 308 pares
  distrito/concelho distintos; a soma dos totais é 1.543.697. Ainda não é
  um pipeline, uma correspondência DICO validada nem prova de extração do RMA 2025.

Recibos: `sns-meta.*`, `sns-sample.*`, `sns-export.*`, `sns-export-audit.json`,
`ine-0013219-meta.body` e `adenda-2024-row-audit.json`. SHA-256 do export SNS:
`204b6cbbcfd08d08a8b7e98bcfefc7da3803617fd7252cff423ffb193694bb1e`.
As dúvidas de acesso e de escolha de cobertura foram resolvidas; a licença
de reutilização/publicação e a correspondência territorial completa não foram.
