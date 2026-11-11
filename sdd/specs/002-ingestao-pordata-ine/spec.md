# Feature Specification: Ingestão Pordata e INE — coleta rastreável e staging por município

**Slug**: `002-ingestao-pordata-ine`

**Created**: 2026-11-11

**Status**: Convergida

**Input**: "ingestao pordata e Ine — referência: .docs/" (ver `.docs/fontes_de_dados.md` §2.2, §3.3 e §5, e `.docs/plano_plataforma_recomendacao_portugal.md` §5.4, §8 e Fase 2)

## Escopo

### Incluído

- **Catálogo de fontes**: entradas `pordata` e `ine` em `config/sources.yml`, com publicador, licença, método, frequência, nível territorial e a lista declarada de datasets (Pordata) e de indicadores (INE). Um dataset novo entra por mudança de catálogo, não de código.
- **Coleta do Pordata**: 16 datasets CSV baixados por HTTP e 1 planilha carregada manualmente (os usados pelos critérios do plano), guardados exatamente como vieram da fonte, com rastreabilidade por dataset:
  - 16 CSV: população residente por sexo e idade (1), densidade populacional (4), agências bancárias (295), população estrangeira residente (354), ensino superior (375), ensino não superior (379), desemprego registado (439), farmácias (464), hospitais (470), crimes registados (559), crimes por categoria (560), ganho médio mensal (581), recintos de cinema (623), sessões de espetáculos ao vivo (631), edifícios concluídos (978) e fogos concluídos (980);
  - 1 planilha, por **carga manual**: poder de compra per capita por município. O Pordata só a oferece por um botão que exige navegador (a URL da planilha antiga deixou de existir), então o operador a exporta à mão e a entrega ao sistema, que a guarda como bruto rastreável.
- **Coleta do INE**: três conjuntos de indicadores por município, obtidos pela **API de indicadores do INE** (não pelos links de exportação do site): rendas da habitação ao nível local (mediana de novos contratos), taxa de criminalidade (total e todas as categorias de crime) e poder de compra per capita. O poder de compra vem **também** pela carga manual do Pordata, porque a cobertura do INE ainda não foi comprovada na prática; os dois entram como datasets distintos.
- **Staging por dataset** em formato longo, com o município resolvido para o código oficial `dico` por uma tabela de sinônimos de município. Município sem correspondência reprova o staging.
- **Relatório de cobertura por dataset**: quantos dos 308 municípios têm valor e quais não têm.
- **Execução** local e em S3 simulado, com o mesmo layout de chaves da spec 001; testes sem rede, com fixtures gravadas.

### Fora de Escopo

- **Freguesia**: rendas do INE por freguesia, sinônimos de freguesia e a tabela de correspondência 2013→2025. Entram quando essa tabela existir.
- **Camadas posteriores**: Silver de indicadores, Gold, `criteria_catalog`, ranker e publicação (`published/vN`). Esta spec termina no staging.
- **Datasets sem uso nos critérios**: Pordata 294 (depósitos), 445 e 447 (emprego por escolaridade), 582 (ganho por escolaridade) e a planilha de proporção do poder de compra.
- **Pordata 845** (emprego por setor): foi baixado à mão e não tem URL conhecida. Entra depois, como mudança de catálogo, quando a URL for confirmada.
- **Outros indicadores do INE** além de rendas e criminalidade.
- **Descoberta automática de links** do Pordata (processo L2 do legado). Datasets novos entram por mudança no catálogo.
- **Pivot para base larga** do legado (`PorDataProcess.py`), correções heurísticas de valores (como multiplicar preços por 1.000) e imputação de qualquer tipo.
- **Deploy e agendamento**: Lambda, ECS, Terraform, MWAA e execução mensal automática.
- **Outras fontes**: Open-Meteo, WWO, Wikipedia, Censos, AIMA, SNS, Idealista e distâncias.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coletar os datasets do Pordata com rastreabilidade (Priority: P1)

O operador (o autor do projeto) roda um comando que baixa os 16 datasets do Pordata disponíveis por HTTP e declarados no catálogo e os guarda como dado bruto imutável, com um manifest que registra, por dataset, de onde veio, quando foi coletado, a licença, o checksum e o resultado. Se um dataset falha (URL morta, HTML no lugar do CSV, colunas esperadas ausentes), os demais continuam sendo coletados e a falha fica registrada com o motivo.

**Why this priority**: o Pordata alimenta a maior parte dos critérios do ranking (cultura, economia, emprego, educação, população, comunidade estrangeira, saúde e segurança). Sem o bruto rastreável não há staging. As URLs do Pordata são internas do site e podem mudar sem aviso, então a tolerância a falha por dataset é o que impede que uma URL quebrada trave toda a atualização. Esta story também prova o padrão do segundo coletor.

**Independent Test**: com um servidor simulado, rodar o comando num destino local vazio e conferir os 16 arquivos e o manifest. Rodar de novo e conferir que tudo é `unchanged`, sem arquivos novos. Fazer um dataset falhar e conferir que os outros 15 foram gravados.

**Acceptance Scenarios**:

1. **Given** um destino vazio, **When** o operador executa a coleta do Pordata, **Then** os 16 datasets ficam gravados, separados por fonte, execução e dataset, e o manifest lista para cada um: identificador, origem, `sha256`, tamanho, licença, horário da coleta e status `changed`.
2. **Given** uma coleta anterior bem-sucedida e nenhum dataset alterado, **When** o operador coleta de novo, **Then** cada dataset é registrado como `unchanged` e nenhum arquivo bruto novo é gravado.
3. **Given** uma coleta anterior em que apenas um dataset mudou, **When** o operador coleta de novo, **Then** só o arquivo desse dataset é gravado como novo; os demais são `unchanged`.
4. **Given** um dataset cuja URL devolve HTML, ou cujo CSV perdeu uma coluna esperada, **When** a coleta roda, **Then** esse dataset é registrado como `failed` com o motivo, nenhum arquivo parcial dele fica no bruto, os outros datasets são gravados e o comando termina com código de erro.
5. **Given** um dataset que falhou numa execução, **When** a seguinte tem sucesso, **Then** a falha anterior não impede o novo estado de ser aceito como o mais recente do dataset.

---

### User Story 2 - Coletar rendas e criminalidade do INE (Priority: P2)

O operador roda um comando que consulta a API de indicadores do INE para os três conjuntos declarados no catálogo (rendas da habitação ao nível local, taxa de criminalidade e poder de compra per capita) e guarda cada resposta como veio, com o mesmo manifest e as mesmas regras de idempotência e de falha do Pordata.

**Why this priority**: as rendas do INE são a referência oficial de aluguel para os 308 municípios e sustentam o critério de custo mesmo quando o Idealista não tem amostra. Fica abaixo do Pordata porque o método (API) é diferente e só depende do padrão que a US1 estabelece.

**Independent Test**: com respostas gravadas da API do INE, rodar o comando e conferir o bruto e o manifest. Repetir e conferir `unchanged`. Simular a API indisponível e conferir o `failed` sem arquivo parcial.

**Acceptance Scenarios**:

1. **Given** um destino vazio, **When** o operador executa a coleta do INE, **Then** as respostas dos três conjuntos ficam gravadas como vieram, e o manifest registra para cada um o código do indicador, o período de referência informado pela fonte, a licença, o `sha256` e o status.
2. **Given** respostas idênticas às da coleta anterior, **When** a coleta roda de novo, **Then** os indicadores são `unchanged` e nada novo é gravado.
3. **Given** a API do INE indisponível, com erro ou com resposta vazia para um indicador, **When** a coleta roda, **Then** esse indicador é `failed` com o motivo, não deixa arquivo parcial, o outro indicador é tratado normalmente e o comando termina com código de erro.
4. **Given** um indicador que o INE não publica para um município (por exemplo, dado suprimido por sigilo estatístico), **When** a resposta é guardada, **Then** o bruto preserva a ausência como a fonte a representa.

---

### User Story 3 - Staging por município com o código oficial (Priority: P2)

A partir do último estado válido de cada dataset, o operador executa a transformação e obtém, para cada dataset do Pordata e do INE, uma tabela em formato longo em que cada linha é uma observação de um município (código `dico`), de um indicador, de um período, com valor, unidade e proveniência. O nome do município da fonte é resolvido para o código oficial pela tabela de sinônimos. Se algum município não tiver correspondência, o staging do dataset é interrompido e lista os nomes.

**Why this priority**: a junção entre fontes pelo código oficial é o princípio III da constitution. O bruto sozinho não prova que os 308 municípios se ligam à CAOP. Depende da US1 e da US2 só pela existência do bruto.

**Independent Test**: com brutos de fixture e a dimensão de municípios da spec 001, rodar a transformação e conferir que todo `dico` existe na dimensão, que não há linhas duplicadas e que um nome sem correspondência interrompe a execução.

**Acceptance Scenarios**:

1. **Given** o último estado válido de um dataset do Pordata, **When** a transformação roda, **Then** a saída traz uma linha por município, indicador, dimensões do dataset e período, com `dico`, valor, unidade, símbolo da fonte (quando houver) e proveniência (fonte, execução, licença).
2. **Given** um nome de município que a tabela de sinônimos não resolve, **When** a transformação roda, **Then** ela falha, informa o dataset e lista os nomes sem correspondência, e nenhuma linha é descartada em silêncio.
3. **Given** homônimos (como "Lagoa", que existe em Faro e em São Miguel), **When** a transformação resolve os nomes, **Then** cada ocorrência recebe o código correto por uma regra explícita da tabela de sinônimos, nunca por escolha arbitrária.
4. **Given** linhas de agregação na fonte (Portugal, regiões, distritos, NUTS), **When** a transformação roda, **Then** elas não entram como município; o relatório de cobertura registra quantas foram excluídas.
5. **Given** um valor ausente, suprimido ou marcado com símbolo pela fonte, **When** a transformação roda, **Then** ele permanece ausente, com o símbolo preservado, e nunca vira zero nem é estimado.
6. **Given** a coluna de ano ou período do CSV do Pordata, **When** a transformação roda, **Then** o período sai como o valor correto (por exemplo, 2024), sem formatação de locale como "2.024,00".

---

### User Story 4 - Relatório de cobertura por dataset (Priority: P3)

Ao fim da transformação, o operador recebe, para cada dataset, um relatório que diz quantos dos 308 municípios têm valor no período mais recente e quais não têm.

**Why this priority**: torna a ausência visível desde o staging (constitution III), em vez de aparecer só quando os indicadores forem montados. Não bloqueia a coleta nem o staging.

**Independent Test**: com fixtures em que alguns municípios não têm valor, rodar a transformação e conferir as contagens e a lista de ausentes.

**Acceptance Scenarios**:

1. **Given** um dataset com valor para 290 dos 308 municípios no período mais recente, **When** o relatório é gerado, **Then** ele informa 290 com valor, 18 sem valor e a lista desses 18 códigos e nomes.
2. **Given** um dataset sem nenhum município em um período recente, **When** o relatório é gerado, **Then** ele informa cobertura zero para o período mais recente e o último período com dados.
3. **Given** a execução concluída, **When** o operador consulta o relatório, **Then** a cobertura de cada dataset está num formato legível por pessoa e preservada junto da saída.

---

### User Story 5 - Carregar a planilha do Pordata à mão (Priority: P3)

O operador exporta do site do Pordata a planilha de poder de compra per capita por município e a entrega ao sistema por um comando. O sistema valida o arquivo, guarda-o como bruto rastreável e o trata no staging como os demais datasets, ao lado do indicador equivalente do INE.

**Why this priority**: o Pordata só oferece essa tabela por um botão que exige navegador, e a cobertura do indicador do INE ainda não foi comprovada na prática. A carga manual mantém as duas fontes disponíveis para comparação. Depende do padrão da US1 e é a menos urgente, porque o INE já cobre os 308 municípios.

**Independent Test**: com uma planilha sintética no layout do Pordata, rodar o comando e conferir o bruto e o manifest. Entregar a mesma planilha de novo e conferir `unchanged`. Entregar uma planilha com a aba ou o cabeçalho errado e conferir `failed` sem bruto.

**Acceptance Scenarios**:

1. **Given** uma planilha exportada do Pordata no layout esperado, **When** o operador a entrega ao sistema, **Then** ela é guardada como bruto imutável e o manifest registra o dataset com `sha256`, tamanho, licença, horário e status `changed`.
2. **Given** a mesma planilha entregue de novo, **When** o comando roda, **Then** o dataset é `unchanged` e nenhum arquivo novo é gravado.
3. **Given** um arquivo que não é a planilha esperada (aba ausente, cabeçalho de anos ausente ou menos de 308 municípios), **When** o operador o entrega, **Then** o dataset é `failed` com o motivo, nada é gravado no bruto e o comando termina com código de erro.
4. **Given** a planilha guardada, **When** o staging roda, **Then** cada município vira uma linha por ano com o `dico` resolvido, e as linhas de agregação territorial (Portugal, NUTS) são excluídas e contadas.

---

### Edge Cases

- **URL do Pordata mudou ou devolveu HTML:** o dataset fica `failed` com mensagem explícita; os outros seguem. A planilha de poder de compra do Pordata já passou por isso: a URL com a data da edição deixou de existir, e por isso ela é carregada manualmente.
- **Estrutura do dataset mudou** (coluna renomeada, removida ou nova): a validação das colunas esperadas reprova o dataset antes de ele ser aceito como novo estado.
- **Arquivo vazio, truncado ou com codificação inesperada:** reprovado na validação, sem arquivo parcial no bruto.
- **Mudança de um único dataset:** só ele gera arquivo novo; o estado vigente de cada dataset é independente dos demais.
- **Execução concorrente:** cada execução grava num prefixo próprio e não corrompe outra; o `unchanged` compara com o último estado válido do dataset.
- **Município com nome diferente entre Pordata e INE, ou com grafia sem acento:** resolvido pela tabela de sinônimos; a regra de normalização de nomes é a única da spec 001.
- **Município de uma série histórica que não existe na CAOP vigente:** não é descartado em silêncio; o staging do dataset reprova e lista o nome.
- **Valor suprimido por sigilo estatístico (por exemplo, "x" no INE):** permanece ausente, nunca zero.
- **Ilhas e municípios pequenos sem dado:** aparecem como ausentes no relatório de cobertura; nenhum valor regional é copiado para eles.
- **Limite de taxa do INE ou do Pordata:** a coleta espera e tenta de novo com espera crescente; esgotadas as tentativas, o dataset ou indicador fica `failed`.
- **Diretório local inexistente:** é criado automaticamente. Um bruto já existente nunca é sobrescrito.

## Requirements *(mandatory)*

### Functional Requirements

**Catálogo e coleta**

- **FR-001**: O sistema DEVE registrar `pordata` e `ine` no catálogo de fontes (`config/sources.yml`) com identificador, publicador, licença, método de coleta, frequência e nível territorial. Cada entrada DEVE listar seus datasets (Pordata) ou indicadores (INE), cada um com identificador, origem e as colunas ou campos esperados.
- **FR-002**: Um coletor DEVE recusar a execução de uma fonte, dataset ou indicador que não esteja no catálogo (constitution IV).
- **FR-003**: Toda requisição DEVE enviar um User-Agent identificado do projeto, respeitar um tempo limite, limitar a taxa de requisições por servidor e fazer retentativas com espera crescente (constitution IV).
- **FR-004**: O sistema DEVE gravar o bruto de cada dataset ou indicador como veio da fonte, separado por fonte, execução e dataset, sem nunca sobrescrever um bruto existente (constitution V).
- **FR-005**: Toda execução DEVE gerar um manifest com `source_id`, `run_id`, método, horário da coleta em UTC, licença e, **para cada dataset ou indicador**: identificador, origem, status (`changed`, `unchanged` ou `failed`), `sha256`, tamanho em bytes, período de referência (quando a fonte o informa) e mensagem de erro (quando `failed`).
- **FR-006**: Se o `sha256` de um dataset for igual ao do último estado válido desse mesmo dataset, o sistema DEVE registrar `unchanged` para ele e NÃO DEVE gravar bruto novo (constitution V). O estado vigente é independente por dataset.
- **FR-007**: Uma falha em um dataset ou indicador DEVE ser registrada no manifest com o motivo, NÃO DEVE deixar arquivo parcial dele no bruto e NÃO DEVE impedir a coleta dos demais. O comando DEVE terminar com código de erro se algum falhar.
- **FR-008**: O sistema DEVE validar cada bruto antes de aceitá-lo: não vazio, não HTML, e com as colunas ou campos esperados do catálogo. Um bruto reprovado nunca vira novo estado vigente.
- **FR-009**: A coleta do INE DEVE usar a API de indicadores, consultando cada indicador pelo código declarado no catálogo, e NÃO DEVE depender de links de exportação gerados pelo site.
- **FR-010**: O destino DEVE ser selecionável entre local e S3 com a mesma lógica e o mesmo layout de chaves. O modo local NÃO DEVE exigir credenciais, e nenhuma credencial DEVE ser lida de arquivo versionado (constitution I).
- **FR-011**: O operador DEVE poder executar a coleta de cada fonte por um comando único e DEVE receber ao final um resumo com o status de cada dataset ou indicador e o caminho do manifest.

**Staging e qualidade**

- **FR-012**: O sistema DEVE produzir, para cada dataset e indicador, um staging em formato longo a partir do último estado válido, com: código `dico`, indicador e dimensões do dataset, período, valor, unidade, símbolo da fonte (quando houver) e proveniência (fonte, execução, licença).
- **FR-013**: O sistema DEVE resolver o município para o código oficial `dico`: no Pordata, pelo nome, por uma tabela de sinônimos de município; no INE, pelo código geográfico da própria fonte, cujos quatro últimos caracteres são o `dico`, sem depender de nome. Um nome sem correspondência DEVE interromper o staging do dataset, informando os nomes, e NÃO DEVE ser descartado em silêncio (constitution III).
- **FR-014**: Homônimos DEVEM ser distinguidos por uma regra explícita da tabela de sinônimos. O sistema NÃO DEVE escolher uma correspondência arbitrária.
- **FR-015**: Linhas de agregação (país, regiões, distritos, NUTS) NÃO DEVEM entrar como município; o sistema DEVE contar quantas foram excluídas.
- **FR-016**: Valores ausentes, suprimidos ou marcados com símbolo pela fonte DEVEM permanecer ausentes, com o símbolo preservado. Nenhum valor DEVE ser inventado, imputado ou convertido em zero (constitution III).
- **FR-017**: O período DEVE ser normalizado para o valor correto da fonte, sem artefatos de formatação regional (o legado gravava anos como "2.024,00").
- **FR-018**: Testes de qualidade DEVEM verificar: unicidade da chave de cada observação, todo `dico` existente na dimensão de municípios da spec 001, valores numéricos válidos quando presentes, unidade e período presentes. Uma falha DEVE interromper a execução.
- **FR-019**: O sistema DEVE gerar um relatório de cobertura por dataset com: municípios com valor no período mais recente (de 308), municípios sem valor (com código e nome), último período com dados e linhas de agregação excluídas.
- **FR-020**: Todo staging DEVE carregar fonte, período de referência e licença (constitution III). A regra de normalização de nomes DEVE ser a da spec 001 (FR-016), sem uma segunda implementação.
- **FR-021**: Toda a lógica de coleta, validação, staging e cobertura DEVE ser testável sem acesso à rede, com fixtures gravadas (constitution, Quality Gates).

*Marcador de requisito não claro:*

- **FR-022**: O sistema DEVE registrar no catálogo, em cada dataset e em cada linha do staging, a licença e a atribuição da fonte. Para o INE: CC BY 4.0 com a citação exigida. Para o Pordata: licença "não concedida pela fonte" e o risco aceito pelo autor, em vez de um identificador de licença aberta.
- **FR-023**: O sistema DEVE permitir ao operador entregar a planilha de poder de compra do Pordata por um comando de carga manual, que a valida (abas e cabeçalhos esperados, os 308 municípios), a guarda como bruto imutável e a registra no manifest com o mesmo estado vigente por dataset, `unchanged` para o mesmo conteúdo e `failed` com o motivo para uma planilha inválida. Nenhuma planilha real vai para o Git.

### Key Entities *(include if feature involves data)*

- **Fonte**: `pordata` ou `ine`, com publicador, licença, método, frequência e nível territorial.
- **Dataset / Indicador**: uma unidade coletável e independente do catálogo, com identificador, origem, colunas ou campos esperados e período de referência.
- **Execução (run)**: uma tentativa de coletar uma fonte, com `run_id` e horário.
- **Manifest**: o registro auditável de uma execução, com o resultado de cada dataset ou indicador.
- **Arquivo bruto**: os bytes como vieram da fonte, imutáveis, por fonte, execução e dataset.
- **Estado vigente de um dataset**: o último bruto aceito (`changed`) daquele dataset, independente dos outros.
- **Sinônimo de município**: correspondência entre uma grafia vinda de uma fonte e o código oficial `dico`, com regra para homônimos.
- **Observação (staging)**: uma linha em formato longo: município (`dico`), indicador e dimensões, período, valor, unidade, símbolo e proveniência.
- **Relatório de cobertura**: por dataset, a contagem e a lista de municípios com e sem valor.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Num ambiente limpo, um único comando por fonte coleta todos os datasets declarados. Uma segunda execução sem mudança na fonte termina com todos `unchanged` e nenhum arquivo bruto novo.
- **SC-002**: Quando um dataset falha, 100% dos demais são coletados normalmente, 100% dos falhos têm o motivo no manifest, e nenhum arquivo parcial permanece no bruto.
- **SC-003**: Em 100% dos datasets aceitos, toda linha municipal resolve para um dos 308 códigos oficiais, e 0 nomes sem correspondência são aceitos em silêncio.
- **SC-004**: Todo dataset tem relatório de cobertura, e nenhum valor ausente na fonte aparece como zero ou como valor estimado no staging.
- **SC-005**: As execuções com destino local e com destino S3 (simulado) produzem o mesmo conjunto de chaves e manifests equivalentes.
- **SC-006**: A suíte de testes da feature roda sem acesso à rede e passa no CI.
- **SC-007**: A primeira coleta real, feita uma vez em ambiente local, registra para cada um dos 16 datasets do Pordata, para a planilha manual e para os 3 conjuntos do INE o status e a cobertura, ou a lista explícita dos que falharam e o motivo. Essa verificação manual é distinta da prova automatizada.

## Assumptions

- **Depende da spec 001** (convergida): usa a dimensão de 308 municípios (`dim_municipality`), a regra única de normalização de nomes, o padrão de coletor com dependências injetadas e os destinos local e S3.
- **Datasets do Pordata** são os 16 CSV e a planilha manual listados no Escopo. As URLs do blob do Pordata são internas do site e podem mudar; uma mudança vira falha explícita do dataset, não erro silencioso. O Pordata 845 não tem URL conhecida e fica para depois.
- **Indicadores do INE** (levantados no plano, 2026-11-11): rendas `0014698`, criminalidade `0008074` e poder de compra `0014580`, todos com os 308 municípios na API. A cobertura das rendas é parcial por regra do INE (mínimo de contratos por unidade territorial): 247 dos 308 municípios têm valor em 2025.
- **Nível município apenas.** Freguesia depende da tabela de correspondência 2013→2025 e fica fora.
- **Séries completas:** o staging mantém todos os períodos disponíveis de cada dataset. A escolha do período usado por cada critério pertence à camada seguinte.
- **A tabela de sinônimos de município** é mantida à mão, nasce dos nomes encontrados nas duas fontes e cobre só municípios.
- O operador roda os comandos localmente, com acesso à internet. Não há agendamento nesta feature; o ciclo mensal virá com a orquestração.
- O volume é pequeno (bem abaixo de 1 GB) e o custo recorrente desta feature é zero (local e S3 simulado); recursos AWS reais ficam sob o gate da constitution.
- **Licenças** (conferidas no plano): o INE permite reutilização sob CC BY 4.0, citando "Instituto Nacional de Estatística, IP – Portugal", o indicador e o período, e sinalizando dados modificados. Os termos do Pordata não concedem licença de reutilização; o autor decidiu coletar mesmo assim, como risco aceito registrado no plano.

## Clarifications

### Sessão 2026-11-11

- Q: Até onde esta spec vai depois de gravar o bruto? → A: Raw + Bronze com `dico`: coleta com manifest e, por dataset, um staging em formato longo com o município resolvido por tabela de sinônimos. Sem Silver de indicadores nem Gold.
- Q: Como o INE entra? → A: Pela API JSON de indicadores, por código de indicador, e não pelos `.xls` de links `clientFiles` do legado.
- Q: Quais indicadores do INE entram? → A: Rendas da habitação ao nível local (mediana de novos contratos) e taxa de criminalidade, ambos por município.
- Q: Quais datasets do Pordata entram? → A: Só os usados pelos critérios do plano (16 CSV e a planilha de poder de compra per capita); ficam fora 294, 445, 447, 582 e a planilha de proporção; o 845 depende de URL ainda desconhecida.
- Q: Se um dataset falhar, o que acontece com os demais? → A: Tolerância por dataset: os válidos são gravados, cada falha é registrada com o motivo, nenhum arquivo parcial fica no bruto e o comando sai com código de erro.
- Q: Freguesia entra agora? → A: Não; só município, porque a tabela de correspondência 2013→2025 está fora do escopo da spec 001.
- Q: Esta spec entrega relatório de cobertura por dataset? → A: Sim, com a contagem de municípios com valor no período mais recente e a lista dos que não têm, sem imputar nada.

### Sessão 2026-11-11 (sdd-plan)

- Q: Como tratar a licença do Pordata, cujos termos não concedem reutilização? → A: O autor decidiu coletar mesmo assim ("os dados são públicos"); entra como risco aceito registrado no plano (constitution IV), sem bloquear a coleta.
- Q: A planilha de poder de compra do Pordata, cuja URL morreu? → A: O poder de compra passa a ser coletado pela API do INE (`0014580`) **e** mantido como carga manual do Excel exportado do Pordata, porque o autor não tem certeza de que o INE cobre o necessário. Entram como datasets distintos.
- Q: Como resolver o município no INE? → A: Pelo código geográfico da fonte (os 4 últimos caracteres são o `dico`; 308 de 308 conferem com a CAOP), sem sinônimos. No Pordata, pelo nome e pela tabela de sinônimos.
- Q: Qual a cobertura real das rendas do INE? → A: Parcial: 247 dos 308 municípios têm valor em 2025 e 222 em 2020; o INE só publica unidades com contratos suficientes. A ausência permanece explícita; o `.docs` que afirmava cobertura total estava incorreto.
