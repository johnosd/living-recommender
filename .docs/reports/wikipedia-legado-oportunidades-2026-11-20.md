# Wikipedia: análise do legado e oportunidades — 2026-11-20

## Resultado

O notebook antigo não extraía o artigo completo nem sua introdução: selecionava
algumas seções por palavras-chave, guardava um único parágrafo ou lista por
título e acrescentava campos de uma infobox. Há oportunidades de ampliar o
conteúdo e melhorar sua utilização, mas a identificação territorial precisa
ser corrigida antes: existem textos sobre países, aves e lugares de outros
países associados a nomes de municípios portugueses.

Esta análise subsidia a especificação solicitada. As sugestões de expansão
não são requisitos aprovados nem uma implementação da nova fonte.

## Arquivos examinados e método

- Notebook: `J:/MPAlugueisLisboa/src/wikipedia/wikipediaApi.ipynb`.
- Saídas: todos os 308 TXT em `J:/MPAlugueisLisboa/Bases/Wikipedia`.
- Entrada: `J:/MPAlugueisLisboa/Bases/Municipios/portugalMunicipios.csv`.
- Leitura estática do código e das saídas; o notebook não foi executado.
- Documentação oficial MediaWiki consultada por Context7; documentação
  Wikidata/Commons consultada diretamente para avaliar oportunidades.
- Três consultas HTTP de leitura: metadados agrupados de seis títulos;
  estrutura de seções de Lisboa em revisão identificada; entidade Wikidata
  associada a esse artigo. Sem nova coleta nacional e sem download de imagens.
- Nenhum arquivo do legado foi modificado. Os números abaixo descrevem o
  snapshot encontrado, não a cobertura atual da Wikipedia.

## O que o script fazia

1. Lê a coluna `Cidades` do CSV, sem código oficial de município.
2. Consulta um título em `pt.wikipedia.org` usando exatamente o nome recebido.
3. Obtém o HTML renderizado da página encontrada, sem fixar uma revisão.
4. Percorre títulos `h2`, `h3` e `h4`, buscando: clima, economia, educação,
   transporte, população, lazer, bairros, gastronomia, parques e jardins,
   demografia, turismo, `saude` e desporto.
5. Para cada título selecionado, executa `find_next(['p', 'ul'])` e guarda
   somente esse primeiro bloco, usando `get_text(strip=True)`.
6. Busca a primeira tabela com classe `infobox`; percorre seus `tr`, aceita
   linhas com exatamente dois `td` e concatena título/valor em texto.
7. Grava `<nome>.txt` com modo `w`, sobrescrevendo a saída anterior.

Evidências: célula 1, função `get_city_info_wikipedia`, linhas locais 7–25
(consulta), 39–49 (seções) e 53–64 (infobox); células 3–5 (CSV e gravação).

O CSV atual tem 309 nomes distintos e inclui ` São Paulo`, sem TXT
correspondente. O output gravado no notebook lista 308 buscas. Não é possível
reconstituir a sequência histórica apenas com esses arquivos; o CSV não deve
ser tomado como universo territorial do projeto novo.

## Auditoria das saídas

| Medida | Resultado |
| --- | ---: |
| Arquivos TXT | 308 |
| Volume total | 464.908 bytes |
| Arquivos com mensagem de página não encontrada | 4 |
| Outros arquivos sem trechos nem campos de infobox extraídos | 48 |
| Arquivos com algum bloco de seção extraído, inclusive vazio | 251 |
| Arquivos com ao menos um bloco de seção não vazio | 244 |
| Arquivos com linhas de infobox | 254 |
| Blocos de seção gravados | 766 |
| Blocos vazios, escritos apenas como marcador | 27 |

As categorias de seções e infobox se sobrepõem. Ter conteúdo não comprova que
ele pertence ao município correto, está atualizado ou foi extraído sem perdas.

As quatro mensagens de página não encontrada são: `Calheta [R.A.A.]`,
`Calheta [R.A.M.]`, `Lagoa [R.A.A.]` e `Vila da Praia da Vitória`.
Isso comprova falha da consulta pelo título usado, não inexistência de artigo
adequado sobre o município.

### Problemas semânticos confirmados

| Saída | Conteúdo observado | Consequência |
| --- | --- | --- |
| `Cuba.txt` | Clima e economia do país Cuba. | Texto de outro território aceito como informação municipal. |
| `Corvo.txt` | Infobox taxonômica de aves, com género Corvus. | Homônimo não geográfico. |
| `Gavião.txt` | Infobox taxonômica de aves de rapina. | Homônimo não geográfico. |
| `Nazaré.txt` | Nazareth, com campos em hebraico/árabe e site `nazarethinfo.org`. | Localidade de outro país. |
| `Santa Cruz.txt` | Lista de bairros/distritos brasileiros. | Página de desambiguação tratada como artigo municipal. |
| `Lisboa.txt` | Seção “População por freguesia” contém parágrafo sobre religiões. | Busca pelo próximo `p`/`ul` atravessou a fronteira da seção. |
| `Alpiarça.txt` e `Porto Santo.txt` | Campos municipais e de junta de freguesia aparecem na mesma extração. | Percurso por tabelas aninhadas mistura entidades. |

São exemplos verificados, não uma classificação semântica exaustiva dos
308 arquivos. Não é possível apresentar os demais como todos corretos.

### Limitações de extração

- **Conteúdo truncado:** os demais parágrafos/listas de cada seção são perdidos.
- **Introdução descartada:** não é coletada como campo próprio.
- **Fronteiras ignoradas:** a busca do próximo bloco pode capturar outra seção.
- **Vocabulário limitado:** história, geografia, cultura, museus, património e
  meio ambiente não são temas explicitamente selecionados. `saude` não casa
  com `saúde`; não há normalização de acentos na busca.
- **Estrutura destruída:** listas e links ficam concatenados; exemplos incluem
  palavras coladas em Braga e listas de monumentos/escolas em Aveiro.
- **Infobox frágil:** pressupõe dois `td`, perde outras estruturas e percorre
  descendentes aninhados. Campos e entidades podem ficar misturados.
- **Links incompletos:** o código de extração de `href` está comentado. Sites
  oficiais são concatenados como texto, sem preservar cada ligação.
- **Sem evidência reproduzível:** não guarda resposta bruta, page ID, revisão,
  instante da coleta, checksum ou licença/atribuição estruturados.
- **Operação frágil:** não define timeout, identificação própria no User-Agent,
  política de taxa/retry, inspeção de status HTTP ou tratamento de erros da API.

## Oportunidades além do legado

| Informação | Oportunidade e utilidade | Prioridade sugerida |
| --- | --- | --- |
| Identidade da página | DICO, título canônico, page ID, tipo/abrangência da entidade e item Wikidata quando disponível. Evita homônimos e distingue cidade, município, freguesia e região. | Essencial |
| Revisão e atribuição | ID/data da revisão, URL permanente, licença e referência ao bruto. Permite reconstruir e justificar cada texto. | Essencial |
| Introdução | Apresentação curta do local para futuras fichas; usar a introdução original, sem geração automática de resumo. | Alta |
| Artigo completo por seções | Todos os blocos e a hierarquia de títulos, incluindo temas que o filtro antigo não selecionava. Permite recortes posteriores sem nova perda de conteúdo. | Alta |
| Contexto temático | História, geografia, áreas verdes, património, cultura, eventos, gastronomia, educação, saúde e mobilidade, quando presentes. | Alta |
| Referências e ligações | Associar trechos/seções aos links e referências disponíveis; manter os sites oficiais como ligações separadas. | Alta |
| Ligações para outros idiomas | Identificar o artigo correspondente em inglês sem pesquisar novamente por nome. Não equivale a tradução nem garante que os artigos tenham o mesmo conteúdo. | Média |
| Imagem representativa | Nome/URL da imagem, descrição e crédito/licença por arquivo. Pode enriquecer as fichas futuras, com seleção de relevância e verificação de direitos. | Média / opcional |
| Dados estruturados Wikidata | Website, gentilício quando disponível, imagem, brasão, bandeira e relações administrativas, com qualificadores e referências. | Avaliação separada |
| Tabelas e infobox | Preservação estruturada das tabelas relevantes, contexto da entidade e unidades. Evitar converter toda tabela automaticamente em indicador oficial. | Posterior |

O índice da API permite conhecer a estrutura do artigo; a API de parsing
permite obter conteúdo vinculado a uma revisão. Isso sustenta a oportunidade
de extração completa por seções, em vez do primeiro bloco encontrado.
Fontes: [conteúdo de páginas](https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page)
e [parsing por revisão](https://www.mediawiki.org/wiki/API:Parsing_wikitext).

A propriedade `wikibase_item` fornece a ligação entre artigo e item Wikidata;
ligações entre idiomas também são disponibilizadas pela API. Esses
identificadores ajudam na validação, mas sua presença isolada não comprova
equivalência com um município CAOP.
Fontes: [Pageprops](https://www.mediawiki.org/wiki/API:Pageprops),
[ligação com Wikidata](https://www.mediawiki.org/wiki/API:Presenting_Wikidata_knowledge)
e [Langlinks](https://www.mediawiki.org/wiki/API:Langlinks).

Imagens exigem mais que uma URL: a API oferece imagem representativa e
metadados dos arquivos; a documentação do Commons orienta verificar as
condições de cada imagem. O texto do artigo e a imagem não devem receber uma
licença única presumida. Fontes:
[Pageimages](https://www.mediawiki.org/wiki/API:Pageimages),
[Imageinfo](https://www.mediawiki.org/wiki/API:Imageinfo) e
[reutilização no Commons](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia).

Wikidata permite obter declarações com qualificadores, referências e ranks.
Isso exige preservar datas e contexto, sem selecionar o primeiro valor como
atual. Seus dados estruturados são disponibilizados sob CC0; isso não se
estende automaticamente ao texto da Wikipedia nem a imagens. Fontes:
[acesso aos dados](https://www.wikidata.org/wiki/Wikidata:Data_access) e
[declarações](https://www.wikidata.org/wiki/Help:Statements).

## Pequena verificação real de disponibilidade

- A consulta agrupada retornou metadados para Lisboa, Cuba, Corvo, Gavião,
  Nazaré e Santa Cruz. Confirmou os IDs dos artigos, revisões, ligações para
  inglês e, quando existente, nome de imagem. Santa Cruz tem a propriedade
  de desambiguação. As ligações inglesas confirmam Cuba, Corvus, Hawk e
  Nazareth para os títulos ambíguos consultados.
- Lisboa: page ID `1165`, revisão `73385502`, datada de
  `2026-11-06T21:15:33Z`; **34 seções/subseções**, incluindo história,
  geografia, meio ambiente/áreas verdes, saúde, cultura, museus, eventos e
  património. Inclui também seções auxiliares de referências e links.
- O item associado a Lisboa é `Q597`. A resposta examinada, revisão
  `2571415836`, contém website, imagem, brasão, bandeira e outros campos.
  Existem valores históricos/depreciados em algumas propriedades; extrair
  apenas o primeiro seria incorreto. A descrição identifica cidade/capital;
  não foi auditada uma equivalência completa dessa entidade com a CAOP.
- Uma imagem representativa pode ser inadequada: o título `Cuba` retornou
  uma bandeira do país; Corvo/Gavião retornaram imagens de aves. Primeiro
  validar identidade e depois a relevância da imagem.

As consultas demonstram capacidade da API e disponibilidade nesses exemplos,
sem comprovar completude de conteúdo, imagens ou campos para 308 municípios.
Não é uma comparação de volume de texto na mesma revisão do legado: o
notebook não preservou a revisão histórica para fazer essa comparação.

Referências dos exemplos:
[Lisboa na revisão examinada](https://pt.wikipedia.org/w/index.php?oldid=73385502)
e [entidade Q597](https://www.wikidata.org/wiki/Q597).

## Recomendação para a especificação

Definir como núcleo: **identidade municipal validada + bruto preservado +
introdução + texto completo por seções + revisão/atribuição + relatório de
cobertura**. Os temas são recortes do conteúdo disponível, não campos cuja
presença se pode prometer em todos os municípios. Ausência de tema deve ser
distinta de falha de extração ou artigo incorreto.

Guardar o identificador Wikidata e ligações entre idiomas como metadados é
uma expansão limitada. Ingerir declarações Wikidata e imagens/atribuições
é uma expansão com contratos próprios, cuja inclusão ainda precisa de escolha.

Manter CAOP como referência territorial, INE/Pordata para estatísticas e
Open-Meteo para clima. Texto enciclopédico complementa a explicação dos
lugares; não deve virar prova de disponibilidade atual de serviços, horário
de transportes, custo de vida ou segurança, nem preencher indicadores ausentes.

Os TXT legados podem ser preservados como histórico identificado como não
validado. Sua importação não deve promovê-los automaticamente como versão
corrente nem inventar revisão/data de coleta. Permanecem por decidir o
backfill, os idiomas e o limite operacional da feature; a discussão anterior
de escopo continua aberta e a spec ainda não foi criada.
