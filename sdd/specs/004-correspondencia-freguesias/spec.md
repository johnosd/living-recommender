# Feature Specification: Correspondência de freguesias 2013→2025 — coleta das tabelas do INE e tabela de correspondência

**Slug**: `004-correspondencia-freguesias`

**Created**: 2026-11-12

**Status**: Convergida

**Input**: "vamos especificar então" a correspondência de freguesias 2013→2025 e o TopoJSON da CAOP, pendências deixadas fora pela spec 001 (ver `sdd/specs/001-ingestao-caop/spec.md`, Clarifications; `.docs/plano_plataforma_recomendacao_portugal.md` §5.4, §8.3 e o risco da reorganização de freguesias; `.docs/fontes_de_dados.md` §3.3, fonte `censos`). A entrevista decidiu que **esta spec cobre só a correspondência**; o TopoJSON fica para outra spec.

## Escopo

### Incluído

- **Catálogo de fonte**: entrada em `config/sources.yml` para as duas tabelas de correspondência publicadas pelo INE, com publicador, licença, atribuição, método, frequência (sob demanda), nível territorial (freguesia), URL de cada tabela e as colunas esperadas em cada uma. Uma tabela nova ou uma URL nova entra por mudança de catálogo, não de código.
- **Coleta das duas tabelas do INE**, guardadas como dado bruto imutável, com manifest e checksum por arquivo, no mesmo padrão das specs 001 a 003:
  - **Tabela A** (`CorrespondenciasAntes-Depois-R2013.xlsx`): freguesias **antes** da reorganização de 2013 → freguesias **da reorganização de 2013** (código e designação em cada geração).
  - **Tabela B** (`Codificação_FR_Repostas 2025_2013_Julho.xlsx`): freguesias **antes** de 2013 → freguesias **repostas em 2025** pela Lei n.º 25-A/2025 (código e designação em cada geração; 302 linhas).
- **Tabela de correspondência 2013→2025**, derivada das duas tabelas pelo código pré-2013: uma linha por par (freguesia de 2013, freguesia de 2025), com a **natureza da relação** (um-para-um, um-para-muitos, muitos-para-um, muitos-para-muitos), os sinais de **herança** e de **origem parcial**, as designações das duas gerações e os códigos pré-2013 que sustentam o par (rastro de evidência).
- **Verificação de cobertura contra a dimensão territorial** (`dim_parish`, spec 001, CAOP 2025): toda freguesia vigente tem origem na correspondência e todo código de 2013 tem destino. A falha **reprova a promoção** da tabela.
- **Relatório de cobertura**: contagens por natureza da relação e lista das freguesias que não são um-para-um, com códigos e nomes.
- **Execução** local e em S3 simulado, com o mesmo layout de chaves das specs anteriores; testes sem rede, com fixtures gravadas (versões reduzidas das duas planilhas).

### Fora de Escopo

- **TopoJSON** da CAOP (geometrias simplificadas para o mapa) e a publicação em `published/vN`. Vai para uma spec própria, perto da Fase 4 (site).
- **Repartição de valores** entre freguesias novas quando uma união de 2013 foi desfeita (pesos por área, por população ou pela BGRI 2021 do INE). Esta spec só **marca** a relação e a herança; aplicar pesos é decisão de uma spec futura.
- **Coletor dos Censos 2021** por freguesia (`censos`) e qualquer conversão de valores entre gerações de código. Esta spec entrega só a tabela de correspondência que o `censos` vai consumir.
- **Código pré-2013 como destino de consulta**: o código pré-2013 aparece apenas como rastro de evidência, não como chave de conversão de valores.
- **Versões da CAOP posteriores à 2025**: a correspondência cobre a divisão vigente hoje. Mudanças posteriores (uma fonte secundária, não verificada, cita cerca de 303 freguesias alteradas com efeito em 2026) ficam para uma entrega futura.
- **Interseção espacial** de geometrias de 2013 e 2025 e qualquer geometria de 2013.
- **Seed de sinônimos de nomes de freguesia** (Idealista, Wikipedia e outras grafias → `dicofre`) e a resolução de títulos de anúncios.
- **Deploy e agendamento**: Lambda, ECS, Terraform, MWAA.
- **Outras fontes**: Pordata/INE por município (spec 002), clima (spec 003), Idealista, AIMA, SNS, distâncias.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coletar as duas tabelas do INE com rastreabilidade (Priority: P1)

O operador (o autor do projeto) roda um comando que baixa as duas planilhas de correspondência publicadas pelo INE e guarda cada uma como dado bruto imutável. Um manifest registra, por arquivo, a origem, o horário da coleta, a licença, o checksum, o tamanho e o resultado. Antes de gravar, cada planilha é validada: precisa ser mesmo uma planilha, ter a estrutura e as colunas esperadas e conter códigos de freguesia de 6 caracteres. Se uma tabela falha, o motivo fica registrado e nada parcial dela entra no bruto.

**Why this priority**: sem as duas tabelas guardadas com checksum não há correspondência auditável. Esta story também protege contra o risco conhecido das fontes do INE: os links de download não têm estabilidade garantida e podem passar a devolver uma página HTML ou outro arquivo, o que não pode virar dado silenciosamente errado.

**Independent Test**: com um servidor simulado que entrega duas planilhas de fixture, rodar o comando num destino local vazio e conferir os dois brutos e o manifest. Rodar de novo e conferir que o estado é `unchanged` e nenhum bruto novo é gravado. Trocar uma das respostas por HTML e conferir a falha explícita, sem arquivo parcial.

**Acceptance Scenarios**:

1. **Given** um destino vazio e as duas tabelas do catálogo, **When** o operador executa a coleta, **Then** os dois brutos ficam gravados, separados por fonte, execução e tabela, e o manifest lista para cada um: origem, `sha256`, tamanho, licença, horário da coleta e status `changed`.
2. **Given** uma coleta anterior bem-sucedida e nenhuma mudança na fonte, **When** o operador coleta de novo, **Then** cada tabela é registrada como `unchanged` e nenhum bruto novo é gravado.
3. **Given** uma coleta anterior em que o conteúdo de apenas uma tabela mudou, **When** o operador coleta de novo, **Then** só o bruto dessa tabela é gravado como novo; a outra é `unchanged`.
4. **Given** uma resposta que é HTML, vazia, não é uma planilha, não tem a aba esperada ou não tem uma das colunas do catálogo, **When** a coleta roda, **Then** essa tabela é `failed` com o motivo, nenhum arquivo parcial dela fica no bruto e o comando termina com código de erro.
5. **Given** uma tabela que falhou numa execução, **When** a seguinte tem sucesso para ela, **Then** a falha anterior não impede que o novo estado seja aceito como o mais recente dessa tabela.

---

### User Story 2 - Tabela de correspondência 2013→2025 com a natureza da relação (Priority: P1)

A partir das duas tabelas vigentes, o sistema produz uma tabela de correspondência de freguesias de 2013 para 2025. Cada linha liga um código de 2013 a um código de 2025 e diz que tipo de relação é: a freguesia continuou igual, uma união de 2013 foi desfeita em várias freguesias, várias freguesias de 2013 viraram uma, ou uma combinação dos dois. Nos casos em que a freguesia nova nasce de uma união desfeita, a linha sinaliza que o valor de qualquer indicador de 2013 só pode ser **herdado**, não repartido. Quem consome (no futuro, o coletor `censos`) usa essa tabela para levar dados do código de 2013 ao código de 2025 sem lógica própria.

**Why this priority**: é o objetivo da feature e o pré-requisito dos indicadores por freguesia. Fica empatada com a US1 porque, sozinha, a US1 só entrega brutos; a US2 entrega o produto consumível.

**Independent Test**: com as duas planilhas de fixture (casos 1:1, uma união desfeita em 2 e em 3 freguesias, um caso muitos-para-um e uma freguesia "(parte)"), produzir a tabela e conferir linha a linha. Rodar de novo com as mesmas entradas e conferir que o resultado é idêntico.

**Acceptance Scenarios**:

1. **Given** uma freguesia que não mudou entre 2013 e 2025, **When** a correspondência é gerada, **Then** há uma única linha para ela, com a relação um-para-um e sem sinal de herança. Isso vale também quando só a designação mudou, caso em que a linha sinaliza a mudança de nome.
2. **Given** uma união de 2013 desfeita em 2025 em duas ou mais freguesias, **When** a correspondência é gerada, **Then** há uma linha por freguesia nova ligada ao mesmo código de 2013, a relação é um-para-muitos e cada linha sinaliza que o valor é **herdado**.
3. **Given** uma freguesia de 2025 formada por partes de mais de uma freguesia de 2013, **When** a correspondência é gerada, **Then** as linhas têm a relação muitos-para-um (ou muitos-para-muitos, se a freguesia de 2013 também se divide) e o relatório lista o caso para revisão.
4. **Given** uma freguesia anterior a 2013 registrada como "(parte)" na tabela do INE, isto é, incorporada só em parte, **When** a correspondência é gerada, **Then** as linhas que dependem dela sinalizam **origem parcial** e trazem os códigos pré-2013 como evidência.
5. **Given** uma freguesia anterior a 2013 que não aparece na tabela das repostas de 2025, **When** a correspondência é gerada, **Then** o código de 2025 dessa freguesia é o mesmo código que ela tem em 2013.
6. **Given** as mesmas duas tabelas de entrada, **When** a correspondência é gerada duas vezes, **Then** o resultado é idêntico (mesmas linhas, mesmos valores).

---

### User Story 3 - Cobertura contra a dimensão territorial, com reprovação (Priority: P2)

O operador precisa saber, antes de qualquer indicador por freguesia ser ligado, se a correspondência cobre toda a divisão vigente. O sistema compara a correspondência com a `dim_parish` (CAOP 2025) e **reprova a promoção** se houver uma freguesia vigente sem origem, um código de 2013 sem destino ou um destino que não exista na dimensão. Um relatório mostra as contagens por natureza da relação e lista as freguesias que não são um-para-um, com códigos e nomes.

**Why this priority**: o mesmo princípio dos municípios ("zero órfãos"). Sem essa trava, uma mudança futura de CAOP ou da tabela do INE faria o `censos` juntar dados a freguesias sem correspondência sem ninguém perceber. Fica abaixo da US2 porque a US2 já entrega a tabela; a US3 a protege.

**Independent Test**: com uma `dim_parish` de fixture e a correspondência de fixture, conferir a promoção e o relatório. Remover uma freguesia da correspondência (ou acrescentar uma à dimensão) e conferir que a promoção é reprovada com a lista do problema.

**Acceptance Scenarios**:

1. **Given** uma correspondência que cobre 100% das freguesias da dimensão, **When** a verificação roda, **Then** a tabela é promovida e o relatório mostra, por natureza da relação, quantos códigos de 2013 e de 2025 entram em cada categoria.
2. **Given** uma freguesia da `dim_parish` sem nenhuma origem na correspondência, **When** a verificação roda, **Then** a promoção é reprovada, a tabela anterior permanece intacta e a mensagem lista o código e o nome.
3. **Given** um código de 2013 da tabela do INE sem nenhum destino, **When** a verificação roda, **Then** a promoção é reprovada com a lista dos códigos.
4. **Given** um destino que não existe na `dim_parish`, **When** a verificação roda, **Then** a promoção é reprovada com a lista dos códigos.
5. **Given** o relatório gerado, **When** o operador o consulta, **Then** ele está num formato legível por pessoa, preservado junto da saída, com a data da coleta e a versão da CAOP da dimensão usada.

---

### Edge Cases

- **Link do INE deixa de funcionar ou muda de conteúdo:** resposta HTML, planilha com outra estrutura ou outro nome de aba → `failed` com o motivo (US1). Nunca vira dado silencioso.
- **Código com zeros à esquerda:** os códigos de freguesia são texto de 6 caracteres (`010103`), nunca número. Um código lido como número (zeros perdidos) é erro de validação, não correção silenciosa.
- **Linhas que não são dado** (cabeçalhos repetidos, legendas, rodapé, notas de designação alterada): ignoradas e contadas, sem virar par de correspondência.
- **Código pré-2013 que aparece duas vezes na tabela de 2013** (freguesia dividida entre duas de 2013, marcada "(parte)"): gera mais de um par e o sinal de origem parcial (US2). Não é duplicidade de dado.
- **Designação mudou, código não:** relação um-para-um com sinal de mudança de nome; o nome nunca é usado para decidir a relação.
- **Freguesia de 2025 de município diferente do de 2013:** se ocorrer, a linha sinaliza a mudança de município (os 4 primeiros dígitos do código); a promoção não reprova por isso.
- **Ilhas:** a reorganização de 2013 e a reposição de 2025 são tratadas pelas mesmas regras; as freguesias das ilhas entram na verificação de cobertura como as do continente.
- **Duas tabelas em estados incompatíveis** (uma coletada em data diferente da outra, ou uma `failed`): a correspondência só é gerada quando as duas têm estado vigente válido; senão a derivação não roda e informa qual tabela falta.
- **Nova versão da CAOP sem a tabela correspondente do INE:** a verificação de cobertura reprova a promoção (US3). Não há tentativa de inferir a correspondência.
- **Reprocessamento:** reexecutar a derivação com as mesmas entradas reproduz a mesma tabela; um bruto novo e válido substitui o estado vigente só depois da verificação.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O catálogo DEVE declarar a fonte das duas tabelas com publicador, responsável, licença, atribuição, método de coleta, frequência (sob demanda), nível territorial, URL de cada tabela e as colunas esperadas em cada uma. O sistema DEVE recusar qualquer coleta de fonte ou tabela fora do catálogo e DEVE validar o catálogo antes de qualquer acesso à rede.
- **FR-002**: O sistema DEVE coletar as duas tabelas e gravá-las como dado bruto imutável, separadas por fonte, execução e tabela, sem alterar um byte do conteúdo recebido.
- **FR-003**: O sistema DEVE registrar um manifest com, para cada tabela: origem, horário da coleta em UTC, licença, `sha256`, tamanho em bytes e status (`changed`, `unchanged`, `failed`); no caso `failed`, o motivo.
- **FR-004**: Se o conteúdo de uma tabela for igual ao do último estado válido dessa mesma tabela, o sistema DEVE registrar `unchanged` e NÃO DEVE gravar bruto novo. O estado vigente DEVE ser independente por tabela.
- **FR-005**: O sistema DEVE validar cada tabela antes de aceitá-la: ser uma planilha legível, ter a aba esperada e as colunas do catálogo (lidas pelo rótulo, não pela posição) e conter códigos de freguesia de 6 caracteres. Uma tabela reprovada DEVE ser `failed` com o motivo, sem arquivo parcial no bruto e sem impedir a coleta da outra.
- **FR-006**: O sistema DEVE tratar os códigos de freguesia como texto de 6 caracteres e DEVE contar e ignorar as linhas que não são dado (cabeçalhos repetidos, legendas, rodapé), sem convertê-las em pares.
- **FR-007**: O sistema DEVE derivar a correspondência 2013→2025 ligando as duas tabelas pelo código pré-2013. Uma freguesia pré-2013 que não consta na tabela das repostas de 2025 DEVE manter em 2025 o código que tem em 2013.
- **FR-008**: A tabela de correspondência DEVE ter uma linha por par único (código de 2013, código de 2025), com: código e designação de 2013, código e designação de 2025, natureza da relação, sinal de herança, sinal de origem parcial, sinal de mudança de nome, sinal de mudança de município e os códigos pré-2013 que sustentam o par.
- **FR-009**: A natureza da relação DEVE ser calculada sobre os pares: **um-para-um** (o código de 2013 tem um só destino e o de 2025 uma só origem), **um-para-muitos** (um código de 2013 com mais de um destino), **muitos-para-um** (um código de 2025 com mais de uma origem) e **muitos-para-muitos** (os dois casos no mesmo conjunto de pares).
- **FR-010**: O sinal de **herança** DEVE ser verdadeiro nas linhas em que o código de 2025 nasce de um código de 2013 com mais de um destino. O sistema NÃO DEVE repartir valores nem calcular pesos nesta feature; a herança é apenas um sinal para quem consome.
- **FR-011**: O sinal de **origem parcial** DEVE ser verdadeiro nas linhas cuja evidência inclui uma freguesia pré-2013 marcada como incorporada só em parte nas tabelas do INE.
- **FR-012**: O sistema DEVE verificar a cobertura contra a `dim_parish` antes de promover a correspondência e DEVE reprovar a promoção se: (a) alguma freguesia da dimensão não tiver origem; (b) algum código de 2013 da tabela do INE não tiver destino; (c) algum destino não existir na dimensão. A reprovação DEVE listar os códigos (e nomes, quando conhecidos) e preservar a tabela promovida anteriormente.
- **FR-013**: O sistema DEVE gerar um relatório de cobertura legível por pessoa, preservado junto da saída, com: a contagem de pares e de códigos distintos de 2013 e de 2025, a contagem por natureza da relação, a lista das freguesias que não são um-para-um (com códigos e nomes), as contagens dos sinais de herança, origem parcial, mudança de nome e mudança de município, a versão da CAOP da dimensão e a data da coleta.
- **FR-014**: A derivação DEVE ser determinística: as mesmas duas tabelas e a mesma dimensão produzem sempre a mesma correspondência e o mesmo relatório.
- **FR-015**: O sistema DEVE só gerar a correspondência quando as duas tabelas tiverem estado vigente válido; senão DEVE informar qual tabela falta ou está inválida e não gerar saída.
- **FR-016**: O sistema NÃO DEVE alterar `dim_parish`, `dim_municipality` nem os dados de outras fontes; isso DEVE ser comprovado por comparação de checksums antes e depois da execução.
- **FR-017**: O operador DEVE poder executar a coleta e a derivação por comandos locais e DEVE receber ao final um resumo com a contagem por status e por natureza da relação e o caminho do manifest e do relatório. A execução em S3 simulado DEVE usar o mesmo layout de chaves do local.
- **FR-018**: Os testes DEVEM rodar sem rede, usando fixtures gravadas (versões reduzidas das duas planilhas e uma `dim_parish` mínima) que contenham os casos um-para-um, união desfeita, muitos-para-um, "(parte)" e mudança de nome.
- **FR-019**: A atribuição da fonte ("Instituto Nacional de Estatística, IP – Portugal") DEVE constar no catálogo, no manifest e no relatório.

### Key Entities *(include if feature involves data)*

- **Tabela de correspondência do INE (bruta)**: uma das duas planilhas coletadas. Atributos: tabela (A ou B), origem, `sha256`, tamanho, licença, horário da coleta, status.
- **Freguesia por geração**: um código de 6 caracteres e uma designação em uma das três gerações (anterior a 2013, 2013, 2025). O código de 2025 é o `dicofre` de `dim_parish`.
- **Par de correspondência**: liga um código de 2013 a um código de 2025. Atributos: designações das duas gerações, natureza da relação, sinais de herança, origem parcial, mudança de nome e mudança de município, e os códigos pré-2013 de evidência.
- **Relatório de cobertura**: contagens por natureza da relação, lista das freguesias não um-para-um, resultado da verificação contra `dim_parish`, versão da CAOP e data da coleta.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% das freguesias da `dim_parish` (3.259 na CAOP 2025 local) têm ao menos uma origem na correspondência e 100% dos códigos de 2013 da tabela do INE têm ao menos um destino. Qualquer diferença reprova a promoção.
- **SC-002**: O relatório de cobertura sobre as tabelas reais reproduz as contagens verificadas na pesquisa de 2026-11-12 (2.957 códigos de 2013 com um só destino; 135 com mais de um; 1 código de 2025 com mais de uma origem), ou explica a divergência por uma mudança na fonte.
- **SC-003**: Uma segunda coleta sem mudança na fonte não grava nenhum bruto novo (todas as tabelas `unchanged`), e a derivação repetida produz uma tabela idêntica.
- **SC-004**: Em 100% dos casos de tabela inválida testados (HTML, vazia, não planilha, aba ausente, coluna ausente, código fora do formato), a tabela é `failed` com o motivo e nenhum arquivo parcial fica no bruto.
- **SC-005**: Dado qualquer conjunto de códigos de freguesia de 2013 existentes na tabela do INE, 100% são convertidos para um ou mais códigos de 2025 numa única consulta à tabela, e cada resultado informa se o valor é herdado.
- **SC-006**: A execução da feature não altera nenhum dos arquivos de outras fontes e dimensões: os checksums de `dim_parish`, `dim_municipality` e das demais saídas são idênticos antes e depois.
- **SC-007**: A suíte da feature roda sem rede e passa em um ambiente limpo, junto da suíte existente, sem alterar o resultado dos testes das specs 001 a 003.

## Assumptions

- **Fonte verificada em 2026-11-12.** As duas tabelas estão no portal do INE e são citadas na nota da DGT sobre a CAOP2024.1: `https://smi.ine.pt/Versao/Download/9160` (`CorrespondenciasAntes-Depois-R2013.xlsx`, 205 KB, 4.266 linhas de dado, 4.260 códigos pré-2013 distintos e 3.092 códigos de 2013) e `https://smi.ine.pt/Versao/Download/10698` (`Codificação_FR_Repostas 2025_2013_Julho.xlsx`, 27 KB, 302 linhas). Os URLs de download não têm estabilidade garantida (por isso a US1 e o FR-005).
- **Regra das freguesias não repostas.** Uma freguesia pré-2013 ausente da tabela B mantém o código de 2013 em 2025. A pesquisa comprovou a regra: encadeadas as duas tabelas com ela, os 3.259 códigos resultantes coincidem com a `dim_parish` (nenhum a mais, nenhum a menos).
- **CAOP 2025.** A dimensão de referência é a `dim_parish` da spec 001, com 3.259 freguesias, gerada a partir da CAOP 2025.
- **Casos conhecidos.** A pesquisa encontrou 6 códigos pré-2013 marcados "(parte)" (na área de Lisboa, Loures, Amadora e na freguesia de Bicos) e 1 código de 2025 vindo de mais de uma freguesia de 2013 (Bicos). O plano confirma o enquadramento exato (muitos-para-um ou muitos-para-muitos).
- **Censos 2021 e códigos de 2013.** Assume-se que o Censos 2021 publica freguesias com os códigos de 2013; a BGRI 2021 segue a CAOP2020, o que é coerente, mas isso será validado na spec do `censos` e não nesta.
- **Licença.** Assume-se a mesma licença da fonte `ine` já catalogada (CC-BY-4.0), com a atribuição "Instituto Nacional de Estatística, IP – Portugal". O plano confirma a licença específica dessas duas planilhas.
- **Mudanças de 2026.** Uma fonte secundária cita cerca de 303 freguesias alteradas com efeito em 2026. Não foi verificada e está fora do escopo; se existir uma CAOP posterior à 2025, a verificação de cobertura reprova a promoção até que uma nova entrega estenda a correspondência.
- O operador roda os comandos localmente, com acesso à internet só para a coleta. Não há agendamento nesta feature.
- O volume é pequeno (milhares de linhas) e o custo recorrente desta feature é zero (local e S3 simulado); recursos AWS reais ficam sob o gate da constitution.

## Clarifications

### Sessão 2026-11-12

- Q: Qual o escopo da spec 004? → A: Só a correspondência de freguesias. O TopoJSON é outro trabalho, de outro consumidor (o mapa do site) e de outro momento (Fase 4), e vira outra spec. A correspondência é o que destrava o `censos`.
- Q: Quais gerações de código a tabela cobre? → A: 2013→2025 como contrato de consulta, com o código pré-2013 guardado apenas como rastro de evidência (para auditar a relação de volta às tabelas do INE). Pares completos entre as três gerações ficam de fora, por falta de consumidor hoje.
- Q: Como tratar as 135 uniões de 2013 desfeitas em 2025 (um-para-muitos)? → A: Marcar a relação e a herança, sem pesos. A freguesia nova herda o valor da união e é sinalizada como herdada (plano §8.3). Repartir por área, por população ou pela BGRI 2021 fica para uma spec futura.
- Q: Como as tabelas entram no projeto? → A: Como fonte catalogada em `config/sources.yml`, com bruto imutável, checksum e manifest, como as demais fontes. Descartado o seed CSV gerado uma vez: sem manifest, sem detecção de mudança na fonte e com dado versionado no Git.
- Q: O que acontece se a correspondência não cobrir a `dim_parish` por completo? → A: Reprova o build, na linha do "zero órfãos" dos municípios. Um relatório lista as contagens por natureza da relação.
- Q: Como tratar uma CAOP posterior à 2025? → A: A spec cobre só a CAOP 2025. A regra de cobertura reprova a promoção diante de uma versão nova, em vez de errar em silêncio; estender a correspondência é outra entrega. Versionar a tabela por versão da CAOP foi descartado por falta de evidência de que a versão de 2026 exista e de consumidor hoje.

### Pesquisa prévia (2026-11-12)

- A pesquisa encontrou que o INE publica duas tabelas oficiais de correspondência (citadas em `alteracoes_CAOP2024.1.pdf`, da DGT). Foram baixadas e inspecionadas: a tabela A tem colunas `Código`, `Freguesias antes da Reorganização`, `Freguesias - Reorganização de 2013` e `Código Novo`; a tabela B tem `Código - Freguesias antes da reorganização administrativa de 2013`, `Designação - ...`, `Designação - Município`, `Código - Freguesias repostas em 2025` e `Designação - Freguesias repostas em 2025`.
- Encadeadas pelo código pré-2013, as duas tabelas geram 3.259 códigos de 2025 que coincidem 100% com a `dim_parish` local: 2.957 códigos de 2013 com um só destino, 135 uniões de 2013 desfeitas (2 a 4 destinos) e 1 código de 2025 vindo de duas freguesias de 2013. Não foi preciso cruzar geometrias.
- Não verificado: a licença específica das planilhas, o uso dos códigos de 2013 pelo Censos 2021 e as mudanças de 2026.
