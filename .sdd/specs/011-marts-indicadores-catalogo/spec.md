# Feature Specification: Marts de indicadores e criteria_catalog versionado

**Slug**: `011-marts-indicadores-catalogo`

**Created**: 2026-11-24

**Status**: Convergida

**Input**: Fase 3: marts de indicadores municipais (e de freguesia quando houver dado) e criteria_catalog versionado (plano §8.1 e §8.2), que alimenta o ranker. Critério: dbt build verde localmente (dbt-duckdb); execução no S3 condicionada à Fase 1. Mobilidade usa stg_municipality_pole_distance com atribuição "Tempos de viagem: Google".

## Escopo

### Incluído

- Mart de indicadores por município (308 municípios da CAOP vigente) com as categorias do catálogo do MVP (plano §8.1): custo, clima, cultura, economia, emprego e salários, educação, população, comunidade estrangeira, saúde, segurança, distância a capitais e mercado habitacional.
- Aluguel descritivo do Idealista por município e tipologia (n, mediana, P25, P75, €/m² mediano), com outliers marcados por IQR, ao lado da renda mediana do INE.
- Indicadores de clima derivados do clima diário do Open-Meteo: médias mensais e anuais, percentual de dias extremos e TCI mensal e anual, com as regras do `weatherClassifier` do legado adaptadas às variáveis do Open-Meteo.
- `criteria_catalog` versionado: um registro por critério com os metadados do plano §8.1 (id, categoria, rótulos PT-BR/EN, unidade, fonte, período de referência, direção, nível, modos permitidos, faixa padrão, licença), estado (`disponível` ou `fonte pendente`) e parâmetros de normalização calculados da distribuição real.
- Mart de freguesia (P3) com indicadores próprios onde existir dado (Censos 2021, densidade, aluguel com n ≥ 10) e os demais herdados do município, com a origem sinalizada por indicador.
- Mart de qualidade de dados (P2): cobertura por indicador e nível, período usado, quantidade de valores em período anterior ao nacional e critérios com fonte pendente.
- Testes que garantem `dbt build` verde no ambiente local, sobre o lake local.

### Fora de Escopo

- Ranker (`packages/ranker`), score, filtros e golden tests do ranking (Fase 4).
- Exportação para o formato de consumo do ranker (`criteria.json`, `published/vN`, contrato em `packages/contracts/`) e publicação versionada (Fase 4/5).
- Execução no S3, imagem ECS, workflows MWAA e qualquer recurso AWS (Fase 1; a execução no S3 fica condicionada a ela).
- Coleta de fontes novas ou recoleta das existentes, incluindo o upload manual do poder de compra e o transporte público na mobilidade.
- Indicadores de proximidade por raio ("hospital ou ensino superior a ≤ X km"), que exigem pontos georreferenciados ainda inexistentes (Fase B).
- Clima e mobilidade calculados no centroide da freguesia: hoje só existem por município e entram herdados.
- Score climático diário contínuo e classificação textual de dias ("Excelente", "Bom"...) do legado; só os extremos e o TCI entram.
- Comparação do TCI com o ranking legado (o legado usou o WWO; a validação é só por casos sintéticos).
- Wikipedia como critério (é conteúdo da ficha, não indicador).
- Previsão de aluguel por ML (Fase B).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Perfil municipal de indicadores e catálogo de critérios (Priority: P1)

Como autor do projeto (e futuro ranker), quero uma tabela com um registro por município e indicador, já normalizada para unidades comparáveis (por habitante, percentuais, médias), e um catálogo versionado que descreva cada critério e diga se ele tem dado. Assim o ranker é construído sobre uma base processada e verificável, e cada critério aponta para um dado que existe no lake.

**Why this priority**: é o núcleo da Fase 3 e o insumo direto do ranker e do "v0 sem Idealista" (plano §15). Sem ele não há recomendação.

**Independent Test**: rodar o build local sobre o lake e conferir que todo critério `disponível` do catálogo tem valores no perfil municipal, que os 308 municípios aparecem, que cada valor traz fonte, período e licença, e que os parâmetros de normalização existem para todo critério disponível.

**Acceptance Scenarios**:

1. **Given** o lake local com as fontes das specs 001–009, **When** o build roda, **Then** o perfil municipal tem exatamente os 308 municípios da CAOP vigente para cada critério disponível, com valor ou ausência explícita.
2. **Given** um critério marcado como `disponível` no catálogo, **When** não existe nenhum valor para ele no perfil, **Then** o build falha com uma mensagem que nomeia o critério.
3. **Given** um critério marcado como `fonte pendente` (ex.: poder de compra do upload manual, se ausente), **When** o build roda, **Then** o build passa e o critério aparece como pendente no mart de qualidade.
4. **Given** um dataset cujo ano mais recente não cobre um município, **When** o perfil é montado, **Then** esse município usa o seu ano mais recente com valor, a linha registra o ano usado e a bandeira "período anterior ao nacional".
5. **Given** um indicador de mobilidade de carro, **When** ele aparece no perfil e no catálogo, **Then** traz a atribuição "Tempos de viagem: Google" e a restrição de uso da fonte; o de linha reta traz a atribuição da CAOP.
6. **Given** o clima diário de um município, **When** o perfil é montado, **Then** existem médias mensais e anuais, percentuais de dias extremos e TCI mensal e anual calculados pelas regras documentadas.

---

### User Story 2 - Qualidade e cobertura dos indicadores (Priority: P2)

Como autor, quero um relatório de qualidade que diga, para cada indicador e nível, quantos territórios têm valor, qual período foi usado, quantos valores vieram de um período anterior ao nacional e quais critérios estão com fonte pendente. Assim vejo lacunas da ingestão antes do ranker e consigo explicar a cobertura no site.

**Why this priority**: é a "checagem final da ingestão" do backlog e base do selo de cobertura; depende do perfil da P1, mas entrega valor sem a freguesia.

**Independent Test**: com a P1 pronta, rodar o build e conferir que o mart de qualidade tem uma linha por critério e nível, com contagens que batem com o perfil.

**Acceptance Scenarios**:

1. **Given** o perfil municipal, **When** o mart de qualidade é gerado, **Then** cada critério tem: territórios esperados, com valor, ausentes, em período anterior ao nacional, período nacional mais recente e estado do critério.
2. **Given** um critério pendente, **When** o mart é gerado, **Then** ele aparece com cobertura zero e o motivo "fonte pendente", sem falhar o build.
3. **Given** o aluguel do Idealista, **When** o mart é gerado, **Then** ele mostra quantos municípios e tipologias têm n ≥ 10 e quantos anúncios foram marcados como outlier.

---

### User Story 3 - Indicadores por freguesia com origem sinalizada (Priority: P3)

Como autor, quero um perfil por freguesia para o drill-down: indicadores próprios onde há dado da freguesia (população e faixas etárias dos Censos 2021, densidade, aluguel com amostra suficiente) e os demais herdados do município, com a origem marcada em cada indicador. Assim o drill-down nunca mostra uma diferença entre freguesias que os dados não sustentam.

**Why this priority**: o plano coloca o drill-down como v1.1; a P1 e a P2 já entregam o ranking municipal.

**Independent Test**: rodar o build e conferir que todas as freguesias da CAOP vigente aparecem, que cada indicador tem origem `próprio`, `herdado` ou ausente, e que os herdados são iguais ao valor do município.

**Acceptance Scenarios**:

1. **Given** uma freguesia com dados dos Censos 2021 (via correspondência 2013→2025), **When** o perfil é montado, **Then** população, % 25–39 anos, % 65+ e densidade são `próprio`, e a herança da correspondência 2013→2025 continua sinalizada.
2. **Given** uma freguesia com n ≥ 10 anúncios elegíveis, **When** o perfil é montado, **Then** o aluguel é `próprio`; por tipologia só quando a tipologia tem n ≥ 10, senão só o €/m².
3. **Given** uma freguesia sem amostra de aluguel suficiente, **When** o perfil é montado, **Then** o aluguel é `herdado` do município (ou ausente se o município também não tiver).
4. **Given** um indicador que só existe por município (saúde, educação, segurança, clima, mobilidade), **When** o perfil de freguesia é montado, **Then** ele é `herdado`, com valor idêntico ao do município.

---

### Edge Cases

- Município sem nenhum valor num dataset (nunca publicado): o indicador fica ausente, nunca imputado, e conta como ausente na cobertura.
- Valor com símbolo da fonte (`x`, `-`, `...`) e valor nulo: ausente, com o símbolo preservado como motivo.
- Indicador por habitante cujo denominador (população) falta no mesmo ano do numerador: o indicador fica ausente para aquele município.
- Ilhas (Açores e Madeira): só têm distância a polos do mesmo grupo de roteamento; pares `sem_rota` não viram valor. Ilhas sem amostra de aluguel recebem `rent_coverage = 'regional_only'` quando só há anúncios regionais.
- Pares de mobilidade `falha`, `pendente` ou `stale`: o primeiro e o segundo ficam ausentes; o `stale` é usado, mas sinalizado no mart de qualidade.
- Município-polo (distância 0 por `identity`): o valor 0 é válido, não ausente.
- Dias de clima com variável nula: o dia é ignorado só no cálculo que usa a variável, e o mês com menos de um mínimo de dias válidos fica sem valor mensal.
- Tipologia com n < 10 no município: mediana, P25 e P75 ausentes com "amostra insuficiente"; n continua visível.
- Grupo município × tipologia pequeno demais para IQR: nenhum outlier é marcado (o mínimo de n segue o limiar de 10).
- Anúncios regionais (sem município): não entram em nenhum agregado municipal nem são redistribuídos.
- Critério categórico (porte populacional, clima-alvo): o catálogo define as opções e as faixas, mas o valor no perfil é numérico.
- Distribuição degenerada (todos os municípios com o mesmo valor, P5 = P95): os parâmetros são registrados, e o caso fica sinalizado no catálogo.

## Requirements *(mandatory)*

### Functional Requirements

**Perfil municipal (P1)**

- **FR-001**: O sistema DEVE produzir um perfil municipal com uma linha por município da CAOP vigente e indicador, cobrindo exatamente os 308 municípios.
- **FR-002**: Cada valor do perfil DEVE trazer fonte, dataset de origem, período de referência usado, licença, atribuição e restrição de uso da fonte (quando houver).
- **FR-003**: Para cada indicador, o sistema DEVE usar o período mais recente com valor do município; quando esse período for anterior ao mais recente do dataset, a linha DEVE levar a bandeira "período anterior ao nacional". Só fica ausente o município que nunca teve valor.
- **FR-004**: Indicadores por habitante DEVEM usar a população residente do mesmo município e do mesmo período do numerador; sem denominador, o indicador fica ausente.
- **FR-005**: Valores ausentes DEVEM permanecer ausentes, com o motivo (símbolo da fonte, sem publicação, sem rota, amostra insuficiente). Nenhum valor DEVE ser imputado.
- **FR-006**: O perfil DEVE incluir os indicadores do catálogo do MVP que têm dado no lake: cinemas e sessões de espetáculos ao vivo por 10 mil habitantes; agências bancárias por 10 mil habitantes; poder de compra per capita (INE); desemprego registado, ganho médio mensal e emprego por setor; escolas não superiores por mil jovens e presença de ensino superior no município; residentes, densidade, % 25–39 anos e % 65+; % de população estrangeira; hospitais no município e farmácias por 10 mil habitantes; taxa de criminalidade e crimes contra pessoas por mil habitantes; fogos novos concluídos por mil habitantes.
- **FR-007**: O perfil DEVE incluir, por município, a distância em linha reta (km) e a distância e o tempo de carro (km e minutos) até Lisboa, Porto, a sede de distrito (ou capital regional) e o aeroporto mais próximo, a partir de `stg_municipality_pole_distance`. Só pares `ok` viram valor.
- **FR-008**: Os indicadores de carro DEVEM levar a atribuição "Tempos de viagem: Google" e a restrição de uso registrada (ADR-002 D8, ADR-004); a linha reta leva a atribuição da CAOP.

**Aluguel (P1)**

- **FR-009**: O sistema DEVE produzir, por município e tipologia (T0, T1, T2, T3, T4+) e para todas as tipologias juntas, n, mediana, P25, P75 e €/m² mediano dos preços pedidos do Idealista no snapshot vigente.
- **FR-010**: Os outliers de preço DEVEM ser marcados por IQR dentro de cada município e tipologia, sem apagar anúncios. As estatísticas DEVEM ser calculadas sem os marcados, e as contagens com e sem outliers DEVEM ficar visíveis.
- **FR-011**: Mediana, P25 e P75 só DEVEM existir com n ≥ 10 (após excluir os outliers); abaixo disso, ficam ausentes com o motivo "amostra insuficiente".
- **FR-012**: Anúncios só regionais (sem município) NÃO DEVEM entrar em agregados municipais. Ilhas sem amostra municipal e com anúncios regionais DEVEM receber `rent_coverage = 'regional_only'`.
- **FR-013**: A renda mediana do INE (novos contratos, €/m²) DEVE aparecer como indicador próprio, com o seu período de referência, ao lado das estatísticas do Idealista.

**Clima (P1)**

- **FR-014**: O sistema DEVE calcular por município, na janela coletada do Open-Meteo, médias mensais e anuais de temperatura média, máxima e mínima, precipitação total e horas de sol.
- **FR-015**: O sistema DEVE calcular o percentual de dias extremos por tipo e no total: calor (máxima > 35 °C ou temperatura aparente máxima > 40 °C), frio (mínima < 1 °C ou temperatura aparente mínima < −5 °C), chuva (> 35 mm) e neve (> 0 cm).
- **FR-016**: O sistema DEVE calcular o TCI mensal e anual com as faixas e os pesos do `weatherClassifier` legado (TCI = 2·CID + 2·CIA + 0,5·P + 0,5·S + W, limitado a 0–100), usando a temperatura média, a máxima, a umidade relativa média, a precipitação, as horas de sol (de `sunshine_duration`) e o vento médio do Open-Meteo.
- **FR-017**: A adaptação das variáveis do legado (temperatura aparente no lugar de Heat Index e Wind Chill, horas de sol a partir de segundos) DEVE estar documentada na metodologia do catálogo.
- **FR-018**: As regras de extremos e do TCI DEVEM ter testes com casos sintéticos que cubram cada faixa e cada limite das regras do legado.

**Catálogo de critérios (P1)**

- **FR-019**: O sistema DEVE manter um `criteria_catalog` versionado com, por critério: id estável, categoria, rótulos PT-BR e EN, unidade, fonte, período de referência, direção (maior é melhor, menor é melhor, faixa-alvo), nível (município, freguesia ou ambos), modos permitidos (peso, faixa, opção categórica), faixa padrão, peso interno na categoria, licença e atribuição.
- **FR-020**: Cada critério DEVE ter um estado: `disponível` ou `fonte pendente`. O build DEVE falhar se um critério `disponível` não tiver valor no perfil correspondente.
- **FR-021**: Para cada critério disponível, o catálogo DEVE trazer os parâmetros de normalização calculados da distribuição real do nível: P5, P95, mínimo, máximo e n de territórios com valor.
- **FR-022**: O catálogo DEVE ter uma versão identificável, e toda mudança de critério ou de parâmetro DEVE produzir uma versão nova.
- **FR-023**: Critérios categóricos (porte populacional, clima-alvo) DEVEM declarar no catálogo as suas opções e a faixa-alvo de cada uma.
- **FR-024**: Os pesos internos dos indicadores de uma mesma categoria DEVEM somar 1.

**Qualidade (P2)**

- **FR-025**: O sistema DEVE produzir um mart de qualidade com uma linha por critério e nível: territórios esperados, com valor, ausentes, em período anterior ao nacional, período mais recente do dataset, estado do critério e motivo quando pendente.
- **FR-026**: O mart de qualidade DEVE mostrar, para o aluguel, os municípios e tipologias com n ≥ 10 e a contagem de anúncios marcados como outlier; para a mobilidade, os pares `stale`.

**Freguesia (P3)**

- **FR-027**: O sistema DEVE produzir um perfil por freguesia com todas as freguesias da CAOP vigente, cada indicador com origem `próprio`, `herdado` ou ausente.
- **FR-028**: População residente, % 25–39 anos, % 65+ e densidade (população dos Censos 2021 ÷ área CAOP) DEVEM ser `próprio` quando a freguesia tiver valor dos Censos; a sinalização de herança da correspondência 2013→2025 DEVE ser preservada.
- **FR-029**: O aluguel da freguesia DEVE ser `próprio` com n ≥ 10 anúncios elegíveis; por tipologia só quando a tipologia tem n ≥ 10, senão só o €/m². Sem amostra suficiente, herda do município.
- **FR-030**: Indicadores que só existem por município DEVEM ser `herdados`, com valor idêntico ao do município, e NÃO DEVEM contar para a cobertura própria da freguesia.

**Build (todas)**

- **FR-031**: Todos os modelos novos DEVEM ter testes de chave (`unique`, `not_null`), relacionamento com `dim_municipality` e `dim_parish`, valores aceitos nos campos categóricos e faixas plausíveis (aluguel €100–€10.000; percentuais 0–100; TCI 0–100).
- **FR-032**: O build completo DEVE passar no ambiente local, sobre o lake local. A execução no S3 não faz parte desta feature.
- **FR-033**: As tabelas novas DEVEM aparecer no dicionário de dados e no catálogo do lake da spec 010, com as colunas descritas.

### Key Entities *(include if feature involves data)*

- **Indicador municipal**: valor de um critério para um município; leva o período usado, a bandeira de período anterior, o motivo da ausência e a proveniência (fonte, licença, atribuição, restrição).
- **Estatística de aluguel**: n, n de outliers, mediana, P25, P75 e €/m² por território (município ou freguesia) e tipologia, com a situação da amostra e `rent_coverage`.
- **Indicador climático**: médias, percentuais de extremos e TCI, mensais e anuais, por município e janela.
- **Critério do catálogo**: definição de um critério (metadados, estado, parâmetros de normalização) dentro de uma versão do catálogo.
- **Indicador de freguesia**: valor de um critério para uma freguesia, com origem `próprio`/`herdado`/ausente.
- **Registro de qualidade**: cobertura e período de um critério num nível.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos critérios marcados como disponíveis têm valor para pelo menos um município, e o build falha nos casos em que não têm.
- **SC-002**: Os 308 municípios aparecem no perfil municipal para cada critério disponível, sem nenhum valor imputado (toda ausência tem motivo).
- **SC-003**: 100% dos valores publicáveis do perfil trazem fonte, período e licença.
- **SC-004**: O build local completo, com todos os testes, termina sem erro.
- **SC-005**: Cada faixa e cada limite das regras de extremos e do TCI têm um caso de teste sintético que passa.
- **SC-006**: Nenhuma mediana de aluguel aparece com n < 10.
- **SC-007**: No perfil de freguesia, 100% dos indicadores herdados são iguais ao valor do município, e todas as freguesias da CAOP vigente aparecem.
- **SC-008**: O mart de qualidade lista todos os critérios do catálogo, e as contagens dele batem com o perfil.

## Assumptions

- As fontes necessárias já estão no lake local (specs 001–009). Esta feature não coleta nada.
- A janela do clima é a coletada pelo Open-Meteo (24 meses, 2024-11 a 2026-10). As "médias" são dessa janela, não normais climatológicas de 30 anos.
- O poder de compra pode existir pelo INE (`poder_compra_per_capita`). Se não houver valor no lake, o critério entra como `fonte pendente`, sem bloquear a feature.
- As licenças vêm de `config/sources.yml` e são copiadas como estão. O Pordata e o Google têm `not_granted_by_source`; a decisão de publicar fica com a Fase 4/5, como risco já aceito nos ADRs.
- O snapshot vigente do Idealista é o mais recente importado (hoje, 2026-11): 54 municípios com anúncios, 42 com n ≥ 10.
- As fórmulas exatas de cada indicador (numerador, denominador, filtros do dataset) e os rótulos PT-BR/EN ficam definidos no catálogo durante o plano.
- O limiar de 10 anúncios vale para município e freguesia (constitution III).
- O ranking principal continua por município; a freguesia é só drill-down (constitution, Fora do Escopo do MVP).

## Clarifications

### Sessão 2026-11-24

- Q: O nível freguesia entra nesta spec? → A: Sim, como P3: indicadores próprios onde há dado (Censos, densidade, aluguel com n ≥ 10) e os demais herdados, com a origem sinalizada.
- Q: Que período cada indicador municipal usa? → A: O mais recente com valor do município. Se for anterior ao período mais recente do dataset, a linha leva a bandeira "período anterior ao nacional". Só fica ausente quem nunca teve valor. (Isso substitui a primeira resposta, "último ano nacional sem fallback", que o autor revisou.)
- Q: O que acontece quando um critério não aponta para um dado no lake? → A: Estado por critério (`disponível` / `fonte pendente`); o build falha se um critério disponível não tiver dado; os pendentes vão para o mart de qualidade.
- Q: Até onde vai o clima? → A: Médias, percentual de dias extremos e TCI.
- Q: Como adaptar Heat Index e Wind Chill, que o Open-Meteo não tem? → A: Temperatura aparente máxima > 40 °C e mínima < −5 °C no lugar deles; horas de sol a partir de `sunshine_duration`; adaptação documentada.
- Q: Como validar o TCI? → A: Só por testes com casos sintéticos das regras do legado; sem comparação com o ranking legado.
- Q: Outliers de aluguel? → A: Marcados por IQR dentro de município × tipologia, sem apagar; as estatísticas usam os não marcados, e as duas contagens ficam visíveis.
- Q: A spec calcula os parâmetros de normalização? → A: Sim, P5, P95, mínimo, máximo e n por critério, guardados na versão do catálogo.
- Q: Mart de qualidade de dados? → A: Sim, como P2.
- Q: Exportar o catálogo e os marts para o formato do ranker (`criteria.json`, `published/vN`)? → A: Não; fica na Fase 4.
