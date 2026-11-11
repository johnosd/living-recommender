# Feature Specification: Ingestão de clima Open-Meteo — coleta diária por município e staging

**Slug**: `003-ingestao-clima-open-meteo`

**Created**: 2026-11-11

**Status**: Em Execução

**Input**: "planeje a ingestão dos dados de clima — referências: .docs/ e MPAlugueisLisboa" (ver `.docs/fontes_de_dados.md` §3.3 e §4, `.docs/plano_plataforma_recomendacao_portugal.md` §5.4, §8 e Fase 2, e o legado `src/Weather/` de MPAlugueisLisboa)

## Escopo

### Incluído

- **Catálogo de fonte**: entrada `open_meteo` em `config/sources.yml`, com publicador, licença, método, frequência, nível territorial, modelo de reanálise, janela de datas e lista declarada de variáveis diárias. Uma variável ou janela nova entra por mudança de catálogo, não de código.
- **Coleta do Open-Meteo (arquivo histórico)**: séries **diárias** dos **308 municípios**, consultadas no ponto representativo de cada um (`representative_lat`/`representative_lon` de `dim_municipality`, spec 001), numa **janela fixa de 24 meses completos e recentes** declarada no catálogo (valor inicial: 2024-11-01 a 2026-10-31). O bruto é guardado como veio da fonte, com rastreabilidade **por município**.
- **Variáveis do conjunto climatológico base** (13): temperatura média, máxima e mínima; sensação térmica média, máxima e mínima; precipitação; neve; duração de sol; vento médio e máximo; rajada máxima; umidade relativa média. Elas cobrem o que o score diário, os extremos e o TCI do legado (`weatherClassifier.py`) consomem.
- **Coleta retomável e ciente da cota**: a coleta respeita os limites do plano gratuito do Open-Meteo, para de forma limpa e registra os municípios pendentes quando a cota se esgota, e a execução seguinte continua dos pendentes, sem refazer o que já foi gravado.
- **Staging diário em formato longo**: uma linha por município (`dico`), variável e dia, com valor, unidade e proveniência.
- **Relatório de cobertura**: por variável, quantos dos 308 municípios têm série completa na janela, quais têm lacunas e quais não foram coletados.
- **Execução** local e em S3 simulado, com o mesmo layout de chaves das specs 001 e 002; testes sem rede, com fixtures gravadas.

### Fora de Escopo

- **World Weather Online (WWO)**: coletor novo, chave de API e backfill dos 309 CSV legados (2024-06 → 2025-06). Entram, se necessário, numa spec própria. O WWO fica como fallback só no papel (`.docs/fontes_de_dados.md` §4).
- **Cálculos climáticos**: score diário, classes (Excelente…Marginal), eventos extremos, TCI, normais mensais e médias sazonais. É a camada Silver/Gold seguinte; esta spec termina no staging.
- **Freguesia**: coleta por ponto de freguesia. Multiplica as chamadas por ~15 e esbarra na cota gratuita; só entra depois, e depende da correspondência 2013→2025.
- **Séries longas** (10 ou 30 anos): a janela fixa de 24 meses é a decisão desta spec. Ampliar a janela é mudança de catálogo e de planejamento de cota, não de código.
- **Índice UV diário**: não existe no arquivo diário do Open-Meteo; o `uv_extremo` do legado não é reproduzido nesta spec.
- **Dados horários**, previsão do tempo e dados de estações (por exemplo, IPMA).
- **Pivot para base larga** do legado, `formatar_numericos` e imputação de qualquer tipo.
- **Deploy e agendamento**: Lambda, ECS, Terraform, MWAA e execução trimestral automática.
- **Outras fontes**: Pordata/INE (spec 002), Wikipedia, Censos, AIMA, SNS, Idealista e distâncias.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coletar o clima diário dos 308 municípios com rastreabilidade (Priority: P1)

O operador (o autor do projeto) roda um comando que, para cada município da dimensão da spec 001, consulta o Open-Meteo no ponto representativo e na janela do catálogo, e guarda cada resposta como dado bruto imutável. Um manifest registra, por município, de onde veio a resposta, quando foi coletada, a licença, o checksum, o modelo usado, as coordenadas pedidas e as devolvidas pela fonte, e o resultado. Se um município falha, os demais continuam sendo coletados e a falha fica registrada com o motivo.

**Why this priority**: o clima é um dos critérios centrais do configurador ("ameno / quente / fresco") e hoje só existe o WWO de um ano, com cobertura de nomes frágil. Sem o bruto rastreável para os 308 municípios não há staging nem camada de pontuação. Esta story também fixa o padrão de uma coleta **por unidade territorial**, diferente de Pordata/INE (por dataset).

**Independent Test**: com um servidor simulado e a dimensão de municípios da spec 001, rodar o comando num destino local vazio e conferir os 308 brutos e o manifest. Rodar de novo e conferir que nenhum município é reconsultado ("nada a coletar"); pedir a recoleta explícita e conferir que tudo é `unchanged`, sem arquivos novos. Fazer um município falhar e conferir que os outros 307 foram gravados.

**Acceptance Scenarios**:

1. **Given** um destino vazio e os 308 municípios da dimensão, **When** o operador executa a coleta de clima, **Then** os 308 brutos ficam gravados, separados por fonte, execução e município (`dico`), e o manifest lista para cada um: `dico`, coordenadas pedidas e devolvidas, janela, modelo, `sha256`, tamanho, licença, horário da coleta e status `changed`.
2. **Given** uma coleta anterior bem-sucedida de todos os municípios, **When** o operador coleta de novo sem pedir recoleta, **Then** nenhum município é consultado na fonte, nenhum bruto novo é gravado e o comando informa que não há nada a coletar.
   **Given** a mesma coleta anterior e nenhuma mudança na fonte, **When** o operador pede a recoleta explícita, **Then** cada município é consultado e registrado como `unchanged`, e nenhum bruto novo é gravado.
3. **Given** uma coleta anterior em que a resposta de apenas um município mudou, **When** o operador pede a recoleta explícita, **Then** só o bruto desse município é gravado como novo; os demais são `unchanged`.
4. **Given** um município cuja resposta vem vazia, com HTML, sem uma das variáveis do catálogo ou com número de dias diferente do esperado, **When** a coleta roda, **Then** esse município é `failed` com o motivo, nenhum arquivo parcial dele fica no bruto, os outros são gravados e o comando termina com código de erro.
5. **Given** um município que falhou numa execução, **When** a seguinte tem sucesso para ele, **Then** a falha anterior não impede o novo estado de ser aceito como o mais recente desse município.

---

### User Story 2 - Retomar a coleta respeitando a cota gratuita (Priority: P2)

O plano gratuito do Open-Meteo limita as chamadas por minuto, hora e dia, e uma requisição que cobre mais de duas semanas ou mais de dez variáveis pesa mais de uma chamada. Estimam-se dezenas de milhares de chamadas para 308 municípios × 24 meses × 13 variáveis (a medir no plano), acima do limite diário. Quando a cota se esgota, o operador roda o mesmo comando outra vez e a coleta continua dos municípios pendentes, sem repetir os que já foram gravados.

**Why this priority**: sem retomada, uma execução interrompida na cota descarta o trabalho e pode nunca completar o conjunto. Fica abaixo da US1 porque a US1 já entrega valor com uma cota suficiente (ou com poucos municípios); a retomada é o que garante que a cobertura de 308 se feche na prática.

**Independent Test**: com um servidor simulado que passa a responder "limite excedido" depois de N municípios, rodar o comando e conferir que ele para de forma limpa com N gravados e o restante listado como pendente. Rodar de novo com a cota liberada e conferir que só os pendentes foram coletados.

**Acceptance Scenarios**:

1. **Given** uma cota que se esgota depois de N municípios, **When** a coleta roda, **Then** ela para sem tentar os municípios restantes, grava o manifest com os N concluídos e os pendentes como `pending` (motivo: cota), e o comando termina com um código distinto de sucesso e de falha de dado.
2. **Given** uma execução anterior que deixou municípios `pending`, **When** o operador roda o comando de novo, **Then** só os pendentes são consultados; os já gravados, mesmo sem mudança, não geram nova chamada à fonte.
3. **Given** o limite por minuto ou por hora atingido, **When** a coleta roda, **Then** ela espera e continua, por um número limitado de esperas por município; só o limite diário esgotado interrompe a execução de imediato.
   **Given** o limite por minuto ou por hora que persiste depois das esperas, ou o operador que optou por não esperar, **When** a coleta roda, **Then** ela trata o caso como cota esgotada: para, registra os restantes como `pending` e termina com o código de saída de pendência por cota.
4. **Given** todos os municípios coletados numa ou mais execuções, **When** o operador consulta o estado, **Then** o conjunto completo equivale a uma coleta de uma só vez: 308 municípios com estado vigente `changed` e a mesma janela.
5. **Given** a opção de limitar a execução a uma quantidade de municípios, **When** o operador a usa, **Then** só essa quantidade de municípios pendentes é consultada, para controlar o gasto da cota.

---

### User Story 3 - Staging diário por município com o código oficial (Priority: P2)

A partir do último estado válido de cada município, o operador executa a transformação e obtém uma tabela em formato longo em que cada linha é uma observação de um município (`dico`), de uma variável, de um dia, com valor, unidade e proveniência. Como a fonte é consultada pelas coordenadas do `dico`, o município já nasce resolvido, sem tabela de sinônimos.

**Why this priority**: o staging em formato longo é o contrato com a camada seguinte (cálculo de score, extremos e TCI) e com o `stg_observation` das specs anteriores. Depende da US1 só pela existência do bruto. Está no mesmo nível da retomada porque ambas são necessárias para o conjunto ser utilizável.

**Independent Test**: com brutos de fixture e a dimensão da spec 001, rodar a transformação e conferir que todo `dico` existe na dimensão, que não há linhas duplicadas, que as unidades estão presentes e que um município sem bruto válido é reportado, não preenchido.

**Acceptance Scenarios**:

1. **Given** o último estado válido de todos os municípios, **When** a transformação roda, **Then** a saída traz uma linha por município, variável e dia, com `dico`, valor, unidade, modelo e proveniência (fonte, execução, licença, janela).
2. **Given** um valor ausente (`null`) numa variável e dia, **When** a transformação roda, **Then** ele permanece ausente e nunca vira zero nem é estimado ou interpolado.
3. **Given** um município sem bruto válido (nunca coletado, `failed` ou `pending`), **When** a transformação roda, **Then** ele não gera linhas e é listado como ausente, e a transformação informa quantos municípios foram incluídos de 308.
4. **Given** a data de cada observação, **When** a transformação roda, **Then** o dia é o dia calendário do município, sem deslocamento causado por fuso horário (Açores e Madeira inclusive).
5. **Given** a precipitação, a neve e a duração de sol, **When** a transformação roda, **Then** as unidades da fonte (mm, cm, s ou h etc.) são preservadas como declaradas, sem conversão silenciosa.

---

### User Story 4 - Relatório de cobertura climática (Priority: P3)

Ao fim da transformação, o operador recebe um relatório que diz, por variável, quantos dos 308 municípios têm a série completa na janela, quais têm lacunas (e quantos dias faltam) e quais não foram coletados.

**Why this priority**: torna a ausência visível desde o staging (constitution III) e permite saber se a camada seguinte pode confiar no clima antes de calcular qualquer score. Não bloqueia a coleta nem o staging.

**Independent Test**: com fixtures em que alguns municípios têm dias faltantes ou não foram coletados, rodar a transformação e conferir as contagens e as listas.

**Acceptance Scenarios**:

1. **Given** uma variável com série completa em 300 municípios, lacunas em 3 e 5 não coletados, **When** o relatório é gerado, **Then** ele informa 300 completos, 3 com lacuna (com os dias faltantes de cada um) e 5 não coletados, com códigos e nomes.
2. **Given** o relatório gerado, **When** o operador o consulta, **Then** ele está num formato legível por pessoa e preservado junto da saída, com a janela, o modelo e a data da coleta.
3. **Given** um município cujo ponto devolvido pela fonte difere do ponto pedido acima de um limite, **When** o relatório é gerado, **Then** o município aparece sinalizado com a distância, para revisão (caso típico: município costeiro ou de ilha cujo ponto cai numa célula de mar).

---

### Edge Cases

- **Limite diário esgotado no meio da coleta:** a execução para sem erro de dado, registra os pendentes e é retomável (US2).
- **Resposta de erro do Open-Meteo em um município** (HTTP 4xx/5xx, JSON de erro, corpo vazio): `failed` com o motivo; os outros seguem. Erros transitórios têm retentativa com espera crescente antes de falhar.
- **Variável toda nula ou ausente da resposta:** reprova o município; uma variável ocasionalmente `null` em alguns dias não reprova, mas aparece na cobertura.
- **Dados recentes preliminares:** os últimos meses da janela podem vir de uma reanálise preliminar e ser revisados depois. Uma revisão muda o `sha256`, o município vira `changed` com bruto novo, e o anterior permanece (constitution V).
- **Município de ilha ou costeiro:** o ponto representativo está dentro do polígono, mas a célula da reanálise pode ser mar ou ter elevação muito diferente. Isso não é corrigido nem substituído por outro município; coordenadas pedidas e devolvidas e a elevação da célula ficam registradas, e a divergência aparece na cobertura (US4).
- **Fuso horário:** Açores, Madeira e o continente têm fusos diferentes. O dia calendário deve ser o do município.
- **Metadados que variam a cada chamada** (por exemplo, o tempo de geração da resposta): não podem tornar um município `changed` sem que os dados tenham mudado.
- **Janela alterada no catálogo:** é um período novo de referência; nada do período anterior é sobrescrito ou apagado.
- **Execução concorrente:** cada execução grava num prefixo próprio e não corrompe outra; o `unchanged` compara com o último estado válido do município.
- **Dimensão de municípios ausente ou diferente de 308:** a coleta recusa a execução antes de qualquer chamada à fonte.
- **Diretório local inexistente:** é criado automaticamente. Um bruto já existente nunca é sobrescrito.

## Requirements *(mandatory)*

### Functional Requirements

**Catálogo e coleta**

- **FR-001**: O sistema DEVE registrar `open_meteo` no catálogo de fontes (`config/sources.yml`) com identificador, publicador, licença, método de coleta, frequência e nível territorial. A entrada DEVE declarar o modelo de reanálise, a janela de datas (início e fim), a lista de variáveis diárias com suas unidades esperadas e os limites de taxa conhecidos.
- **FR-002**: O coletor DEVE recusar a execução de uma fonte, variável ou janela que não esteja no catálogo (constitution IV).
- **FR-003**: Toda requisição DEVE enviar um User-Agent identificado do projeto, respeitar um tempo limite, limitar a taxa abaixo dos limites por minuto e por hora da fonte e fazer retentativas com espera crescente (constitution IV).
- **FR-004**: O sistema DEVE consultar cada um dos 308 municípios no ponto representativo (`representative_lat`/`representative_lon`) de `dim_municipality`, e NÃO DEVE consultar por nome de município. A coleta DEVE recusar a execução se a dimensão não estiver disponível ou não tiver 308 municípios.
- **FR-005**: O sistema DEVE gravar o bruto de cada município como veio da fonte, separado por fonte, execução e município, sem nunca sobrescrever um bruto existente (constitution V).
- **FR-006**: Toda execução DEVE gerar um manifest com `source_id`, `run_id`, método, horário da coleta em UTC, licença, modelo, janela e, **para cada município**: `dico`, coordenadas pedidas, coordenadas e elevação devolvidas pela fonte, status (`changed`, `unchanged`, `failed` ou `pending`), `sha256`, tamanho em bytes e mensagem de erro (quando `failed` ou `pending`).
- **FR-007**: Se o conteúdo de um município for igual ao do último estado válido desse mesmo município, o sistema DEVE registrar `unchanged` e NÃO DEVE gravar bruto novo (constitution V). A comparação DEVE ignorar os metadados da resposta que variam a cada chamada sem que os dados mudem. O estado vigente é independente por município.
- **FR-008**: Uma falha em um município DEVE ser registrada no manifest com o motivo, NÃO DEVE deixar arquivo parcial dele no bruto e NÃO DEVE impedir a coleta dos demais. O comando DEVE terminar com código de erro se algum falhar.
- **FR-009**: O sistema DEVE validar cada bruto antes de aceitá-lo: não vazio, não HTML nem JSON de erro, com todas as variáveis do catálogo, com a unidade esperada de cada variável e com exatamente os dias da janela. Um bruto reprovado nunca vira novo estado vigente.
- **FR-010**: O destino DEVE ser selecionável entre local e S3 com a mesma lógica e o mesmo layout de chaves. O modo local NÃO DEVE exigir credenciais, e nenhuma credencial DEVE ser lida de arquivo versionado (constitution I). A coleta NÃO DEVE exigir chave de API.
- **FR-011**: O operador DEVE poder executar a coleta por um comando único e DEVE receber ao final um resumo com a contagem por status, a lista de falhas e pendentes e o caminho do manifest.

**Cota e retomada**

- **FR-012**: Ao receber a indicação de limite diário esgotado, o sistema DEVE parar de consultar a fonte, registrar no manifest os municípios restantes como `pending` (motivo: cota) e terminar com um código de saída distinto de sucesso e de falha de dado. Esgotamento dos limites por minuto ou por hora DEVE gerar espera limitada (um número máximo de esperas por município) e a coleta continua; se o limite persistir depois das esperas, ou se o operador optar por não esperar, o caso é tratado como cota esgotada, com os mesmos `pending` e o mesmo código de saída.
- **FR-013**: Em uma nova execução, o sistema DEVE consultar apenas os municípios sem estado vigente `changed` para a mesma janela e modelo. Um município com estado vigente DEVE ser ignorado sem chamada à fonte, a menos que o operador peça uma recoleta explícita.
- **FR-014**: O sistema DEVE permitir ao operador limitar a execução a um número máximo de municípios, para controlar o gasto de cota.
- **FR-015**: O manifest DEVE permitir saber, a partir de uma ou várias execuções, quais municípios estão completos para a janela vigente e quais faltam.

**Staging e qualidade**

- **FR-016**: O sistema DEVE produzir um staging em formato longo a partir do último estado válido de cada município, com: `dico`, variável, data, valor, unidade, modelo e proveniência (fonte, execução, licença, janela). Município e variável DEVEM seguir os nomes do catálogo.
- **FR-017**: Valores ausentes DEVEM permanecer ausentes. Nenhum valor DEVE ser inventado, interpolado, preenchido com o de outro município nem convertido em zero (constitution III).
- **FR-018**: O dia de cada observação DEVE ser o dia calendário do município, sem deslocamento por fuso horário, e a data DEVE ser armazenada como data, não como texto formatado por locale.
- **FR-019**: Testes de qualidade DEVEM verificar: unicidade da chave (município, variável, data), todo `dico` existente na dimensão da spec 001, valores numéricos válidos quando presentes, valores dentro de faixas físicas plausíveis (por exemplo, umidade entre 0 e 100, precipitação não negativa, temperatura mínima ≤ máxima), unidade e data presentes. Uma falha DEVE interromper a execução.
- **FR-020**: O sistema DEVE gerar um relatório de cobertura por variável com: municípios com série completa na janela (de 308), municípios com lacuna (com os dias faltantes), municípios não coletados (com código e nome) e municípios com divergência entre o ponto pedido e o devolvido acima de um limite.
- **FR-021**: Todo staging DEVE carregar fonte, período de referência (janela) e licença (constitution III).
- **FR-022**: O sistema DEVE registrar no catálogo, no manifest e em cada linha do staging a licença e a atribuição da fonte: CC BY 4.0, com a citação "Dados meteorológicos: Open-Meteo.com" e a indicação de que o dado foi modificado quando houver agregação. A restrição de uso não comercial do plano gratuito DEVE constar como risco aceito pelo autor, registrado no plano (constitution IV), com a mitigação e o gate para migrar a um plano comercial.
- **FR-023**: Toda a lógica de coleta, validação, retomada por cota, staging e cobertura DEVE ser testável sem acesso à rede, com fixtures gravadas (constitution, Quality Gates).

### Key Entities *(include if feature involves data)*

- **Fonte**: `open_meteo`, com publicador, licença, método, frequência, nível territorial, modelo e janela.
- **Variável diária**: uma grandeza climática do catálogo, com identificador, unidade esperada e descrição.
- **Execução (run)**: uma tentativa de coletar a fonte, com `run_id` e horário; pode concluir parte dos municípios.
- **Manifest**: o registro auditável de uma execução, com o resultado de cada município.
- **Arquivo bruto**: os bytes como vieram da fonte para um município, imutáveis, por fonte, execução e município.
- **Estado vigente de um município**: o último bruto aceito (`changed`) daquele município para a janela e o modelo atuais, independente dos outros.
- **Ponto de consulta**: as coordenadas pedidas (do ponto representativo) e as devolvidas pela fonte, com a elevação da célula.
- **Observação diária (staging)**: uma linha em formato longo: município (`dico`), variável, data, valor, unidade, modelo e proveniência.
- **Relatório de cobertura**: por variável, a contagem e a lista de municípios completos, com lacuna, não coletados e com ponto divergente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Num ambiente limpo, repetir o comando de coleta até não haver pendentes termina com os 308 municípios no estado vigente. Uma execução seguinte, sem recoleta explícita, não consulta a fonte e informa que não há nada a coletar; uma recoleta explícita, sem mudança na fonte, termina com todos `unchanged` e nenhum arquivo bruto novo.
- **SC-002**: Quando um município falha, 100% dos demais são coletados normalmente, 100% dos falhos têm o motivo no manifest, e nenhum arquivo parcial permanece no bruto.
- **SC-003**: Quando a cota se esgota, a execução termina de forma limpa em 100% dos casos testados, com os pendentes listados, e a execução seguinte consulta somente os pendentes (0 chamadas repetidas).
- **SC-004**: Em 100% das linhas do staging, `dico` existe na dimensão de 308 municípios e a chave (município, variável, data) é única; nenhum valor ausente na fonte aparece como zero ou estimado.
- **SC-005**: Para a janela de 24 meses, cada município completo tem exatamente os dias esperados para as 13 variáveis (730 dias na janela inicial), ou a lacuna aparece no relatório de cobertura.
- **SC-006**: As execuções com destino local e com destino S3 (simulado) produzem o mesmo conjunto de chaves e manifests equivalentes.
- **SC-007**: A suíte de testes da feature roda sem acesso à rede e passa no CI.
- **SC-008**: A primeira coleta real, feita em ambiente local, registra o total de chamadas gastas da cota, o número de execuções necessárias para completar os 308 municípios e a lista dos municípios com lacuna ou ponto divergente. Essa verificação manual é distinta da prova automatizada.

## Assumptions

- **Depende da spec 001** (convergida): usa `dim_municipality` (308 municípios, `dico`, ponto representativo), o padrão de coletor com dependências injetadas, os destinos local e S3 e o mesmo layout de chaves. **Reaproveita da spec 002** o estado vigente por unidade, o manifest com resultado por item, a comparação por impressão digital canônica e o esquema de observações longas; o que exigir adaptação (a unidade passa de dataset para município) é decisão do `sdd-plan`.
- **Janela:** 24 meses completos e recentes, fixa no catálogo, com valor inicial de 2024-11-01 a 2026-10-31 (a data de hoje é 2026-11-11, e a reanálise tem ~5 dias de atraso). Foi escolhida para refletir o clima atual de cada município, não uma normal de 30 anos. Atualizar a janela depois é mudança de catálogo e gera período novo.
- **Cota (a medir no plano):** pelas regras do plano gratuito (600 chamadas/minuto, 5.000/hora, 10.000/dia, 300.000/mês; requisições com mais de 2 semanas ou mais de 10 variáveis pesam mais de uma chamada), a estimativa é da ordem de 70 chamadas por município, cerca de 20 mil no total, isto é, alguns dias de cota diária. O valor real é medido na primeira coleta (SC-008).
- **Modelo de reanálise:** declarado no catálogo e registrado em cada manifest. A escolha entre ERA5 (~25 km), ERA5-Land (~11 km, melhor em relevo como Madeira e Serra da Estrela) e outra resolução é do `sdd-plan`, conforme a disponibilidade de cada uma das 13 variáveis.
- **Município apenas.** Freguesia fica fora; as freguesias herdam o clima do município e isso é sinalizado na camada seguinte.
- **O Open-Meteo é a única fonte** de clima desta spec. O WWO e os 309 CSV legados ficam preservados fora do pipeline.
- **O índice UV não faz parte do conjunto**; o `uv_extremo` do legado não é reproduzido (ver Fora de Escopo).
- **Licença:** os dados são CC BY 4.0 com atribuição obrigatória. O plano gratuito é só para uso não comercial; o autor aceitou o risco, como no Pordata (R-001), e a mitigação é migrar para um plano comercial caso o projeto entre na Fase B comercial.
- O operador roda os comandos localmente, com acesso à internet. Não há agendamento nesta feature; o ciclo trimestral virá com a orquestração.
- O volume é pequeno (cerca de 3 milhões de observações no staging) e o custo recorrente desta feature é zero (local e S3 simulado); recursos AWS reais ficam sob o gate da constitution.

## Clarifications

### Sessão 2026-11-11

- Q: Quais fontes de clima entram nesta spec? → A: Só o Open-Meteo, a fonte principal por decisão de 2026-11-03. O WWO (coletor novo e backfill dos CSV legados) fica fora.
- Q: Qual o ponto geográfico de cada município na consulta? → A: O ponto representativo de `dim_municipality` (spec 001), no nível município; freguesia fica fora por causa da cota.
- Q: Que período e granularidade o bruto guarda? → A: Séries diárias. A janela inicial escolhida foi de 10 anos, mas foi reduzida logo depois (ver abaixo).
- Q: Até onde a spec vai depois de gravar o bruto? → A: Raw + staging diário em formato longo + relatório de cobertura. Score diário, extremos, TCI e normais ficam para a camada Silver/Gold.
- Q: Quais variáveis entram? → A: O conjunto climatológico base, de 13 variáveis (temperatura, sensação térmica, precipitação, neve, sol, vento, rajada e umidade). Índice UV não existe no arquivo diário e fica de fora.
- Q: Como tratar a licença do Open-Meteo, cujo plano gratuito é só para uso não comercial? → A: Risco aceito, como no Pordata, com atribuição CC BY 4.0 e a mitigação de migrar para plano comercial na Fase B.
- Q: Quando o bruto é considerado novo? → A: Janela fixa declarada no catálogo. A mesma janela com os mesmos dados é `unchanged`; uma janela nova é um período novo.
- Q: Como lidar com a cota gratuita? → A: Pelo operador: "2 anos no máximo, com preferência para coletar todos os municípios". A coleta é retomável por município e sempre prioriza cobrir os 308 antes de ampliar qualquer coisa.
- Q: A janela de 10 anos convive com os 2 anos? → A: Não. A janela passa a ser de **2 anos completos e os mais recentes**, para refletir o clima atual de cada município. Valor inicial: 2024-11-01 a 2026-10-31.

### Sessão 2026-11-11 (sdd-plan)

- Q: A segunda execução, sem mudança na fonte, deve reconsultar os 308 municípios e registrar `unchanged` (US1/AC2, SC-001), ou pular os que já têm estado vigente (FR-013)? → A: Pular. Reconsultar custaria de novo toda a cota (~3 dias). Sem recoleta explícita, o comando não consulta a fonte e informa que não há nada a coletar; `unchanged` aparece quando o operador pede a recoleta explícita, para confirmar a fonte ou detectar revisões. US1/AC2–3 e SC-001 foram alinhados ao FR-013 (achado A-001 do Analyze).
- Q: Os limites por minuto e por hora devem gerar espera ilimitada (FR-012 original)? → A: Não: espera **limitada** por município. Persistindo o limite depois das esperas, ou se o operador optar por não esperar, o caso é tratado como cota esgotada (`pending` e o mesmo código de saída), o que mantém a execução retomável em vez de bloqueá-la por horas. FR-012 e US2/AC3 foram alinhados (achado A-002 do Analyze). Os números exatos de esperas são do plano (D5).
