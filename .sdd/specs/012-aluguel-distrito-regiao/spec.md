# Feature Specification: Aluguel por distrito e por região na Gold, com herança marcada

**Slug**: `012-aluguel-distrito-regiao`

**Created**: 2026-11-24

**Status**: Implementada

**Input**: Aluguel por distrito e por região na camada Gold: novas tabelas Gold de mediana de aluguel (Idealista) por distrito e por região da fonte (mesmas regras da 011: snapshot vigente, IQR 1,5 por território × tipologia, n ≥ 10), e o indicador municipal/freguesia custo_aluguel_* passa a usar a referência do nível mais fino com dado, marcada como herdada (origin/territorial_inheritance = distrito|regiao). Motivo: muitos distritos (Braga, Aveiro, Coimbra, Setúbal, Alentejo, ilhas) foram extraídos só no nível do distrito, então 266 municípios ficam sem aluguel e com rótulo enganoso 'sem_anuncios'. Protótipo validado no notebook analytics/notebooks/explorar_gold.ipynb (view aluguel_regional; SQL reproduz a Gold em 279 combinações município × tipologia).

## Contexto

No snapshot vigente do Idealista (2026-11), só os distritos de Lisboa, Porto e Faro foram extraídos no nível de
município. Os demais 15 distritos do continente e as ilhas vieram só com o distrito (ou ilha) e a região da fonte,
sem município. Hoje, pela regra da 011 (FR-012), esses anúncios não entram em nenhum agregado. Por isso só 42 dos
308 municípios têm mediana própria, e 228 municípios do continente aparecem como `sem_anuncios`, mesmo quando o
distrito tem centenas de anúncios. Braga, por exemplo, tem 873.

Esta feature publica o aluguel também por **distrito** e por **região**. Município e freguesia sem amostra própria
passam a receber a referência do nível mais fino que tem dado, **sempre marcada como herdada**, com o nível de
origem. Nenhum anúncio é atribuído a um município ao qual não pertence: a referência herdada é declaradamente da
área, não do município (constitution III).

## Escopo

### Incluído

- Aluguel descritivo do Idealista por **distrito** (ou ilha, nas regiões autónomas) e por **região da fonte**, por
  tipologia (`ALL`, T0, T1, T2, T3, T4+): n, outliers, elegíveis, mediana, P25, P75 e €/m² mediano. As regras são as
  mesmas do município na 011.
- Herança do aluguel no indicador municipal (`custo_aluguel_mediana`, `custo_aluguel_m2`): sem amostra própria na
  variante, o município herda do distrito e, se o distrito também não tiver, da região. A origem e o nível ficam
  marcados.
- Herança em cadeia na freguesia: freguesia (própria) › município (próprio) › distrito › região, com o nível de
  origem marcado.
- Rótulo de cobertura do aluguel honesto. O município sem amostra própria deixa de aparecer só como `sem_anuncios`
  quando existe referência de distrito ou região.
- Mart de qualidade com a contagem de valores próprios e herdados por nível de origem.
- Testes de dados para as tabelas novas e para a herança, e a documentação (dicionário de dados, runbook, notebook
  de exploração lendo a Gold).

### Fora de Escopo

- Recoleta do Idealista no nível de município para os distritos hoje só distritais. É o que resolve na fonte, mas
  é coleta manual (constitution IV) e fica para outra rodada.
- Regiões NUTS II oficiais. A região usada é a da fonte. Uma correspondência município → NUTS fica para depois, se
  for necessária.
- Herança para indicadores que não são de aluguel do Idealista. A renda mediana do INE e os demais indicadores
  seguem as regras da 011.
- Ranker, score e exportação para `published/vN` (Fase 4).
- Imputação estatística ou modelo (por exemplo, prever o aluguel do município a partir de vizinhos).
- Execução no S3 e qualquer recurso AWS.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Aluguel por distrito e por região na Gold (Priority: P1)

Como autor do projeto, quero tabelas Gold com a mediana de aluguel por distrito e por região, por tipologia, com as
mesmas regras de amostra e de outlier do município. Assim tenho uma referência de aluguel para áreas onde a fonte só
traz o distrito, consultável e com proveniência.

**Why this priority**: sem estas tabelas não há o que herdar. Sozinhas, já respondem "quanto custa um T2 no
distrito de Braga".

**Independent Test**: rodar o build Gold e conferir que cada distrito e cada região com anúncios no snapshot
vigente tem uma linha por tipologia; que a mediana só existe com n ≥ 10 elegíveis; e que distrito e região se
somam corretamente a partir dos anúncios.

**Acceptance Scenarios**:

1. **Given** anúncios do distrito de Braga só com o distrito (sem município), **When** o build roda, **Then** a
   tabela distrital tem Braga com a mediana de T2 e T3 calculada sobre esses anúncios.
2. **Given** anúncios com município num distrito extraído por município (por exemplo, Porto), **When** o build
   roda, **Then** eles entram na mediana do distrito do município e na da região.
3. **Given** um distrito × tipologia com menos de 10 anúncios elegíveis, **When** o build roda, **Then** a mediana
   fica ausente com o motivo "amostra insuficiente".
4. **Given** anúncios das ilhas, **When** o build roda, **Then** cada ilha aparece com o nome do CAOP (por exemplo,
   "Ilha de São Miguel") e a região é Madeira ou Açores.

---

### User Story 2 - Município herda o aluguel do distrito ou da região, marcado (Priority: P1)

Como autor (e futuro ranker), quero que o indicador de aluguel de todo município tenha valor quando houver
referência na área. O valor herdado deve vir marcado como herdado, com o nível de origem. Assim o ranking pode usar
o aluguel nos 308 municípios sem esconder que, em boa parte deles, o valor é do distrito.

**Why this priority**: é o pedido central. Sem ela, 266 municípios continuam sem aluguel no ranking.

**Independent Test**: rodar o build e conferir que, por variante, o município com n ≥ 10 próprio tem origem
`proprio`; que os demais têm o valor do distrito, ou da região quando o distrito não tem, com a origem e o nível
marcados; e que todo valor herdado é idêntico ao da tabela de origem.

**Acceptance Scenarios**:

1. **Given** o município de Braga sem anúncios próprios e o distrito de Braga com T2 n ≥ 10, **When** o build
   roda, **Then** `custo_aluguel_mediana` T2 de Braga é igual à mediana T2 do distrito, com origem herdada e nível
   `distrito`.
2. **Given** um município com `ALL` próprio (n ≥ 10) e T2 com n < 10, **When** o build roda, **Then** `ALL` é
   `proprio` e T2 é herdado do distrito, cada variante com a sua origem.
3. **Given** um distrito sem n ≥ 10 numa variante e a região com n ≥ 10, **When** o build roda, **Then** o
   município herda da região, com nível `regiao`.
4. **Given** nenhuma referência com n ≥ 10 em nenhum nível, **When** o build roda, **Then** o indicador fica
   ausente com motivo.
5. **Given** os limites de normalização (P5/P95) do aluguel, **When** o catálogo é gerado, **Then** eles usam só
   os valores próprios dos municípios.

---

### User Story 3 - Freguesia herda em cadeia e a qualidade mostra a origem (Priority: P2)

Como autor, quero que o aluguel da freguesia siga a mesma cadeia: freguesia, município, distrito, região. Quero
também que o mart de qualidade diga quantos territórios têm valor próprio e quantos herdaram, por nível de origem.
Assim o drill-down e o relatório de cobertura contam a verdade sobre de onde vem cada número.

**Why this priority**: completa a herança no nível mais fino e torna a cobertura auditável. O ranking municipal já
funciona sem ela.

**Independent Test**: rodar o build e conferir que toda freguesia tem o aluguel do nível mais fino disponível, com
o nível marcado, e que o mart de qualidade soma próprios e herdados por nível igual ao total de territórios.

**Acceptance Scenarios**:

1. **Given** uma freguesia sem amostra própria num município também sem amostra, **When** o build roda, **Then** o
   aluguel da freguesia é o do distrito, marcado com nível `distrito`.
2. **Given** o mart de qualidade, **When** o build roda, **Then** cada critério de aluguel mostra, por nível de
   território, quantos valores são próprios e quantos foram herdados de município, distrito e região.

---

### Edge Cases

- **Municípios de Lisboa, Porto e Faro:** os distritos extraídos por município não têm anúncios só distritais. A
  mediana do distrito sai dos anúncios dos municípios.
- **Ilhas:** a fonte escreve "São Miguel (Ilha dos Açores)", e o CAOP escreve "Ilha de São Miguel". O nome tem de
  ser resolvido por correspondência explícita. Uma ilha da fonte sem par no CAOP falha o build (constitution III).
- **Anúncios das ilhas sem região na fonte, mas com município** (Flores, Pico, Horta): a região vem da região
  autónoma do município.
- **Distrito da fonte que não existe no CAOP:** falha o build, nunca vira um território novo.
- **Distrito associado a mais de uma região na fonte:** falha o build, porque a hierarquia precisa ser única.
- **Snapshot novo extraído por município num distrito hoje distrital:** o município passa a `proprio` quando tiver
  n ≥ 10, sem mudança de código.
- **`regional_only` da 011 (ilhas):** deixa de ser o estado final quando a ilha ou a região tem referência. O valor
  é herdado e a cobertura própria continua registrada.

## Requirements *(mandatory)*

### Functional Requirements

**Aluguel por distrito e região**

- **FR-001**: O sistema DEVE produzir, por distrito (ilha nas regiões autónomas) e tipologia (`ALL`, T0–T4+), n de
  anúncios, outliers, elegíveis, mediana, P25, P75 e €/m² mediano do snapshot vigente do Idealista.
- **FR-002**: O sistema DEVE produzir as mesmas medidas por região da fonte (Norte, Centro, Área Metropolitana de
  Lisboa, Algarve, Alentejo, Madeira, Açores).
- **FR-003**: Um anúncio DEVE entrar no distrito do seu município, quando tiver município, ou no distrito informado
  pela fonte, quando não tiver. A região DEVE ser a da fonte; sem região na fonte, a da região autónoma do município.
- **FR-004**: Outliers DEVEM ser marcados por IQR 1,5 em cada território × tipologia com pelo menos 10 preços. A
  mediana, P25 e P75 só DEVEM existir com n ≥ 10 elegíveis; abaixo disso, ficam ausentes com motivo.
- **FR-005**: Todo distrito da fonte DEVE corresponder a um distrito ou ilha do CAOP, e cada distrito DEVE pertencer
  a uma única região. Qualquer violação DEVE falhar o build.
- **FR-006**: As tabelas novas DEVEM levar fonte, licença, atribuição e mês do snapshot, e NÃO DEVEM conter linha por
  anúncio (constitution IV: só agregados).

**Herança no município**

- **FR-007**: Para cada variante dos critérios de aluguel do Idealista, o município DEVE usar o próprio valor quando
  tiver n ≥ 10. Senão, DEVE usar o valor do seu distrito. Senão, o da sua região. Senão, fica ausente com motivo.
- **FR-008**: Todo valor herdado DEVE ser idêntico ao valor do nível de origem e DEVE vir marcado com origem herdada e
  o nível (`distrito` ou `regiao`).
- **FR-009**: A herança DEVE ser decidida por variante, de forma independente (`ALL`, cada tipologia e €/m²).
- **FR-010**: A cobertura própria do município (`propria`, `insuficiente`, `sem_anuncios`) DEVE continuar
  registrada, separada da origem do valor publicado. Um município sem amostra própria e com referência herdada NÃO
  DEVE ser apresentado só como "sem anúncios".
- **FR-011**: Os limites de normalização (P5/P95) dos critérios de aluguel DEVEM usar só valores próprios de
  município.

**Herança na freguesia**

- **FR-012**: O aluguel da freguesia DEVE seguir a cadeia freguesia (própria, regra FR-029 da 011) › município
  (próprio) › distrito › região, por variante, com o nível de origem marcado.
- **FR-013**: Um valor herdado na freguesia DEVE ser idêntico ao do nível de origem e NÃO DEVE contar como cobertura
  própria da freguesia.

**Qualidade, testes e documentação**

- **FR-014**: O mart de qualidade DEVE mostrar, por critério de aluguel e nível de território, quantos valores são
  próprios e quantos foram herdados de cada nível (município, distrito, região).
- **FR-015**: As tabelas novas DEVEM ter testes de chave, relacionamento com o CAOP, valores aceitos nos campos
  categóricos e faixa plausível da mediana (€100–€10.000).
- **FR-016**: DEVE existir um teste de dados que garanta que todo valor herdado é igual ao do nível de origem
  declarado.
- **FR-017**: A metodologia dos critérios de aluguel no catálogo DEVE descrever a cadeia de herança.
- **FR-018**: As tabelas novas DEVEM aparecer no dicionário de dados (spec 010) com as colunas descritas, e o
  notebook de exploração DEVE passar a ler o aluguel por distrito e região da Gold.

### Key Entities

- **Aluguel por distrito**: uma linha por distrito (ou ilha) × tipologia, com amostra, medidas e proveniência.
- **Aluguel por região**: uma linha por região da fonte × tipologia, com as mesmas medidas.
- **Hierarquia territorial**: município › distrito (ou ilha) › região da fonte, única por município.
- **Indicador de aluguel com origem**: valor publicado do município ou da freguesia, com origem (`proprio` ou
  herdado) e nível de origem (`freguesia`, `municipio`, `distrito` ou `regiao`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Todos os distritos (ou ilhas) e regiões com anúncios no snapshot vigente aparecem nas tabelas novas,
  e nenhuma mediana existe com menos de 10 elegíveis.
- **SC-002**: Com o snapshot de 2026-11, todos os 308 municípios têm valor em `custo_aluguel_mediana` `ALL`, próprio
  ou herdado. Os próprios continuam 42.
- **SC-003**: 100% dos valores herdados (município e freguesia) são idênticos ao valor do nível de origem declarado.
- **SC-004**: Os limites de normalização do aluguel não mudam em relação à 011, porque são calculados só com valores
  próprios.
- **SC-005**: Recalculadas por município com as mesmas regras, as medianas reproduzem a tabela municipal da 011 sem
  divergência. A regra de distrito e região é a mesma.
- **SC-006**: O build Gold completo passa localmente, com todos os testes de dados verdes.

## Assumptions

- O snapshot vigente é o de 2026-11. Distritos extraídos por município: Lisboa, Porto e Faro. Os demais vieram por
  distrito ou ilha.
- A região da fonte é estável entre snapshots. Se mudar, a regra de unicidade (FR-005) acusa.
- Herdar um valor declarado da área não é imputação: o valor existe, é da área, e a marca diz isso (constitution
  III, mesma lógica da herança município → freguesia da 011). A FR-012 da 011 ("anúncios só regionais não entram em
  agregados municipais") continua valendo: nenhum anúncio entra na mediana de um município ao qual não pertence.
- O protótipo do notebook (view `aluguel_regional`) é a referência de comportamento. A implementação na Gold é
  decidida no `sdd-plan`.

## Clarifications

### Sessão 2026-11-24

- Q: Na Gold, como o aluguel de distrito e região aparece para municípios sem mediana própria? → A: Tabelas novas
  por distrito e por região, mais herança marcada no indicador municipal (origem e nível), como a freguesia já herda
  do município.
- Q: Por qual fluxo? → A: Nova spec (012). A 011 fica convergida como está.
- Q: Quais anúncios entram na mediana do distrito? → A: Todos do distrito: os com município, somados ao distrito do
  município, e os que vieram só com o distrito.
- Q: Que região usar acima do distrito? → A: A região da fonte (Idealista), documentada como não oficial; NUTS II
  fica fora.
- Q: A herança vale por tipologia separadamente? → A: Sim. Cada variante pega o nível mais fino com n ≥ 10.
- Q: A normalização P5/P95 considera herdados? → A: Não, só valores próprios de município.
