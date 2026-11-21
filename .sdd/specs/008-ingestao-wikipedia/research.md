# Research — Wikipedia

Data: 2026-11-20. Pesquisa de planejamento, sem coleta nacional. A inspeção
do legado está no [relatório](../../../.docs/reports/wikipedia-legado-oportunidades-2026-11-20.md).

## R1 — Interface oficial e exceção ao robots

**Decisão:** Action API de leitura em `https://pt.wikipedia.org/w/api.php`;
apenas `query` e `parse`, com identificação, requisições seriais e limites.

**Justificativa:** a sondagem retornou HTTP 200 para metadados, direitos e
parsing de revisão. `robots.txt` retornou HTTP 200 com `Disallow: /w/` no
bloco geral. O autor respondeu explicitamente: “Autorizar uma exceção
específica para a API oficial de leitura”, com registro de risco, baixa taxa,
sem scraping de páginas e sem contorno de bloqueios. R-001 do plano registra
essa exceção, permitida pelo princípio IV; não é uma autorização ampla de crawl.

**Alternativas:** dumps oficiais seriam outra avaliação de origem, com
volume e operação próprios; não foram adotados. Não trocar silenciosamente
domínio, endpoint ou identidade de cliente para evitar restrição.

Fontes: [API e conduta](https://www.mediawiki.org/wiki/API:Etiquette),
[robots observado](https://pt.wikipedia.org/robots.txt).

## R2 — Revisão e metadados atuais são coisas diferentes

**Decisão:** consultar identidade/revisão atual com `query` e obter o corpo
com `parse&oldid=<revid>`. Validar igualdade de page ID e revisão nos dois
documentos. Preservar bytes das duas respostas e o instante da observação.

**Justificativa:** o HTML pode depender de predefinições/renderização;
o identificador da revisão não prova sozinho igualdade de bytes. Pageprops,
URL canônica e ligação inglesa observadas na consulta não são um snapshot
histórico de todas as dependências da revisão. O build usa os bytes já
preservados, não volta à rede. Cada nova verificação obtém também o parse,
mesmo quando a revisão não mudou, para perceber mudanças de renderização.

**Alternativas:** apenas introdução, buscar por nome ou comparar só revid
não atendem integridade, completude e identificação da spec.

Fonte: [Parsing wikitext](https://www.mediawiki.org/wiki/API:Parsing_wikitext).

## R3 — tocdata substitui sections na chamada atual

**Decisão:** requests novos usam
`prop=text|tocdata|revid|properties|links|externallinks`. O leitor aceita
também `sections` nas fixtures e snapshots compatíveis, sem requisitar o
parâmetro depreciado em produção.

**Justificativa:** a consulta real de planejamento avisou que `prop=sections`
foi depreciado. A repetição com `tocdata|revid|properties` retornou sem avisos:
`tocdata.sections` traz `tocLevel`, `hLevel`, `line`, `index`, `anchor` e
`fromTitle`. A revisão Lisboa `73385502`, page ID `1165`, tem 34 entradas.
O HTML observado usa wrappers `div.mw-heading` e também um `h2` de índice;
tratar todo h2 como seção real adicionaria conteúdo de navegação.

**Alternativas:** usar somente regex de h2 ou o formato antigo esconderia
mudanças de API. O adaptador deve normalizar os dois formatos explicitamente.

## R4 — Parser HTML

**Decisão:** acrescentar no execute `beautifulsoup4>=4.14,<5`, usando o parser
explícito `html.parser` do Python 3.12. Resolver a versão exata no `uv.lock`.
Nenhuma dependência/lock foi alterada durante este planejamento.

**Justificativa:** permite caminhar pela árvore e separar descendentes diretos
de tabelas/listas aninhadas; os originais permanecem intactos. O extrator
documenta suas regras e reprova texto substantivo sem representação. A escolha
explícita evita depender de lxml/html5lib instalados por acaso.

**Alternativas:** regex/`find_next` repetem o defeito do legado; escrever um
DOM completo com a biblioteca padrão acrescentaria complexidade. html5lib é
alternativa se HTML real demonstrar incompatibilidade; mudar parser exige
nova versão das regras e reexecução das regressões, não troca silenciosa.

Fonte: [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/bs4/doc/),
consultada por Context7. A documentação evolui; a versão instalada será a
resolvida pelo lock, não uma versão presumida a partir do título da página.

## R5 — Licença do conteúdo

**Decisão:** registrar `CC-BY-SA-4.0`, URL da licença, contribuidores,
artigo, histórico/revisão e indicação da normalização. Preservar avisos de
atribuição adicional presentes no conteúdo. Publicação continua fora do escopo.

**Justificativa:** `query&meta=siteinfo&siprop=rightsinfo` retornou
`Creative Commons Attribution-Share Alike 4.0` e
`https://creativecommons.org/licenses/by-sa/4.0/deed.pt`. Os termos tratam
atribuição por link e possíveis exigências adicionais de textos importados.
Isso não concede licença para imagens nem transforma GPL da API em licença
do artigo. Conferir esses registros novamente antes da coleta real.

**Alternativas:** herdar a licença CAOP/INE ou assumir licença única para
texto e mídia seria incorreto.

Fonte: [Termos Wikimedia, §7](https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content).

## R6 — Reuso do repositório sem alterar os contratos antigos

**Decisão:** reutilizar `LocalStorage`, `RateLimiter`, convenções de CLI,
target dbt `local` e promoção por caminhos; criar catálogo/manifest/estado
próprios da Wikipedia. A preparação segue Python → Parquet → dbt por tag.

**Justificativa:** o validador genérico de datasets exige `indicator` para
`api_json`, e o manifest v2 não expressa ausência editorial. O downloader
genérico não interpreta erro API em HTTP 200, `maxlag` ou `Retry-After` de
forma suficiente para esta fonte. Não modificar a semântica de sete features
para encaixar esses estados. Censos já demonstra snapshot completo e lock.

**Alternativas:** estender implicitamente o estado genérico poderia fazer
builds antigos interpretarem falhas/ausências como dados válidos.

## R7 — Verificação dos contratos

Cinco casos coletados pelo pytest; cinco falhas intencionais por
`NotImplementedError` nas três interfaces públicas, sem erro de importação
ou sintaxe. Baseline compartilhado: 63 passed/6,47 s antes e 63 passed/7,34 s
após os stubs; versão final dos contratos: cinco falhas esperadas em 0,18 s.
Ruff global e oito travas aprovados. O script de trava calcula hashes de Python mas não conta testes
nem detecta mecanismos de desabilitação nesse runtime; a contagem 5 e a
ausência de skip/xfail/parametrização devem ser auditadas também pelo pytest/AST.
