# Feature Specification: Visibilidade do modelo de dados — dicionário, diagrama ER, catálogo DuckDB único e dbt docs

**Slug**: `010-visibilidade-modelo-dados`

**Created**: 2026-11-22

**Status**: Convergida

**Input**: "tenho 1 preocupação sobre o projeto: não tenho visibilidade das tabelas, nem de seus relacionamentos" e, depois: "A e B são necessárias, podemos usar duckdb e também gostaria de poder visualizar no dbt". Situação levantada em 2026-11-22: 25 modelos dbt em 9 domínios (`analytics/dbt/models/`), 15 testes `relationships` espalhados em 9 `schema.yml`, descrições quase só em nível de tabela, nenhum diagrama nem dicionário em `.docs/`, e nenhum banco único: cada fonte é construída em um build dbt isolado, com promoção atômica para `lake/bronze` e `lake/silver`.

## Escopo

### Incluído

- **(A) Documento `.docs/modelo_de_dados.md`, gerado por comando**: diagrama ER (Mermaid) com as tabelas e os relacionamentos declarados, e dicionário de dados por tabela (camada, domínio, descrição, colunas com tipo, descrição e testes, fonte do catálogo quando declarada). Lê os `schema.yml` do dbt; fica versionado no Git; o CI reprova se o arquivo commitado divergir do que o comando geraria.
- **Lista de lacunas no próprio documento**: tabelas e colunas sem descrição, com o percentual de cobertura, e tabelas com chave territorial (`dico`, `dicofre`) sem relacionamento declarado.
- **(B) Catálogo DuckDB único**: um arquivo local, gerado por comando, que expõe como objetos consultáveis todas as tabelas de `lake/bronze` e `lake/silver`, mais um **inventário do `raw/`** (fonte, `run_id`, data da coleta, checksum, licença e estado, lidos dos manifests) e uma tabela de metadados com as descrições e os relacionamentos. Abre no DuckDB UI e no DBeaver.
- **(C) Visualização no dbt**: um comando gera e abre localmente o site do `dbt docs` (catálogo navegável e grafo de dependências), com o grafo ligando as camadas silver e bronze **entre os builds isolados por fonte**.
- **Descrições das tabelas principais**: preencher descrição de tabela e de coluna nos `schema.yml` das tabelas que **não** são relatórios de cobertura (dimensões, staging e marts). O documento mostra a cobertura do restante.
- **Runbook**: seção em `.docs/runbooks/` com os comandos e o passo a passo para abrir o catálogo no DuckDB UI e no DBeaver e o site do dbt.

### Fora de Escopo

- **Gate que reprova modelo novo sem descrição** (decisão do autor, 2026-11-22: mostrar a cobertura e preencher só as principais). Pode virar spec própria depois.
- **Descrições dos relatórios de cobertura** (`rpt_*_coverage`, `*_coverage`): ficam como "sem descrição" no documento até uma spec futura.
- **Publicar o site do dbt** (GitHub Pages, S3) ou anexá-lo ao CI como artefato: o site é local, não é publicado e não faz parte do produto.
- **Servidor, serviço ou API dinâmica**: nenhuma infraestrutura nova, nenhum recurso AWS (constitution II e VII).
- **Alterar dados, modelos, builds, `raw/` ou `lake/`**: a feature só lê. Nenhuma regra de negócio ou transformação muda.
- **Criar relacionamentos novos** entre tabelas ou novos testes dbt: o diagrama mostra o que já está declarado; o que falta aparece como lacuna, e declará-lo é decisão futura.
- **Dados da camada Gold, marts da Fase 3 e `criteria_catalog`**: entram no documento quando existirem, sem trabalho desta feature.
- **Valores dos dados no documento versionado** (contagens de linhas, amostras, exemplos): só estrutura. Contagens ficam no catálogo local.
- **Ferramentas de BI, dashboards e consulta por interface própria do projeto.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver as tabelas e os relacionamentos em um documento (Priority: P1)

O autor roda um comando e obtém `.docs/modelo_de_dados.md` com o diagrama ER e o dicionário de dados de todas as tabelas, sem abrir código nem rodar nenhum build. Ao ler, ele responde "com quais tabelas a tabela X se liga, por quais colunas, e o que cada coluna significa".

**Why this priority**: é o que responde diretamente à preocupação ("não tenho visibilidade das tabelas, nem de seus relacionamentos") e não depende do lake, de dados reais nem de chave. As outras duas visões partem dos mesmos metadados.

**Independent Test**: sem lake real, só com os `schema.yml` e os fixtures que o CI já usa, rodar o comando, abrir o Markdown e conferir que cada modelo aparece com camada, domínio e colunas, que cada teste `relationships` aparece como uma aresta do diagrama, e que rodar de novo gera um arquivo idêntico byte a byte.

**Acceptance Scenarios**:

1. **Given** os 25 modelos dbt existentes, **When** o autor roda o comando de geração, **Then** o documento lista **todos** os modelos, cada um com camada (bronze ou silver), domínio, descrição (ou "sem descrição"), e colunas com tipo, descrição (ou "sem descrição") e testes declarados.
2. **Given** os testes `relationships` declarados nos `schema.yml`, **When** o documento é gerado, **Then** o diagrama ER tem uma aresta para cada um deles, ligando tabela e coluna de origem à tabela e coluna de destino, inclusive quando o destino é uma tabela de outro domínio ou de outro build (por exemplo, `dim_municipality`).
3. **Given** uma tabela com coluna `dico` ou `dicofre` e sem relacionamento declarado, **When** o documento é gerado, **Then** ela aparece na seção de lacunas como "chave territorial sem relacionamento declarado", com o nome da tabela e da coluna.
4. **Given** o documento já commitado e um `schema.yml` alterado (coluna nova ou descrição editada), **When** o CI roda a verificação, **Then** ela falha e diz qual comando regenera o arquivo; **Given** o documento regenerado e commitado, **Then** a verificação passa.
5. **Given** que o comando é executado duas vezes sem mudança nos `schema.yml`, **When** os dois resultados são comparados, **Then** são idênticos byte a byte (ordem estável, sem data nem caminho local no texto).
6. **Given** uma máquina sem `lake/`, **When** o comando é executado, **Then** o documento é gerado normalmente.

---

### User Story 2 - Navegar e consultar as tabelas reais em um DuckDB único (Priority: P2)

O autor roda um comando que gera um arquivo DuckDB e o abre no DuckDB UI ou no DBeaver. Ali ele vê todas as tabelas de bronze e silver, consulta qualquer uma com SQL, faz `JOIN` entre fontes diferentes e confere de qual coleta cada tabela veio.

**Why this priority**: é a visibilidade sobre os dados reais (linhas, valores, cobertura), que o documento versionado não traz por regra. Vem depois da US1 porque a pergunta "como as tabelas se ligam" é respondida primeiro pelo documento.

**Independent Test**: com o `lake/` real ou de fixture, gerar o catálogo, abri-lo em um cliente SQL e conferir que cada tabela de bronze e silver existe, que `SELECT count(*)` bate com o número de linhas do parquet correspondente e que uma consulta unindo duas fontes (por exemplo, `dim_municipality` com `stg_municipality_pole_distance`) funciona.

**Acceptance Scenarios**:

1. **Given** o `lake/` com tabelas em bronze e silver, **When** o autor gera o catálogo, **Then** existe **um** arquivo DuckDB em que cada tabela do lake aparece como objeto consultável, com nome que identifica camada e tabela, e a contagem de linhas de cada uma é igual à do parquet de origem.
2. **Given** o catálogo gerado, **When** o autor consulta duas tabelas de fontes diferentes unidas por `dico`, **Then** a consulta roda sem outra configuração.
3. **Given** o `raw/` com coletas registradas, **When** o catálogo é gerado, **Then** há um inventário consultável com, por coleta, fonte, `run_id`, data, checksum, licença e estado, lidos dos manifests, que permite ligar cada tabela à sua fonte.
4. **Given** o catálogo gerado, **When** o autor consulta a tabela de metadados, **Then** encontra, por tabela e coluna, a descrição e o relacionamento declarado, os mesmos do documento da US1.
5. **Given** que uma fonte ainda não foi construída (sem tabela no lake), **When** o catálogo é gerado, **Then** a geração termina com sucesso e informa essa tabela como "não construída", em vez de falhar.
6. **Given** um parquet no lake que não corresponde a nenhum modelo dbt (por exemplo, um relatório auxiliar), **When** o catálogo é gerado, **Then** ele é exposto e marcado como "sem modelo dbt".
7. **Given** o catálogo aberto, **When** o autor tenta gravar nas tabelas do lake, **Then** não consegue, e `raw/` e `lake/` ficam idênticos aos de antes da geração.

---

### User Story 3 - Descrições nas tabelas principais (Priority: P2)

As tabelas que não são relatórios de cobertura passam a ter descrição em cada tabela e em cada coluna, para que o dicionário (US1) e o catálogo (US2) expliquem o dado, e não só listem nomes.

**Why this priority**: sem descrições o documento mostra a estrutura, mas não o significado. Entra como P2 porque a US1 já entrega valor com "sem descrição" explícito, e o preenchimento é trabalho de conteúdo que pode andar em paralelo.

**Independent Test**: rodar a geração do documento e conferir que nenhuma tabela principal, nem coluna dela, aparece como "sem descrição", e que o percentual de cobertura informado bate com a contagem manual de uma amostra.

**Acceptance Scenarios**:

1. **Given** as tabelas que não são relatórios de cobertura, **When** o documento é gerado, **Then** todas elas, e todas as suas colunas, têm descrição.
2. **Given** os relatórios de cobertura e qualquer outra tabela sem descrição, **When** o documento é gerado, **Then** elas aparecem como "sem descrição", e a seção de lacunas informa a cobertura por camada e total.
3. **Given** as descrições escritas, **When** o autor as lê, **Then** cada uma diz o que o campo representa, e a unidade ou a convenção quando houver (por exemplo, km, minutos, estado `ok`/`sem_rota`/`falha`/`pendente`), sem repetir só o nome da coluna.

---

### User Story 4 - Ver o grafo e o catálogo no dbt (Priority: P3)

O autor roda um comando e abre no navegador o site do `dbt docs`: catálogo de modelos e colunas e o grafo de dependências, inclusive entre os builds isolados por fonte.

**Why this priority**: entrega a visão de linhagem (de onde cada tabela vem), mas parte dos mesmos metadados das US1 e US2 e é a mais trabalhosa por causa dos builds isolados. O valor principal já está nas duas primeiras.

**Independent Test**: gerar o site e conferir que todos os modelos aparecem no catálogo com descrição e colunas, e que o grafo de uma tabela silver (por exemplo, `dim_municipality`) mostra os modelos de outros domínios que dependem dela.

**Acceptance Scenarios**:

1. **Given** os modelos dos 9 domínios, **When** o autor gera o site, **Then** todos os modelos aparecem no catálogo com descrição de tabela e de coluna (ou "sem descrição").
2. **Given** um modelo que depende de uma tabela silver de outro build, **When** o autor abre o grafo, **Then** a dependência aparece como aresta (por exemplo, `stg_municipality_pole_distance` ligada a `dim_municipality`).
3. **Given** o comando executado, **When** termina, **Then** `lake/`, `raw/` e os builds promovidos continuam idênticos, e o site fica numa pasta ignorada pelo Git.
4. **Given** um domínio cuja fonte ainda não foi construída, **When** o site é gerado, **Then** a geração termina com sucesso e o modelo aparece no grafo sem dados.

---

### Edge Cases

- **Modelo sem entrada no `schema.yml`**: aparece no documento como "sem descrição", sem colunas declaradas, e entra na seção de lacunas.
- **Relacionamento cujo destino é uma fonte externa ao build** (tabela silver lida de outro build): a aresta é desenhada normalmente, e o destino aparece marcado com a camada e o domínio dele.
- **Relacionamento que aponta para uma tabela inexistente** (erro de digitação no `schema.yml`): a geração falha com mensagem que nomeia o arquivo, o modelo e o destino, em vez de produzir um diagrama enganoso.
- **Lake parcialmente construído** (só algumas fontes): o catálogo expõe as que existem e lista as demais como "não construída".
- **Build em andamento ou promoção atômica no meio da geração do catálogo**: o catálogo reflete uma versão completa de cada tabela, nunca uma versão pela metade.
- **Nomes iguais em camadas diferentes**: os objetos do catálogo sempre levam a camada no nome.
- **Tabelas grandes** (blocos da Wikipedia, observações): gerar o catálogo não copia nem carrega os dados, e o arquivo continua pequeno.
- **Execução repetida**: gerar o documento, o catálogo ou o site de novo substitui o resultado anterior sem acumular lixo.
- **Segredo ou dado pessoal**: o documento versionado não contém valores de dados; nem o documento nem o catálogo expõem chave de API, e coordenadas exatas de anúncios do Idealista não vão para o Git (constitution I e VI).
- **Mudança de nome ou remoção de tabela**: a tabela some do documento na próxima geração, e a verificação do CI cobra a regeneração.

## Requirements *(mandatory)*

### Functional Requirements

**Documento (A)**

- **FR-001**: O sistema DEVE gerar `.docs/modelo_de_dados.md` por um único comando, a partir dos `schema.yml` do dbt, listando **todos** os modelos com camada, domínio, descrição, e colunas com tipo, descrição e testes declarados.
- **FR-002**: O documento DEVE conter um diagrama ER com uma aresta para **cada** teste `relationships` declarado, indicando tabela e coluna de origem e de destino, inclusive quando o destino pertence a outro domínio ou a outro build.
- **FR-003**: O documento DEVE ter uma seção de lacunas com: modelos e colunas sem descrição, a cobertura de descrição por camada e total, e as tabelas com coluna `dico` ou `dicofre` sem relacionamento declarado.
- **FR-004**: O documento DEVE indicar, por tabela, a fonte do catálogo (`source_id` de `config/sources.yml`) e a licença quando elas forem declaradas ou derivadas dos metadados, e "não declarada" quando não forem.
- **FR-005**: A geração DEVE ser determinística: com os mesmos `schema.yml`, duas execuções produzem arquivos idênticos byte a byte, sem data, caminho local nem ordem instável.
- **FR-006**: O documento versionado NÃO DEVE conter valores de dados (contagens de linhas, amostras, exemplos), só estrutura e metadados.
- **FR-007**: A geração do documento DEVE funcionar sem `lake/` nem `raw/` reais, com os mesmos insumos que o CI já tem.
- **FR-008**: O CI DEVE reprovar quando `.docs/modelo_de_dados.md` divergir do que o comando geraria e DEVE indicar o comando que o regenera.
- **FR-009**: A geração DEVE falhar com mensagem que nomeia o arquivo, o modelo e o destino quando um relacionamento apontar para uma tabela que não existe.

**Catálogo DuckDB (B)**

- **FR-010**: O sistema DEVE gerar, por um único comando, **um** arquivo DuckDB local que expõe cada tabela de `lake/bronze` e `lake/silver` como objeto consultável, com nome que identifica camada e tabela, e contagem de linhas igual à do dado de origem.
- **FR-011**: O catálogo DEVE incluir um inventário consultável do `raw/`, com, por coleta, fonte, `run_id`, data, checksum, licença e estado, lidos dos manifests.
- **FR-012**: O catálogo DEVE incluir uma tabela de metadados com, por tabela e coluna, descrição, tipo e relacionamento declarado, coerentes com o documento da US1.
- **FR-013**: O catálogo NÃO DEVE duplicar os dados do lake e DEVE refletir o estado atual de cada tabela, sem cópia manual depois de um build.
- **FR-014**: O catálogo DEVE ser somente leitura em relação ao lake: gerar ou abrir o catálogo NÃO DEVE alterar `raw/`, `lake/` nem os manifests.
- **FR-015**: A geração DEVE terminar com sucesso quando faltarem tabelas (fonte ainda não construída), informando-as como "não construída", e DEVE marcar como "sem modelo dbt" qualquer tabela do lake que não corresponda a um modelo.
- **FR-016**: O catálogo DEVE ficar fora do Git e ser regenerável a qualquer momento, substituindo o anterior.

**Descrições (US3)**

- **FR-017**: Todas as tabelas que não são relatórios de cobertura DEVEM ter descrição de tabela e descrição de cada coluna nos `schema.yml`, informando o significado e a unidade ou convenção quando houver.
- **FR-018**: O sistema NÃO DEVE inventar descrição: onde faltar, o documento e o site mostram "sem descrição" explicitamente (constitution III).

**Visualização no dbt (C)**

- **FR-019**: O sistema DEVE gerar, por um único comando, o site do `dbt docs` com catálogo e grafo de dependências cobrindo os modelos dos 9 domínios em uma só visão.
- **FR-020**: O grafo DEVE mostrar as dependências entre tabelas silver e modelos de outros builds isolados (por exemplo, a ligação de `stg_municipality_pole_distance` com `dim_municipality`).
- **FR-021**: A geração do site NÃO DEVE alterar, reconstruir nem promover nada em `lake/` ou `raw/` e DEVE funcionar com o lake parcialmente construído.
- **FR-022**: O site gerado DEVE ficar em pasta ignorada pelo Git e NÃO DEVE ser publicado.

**Transversais**

- **FR-023**: Nenhum artefato gerado (documento, catálogo, site) DEVE conter chave de API, segredo ou dado pessoal de terceiros (constitution I e VI); o CI de segredos DEVE continuar passando.
- **FR-024**: Os três comandos DEVEM estar documentados em `.docs/runbooks/`, incluindo como abrir o catálogo no DuckDB UI e no DBeaver e como abrir o site do dbt.
- **FR-025**: A feature NÃO DEVE introduzir servidor, serviço ou recurso com custo recorrente.

### Key Entities

- **Modelo de dados documentado**: cada tabela do projeto, com camada (bronze ou silver), domínio, descrição, colunas e fonte de origem.
- **Coluna**: nome, tipo, descrição, testes declarados e, quando houver, o relacionamento que parte dela.
- **Relacionamento declarado**: ligação entre uma coluna de uma tabela e uma coluna de outra, vinda de um teste `relationships` do dbt. É a única origem de arestas do diagrama.
- **Lacuna**: o que falta ao modelo documentado: descrição ausente, ou chave territorial sem relacionamento declarado.
- **Catálogo DuckDB**: arquivo local único que expõe as tabelas do lake, o inventário do `raw/` e os metadados.
- **Inventário do `raw/`**: uma linha por coleta, com fonte, `run_id`, data, checksum, licença e estado.
- **Site do dbt docs**: catálogo e grafo de dependências navegáveis, gerados localmente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: O documento lista 100% dos modelos existentes (25 hoje), cada um com camada, domínio e colunas, e o diagrama tem exatamente tantas arestas quantos são os testes `relationships` declarados.
- **SC-002**: Para uma amostra de 5 tabelas escolhidas pelo autor, ele responde só com o documento "com quais tabelas se liga, por quais colunas e o que cada coluna significa", e as respostas conferem com os `schema.yml`.
- **SC-003**: Duas gerações seguidas do documento produzem arquivos idênticos, e uma alteração em um `schema.yml` sem regenerar o documento faz o CI falhar.
- **SC-004**: O catálogo expõe 100% das tabelas existentes de bronze e silver (25 hoje), e para cada uma a contagem de linhas bate com a do dado de origem.
- **SC-005**: O arquivo do catálogo é pequeno em relação ao lake (menos de 5 MB, contra cerca de 150 MB de dados no lake), e gerar o catálogo não altera nenhum arquivo de `raw/` nem de `lake/`.
- **SC-006**: O site do dbt lista 100% dos modelos e mostra a dependência entre tabelas de builds diferentes em pelo menos um caso verificado (`stg_municipality_pole_distance` e `dim_municipality`).
- **SC-007**: 100% das tabelas que não são relatórios de cobertura, e das suas colunas, têm descrição, e o documento informa a cobertura do restante.
- **SC-008**: Nenhum artefato versionado contém valor de dado ou segredo, e o CI de segredos continua passando.
- **SC-009**: O autor gera os três artefatos (documento, catálogo e site) com um comando cada, seguindo só o runbook, em uma máquina com o lake já construído.

## Assumptions

- **Usuário-alvo**: o autor do projeto, em máquina local e com o `lake/` já construído para as visões B e C. Não há usuário final nem interface do produto envolvida.
- **Relacionamentos**: a única fonte de arestas do diagrama é o que já está declarado nos `schema.yml` (testes `relationships`). O que não está declarado aparece na lista de lacunas, e declará-lo é decisão futura (decisão do autor, 2026-11-22, de mostrar sem criar novos).
- **Tipos das colunas**: o documento versionado traz o tipo quando ele puder ser obtido sem o lake real (por exemplo, de um build de fixture, como o CI já faz); caso contrário mostra "n/d". Os tipos reais completos ficam no catálogo local. A escolha técnica é do `sdd-plan`.
- **Tabelas principais** (US3): todas as que não são relatórios de cobertura (`rpt_*_coverage`, `*_coverage`). Os relatórios ficam como "sem descrição" e entram na cobertura.
- **Camadas**: "bronze" e "silver" são as pastas atuais do `lake/`; o `raw/` é arquivo de fonte (zip, csv, json) e não tabela, por isso aparece como inventário.
- **Sem custo, sem infraestrutura**: tudo roda localmente com as ferramentas já presentes (dbt, DuckDB); a constitution VII e o ADR-002 não são afetados.
- **Segredos e dados pessoais**: o catálogo é local (`.data/` está no `.gitignore`) e pode conter tudo o que o lake contém, mas nunca vai para o Git; o documento versionado só tem estrutura.
- **Documentos relacionados** a manter coerentes: `.docs/arquitetura.html`, `.docs/fontes_de_dados.md` e o README (link para o novo documento).

## Clarifications

### Sessão 2026-11-22

- Q: O catálogo DuckDB (B) deve cobrir quais camadas do lake? → A: Bronze, silver e um inventário do `raw/` (fonte, `run_id`, checksum, licença, estado, lido dos manifests), para ligar cada tabela à sua origem.
- Q: Como manter `modelo_de_dados.md` (A) atualizado? → A: Comando manual para gerar, arquivo versionado no Git e o CI reprova se divergir do que o comando geraria. Contagens de linhas reais ficam só no catálogo local (B).
- Q: Como o autor quer ver o dbt (C)? → A: Site local do `dbt docs` com o grafo ligando as fontes entre os builds isolados. Não é publicado, não entra no produto e não é artefato do CI.
- Q: O que fazer com as descrições de coluna que faltam? → A: Mostrar a cobertura e preencher só as tabelas principais (que não são relatórios de cobertura). Sem gate de CI para modelos novos nesta feature.
- Decisão registrada na entrevista: o diagrama usa só relacionamentos já declarados; chaves territoriais sem relacionamento aparecem como lacuna, sem criar testes novos.
