# Feature Specification: Mobilidade — distâncias e tempos de viagem dos municípios até polos fixos

**Slug**: `009-mobilidade-distancias`

**Created**: 2026-11-21

**Status**: Convergência Pendente

**Input**: "escreva a feature para passar para outro modelo de IA executar" — próximo passo do backlog depois da integração das specs 005, 007 e 008: ingerir a mobilidade, único critério do catálogo do MVP ("Distância a capitais", plano §8.1) ainda sem dado. Referências: `.sdd/adr/ADR-002-arquitetura-base-mvp.md` (D8, atualização de 2026-11-03), `.sdd/adr/ADR-003-byok-apis-externas.md`, `.docs/fontes_de_dados.md` (linha `google_distances`, "Risco aceito" e pendências do §3.3) e `.docs/plano_plataforma_recomendacao_portugal.md` §8.1 e §15.

## Escopo

### Incluído

- **Catálogo de polos** (`config/poles.yml`): lista declarada e versionada dos pontos de referência. Cada polo tem identificador estável, nome, tipo (`cidade`, `aeroporto`, `sede_distrito`, `capital_regional`), coordenadas e a origem delas, e o grupo de roteamento ao qual pertence (`continente`, `madeira` ou `acores`). Polo novo ou alterado entra por mudança de catálogo, não de código. Os polos de tipo `cidade`, `sede_distrito` e `capital_regional` referenciam um município pelo `dico` e usam o ponto representativo da CAOP desse município; só os aeroportos levam coordenadas próprias.
- **Distância em linha reta (haversine)** do ponto representativo de **cada um dos 308 municípios** (`representative_lat`/`representative_lon` de `dim_municipality`, spec 001) até **cada polo** do catálogo. Não usa API, não exige chave nem rede.
- **Catálogo de fonte** da mobilidade em `config/sources.yml`: publicador (Google Maps Platform), licença, método, frequência (cálculo único), atribuição obrigatória ("Tempos de viagem: Google"), restrições dos termos de uso, o risco aceito e a alternativa documentada de substituição.
- **Cálculo único de carro pelo Google**, por CLI local rodada pelo operador: do ponto representativo de cada município até os polos **elegíveis** (ver FR-013), no modo `driving`. O bruto de cada resposta é guardado imutável, com manifest. **Decisão do autor (2026-11-21): o transporte público (`transit`) não é calculado agora.** O código aceita modos por catálogo, então habilitá-lo depois (com horário de partida fixo, dia útil, 08:00) é mudança de catálogo, e só os pares novos são cobrados.
- **Estimativa e teto antes de gastar**: a CLI calcula, sem chamar a API, o número de pares e de elementos que vai consultar, mostra a estimativa de custo e só consulta com confirmação explícita do operador e dentro de um teto de elementos por execução.
- **Retomada e idempotência**: uma execução interrompida (cota, erro, queda) continua só dos pares pendentes. Pares já gravados não são consultados de novo.
- **Staging em formato longo**: uma linha por município (`dico`), polo, modo e referência de cálculo, com `km`, `minutos`, estado do resultado e proveniência. A linha reta e os modos do Google compartilham o mesmo formato.
- **Relatório de cobertura**: por modo e por polo, quantos municípios têm valor, quantos ficaram sem rota (e por qual motivo), quantos pares estão pendentes.
- **Execução** local e em S3 simulado, com o mesmo layout de chaves das specs 001, 002, 003 e 008; testes sem rede, com fixtures gravadas.

### Fora de Escopo

- **Transporte público (`transit`)**: não é calculado agora (decisão do autor, 2026-11-21). O código o suporta por catálogo, mas o catálogo real só habilita `driving`.
- **Freguesias**: nenhuma distância por freguesia. A herança do valor municipal (sinalizada como herdada, constitution III) é decisão da camada de marts/ranker, não desta ingestão.
- **Seleção do "polo mais próximo"**, "aeroporto mais próximo", normalização, score e a entrada no `criteria_catalog`. É a camada Silver/Gold seguinte; esta spec termina no staging e no relatório.
- **Tempo de viagem por modo alternativo**: bicicleta, a pé, comboio por GTFS, motor de rotas próprio (`r5py` + OSM + GTFS da CP) ou OpenRouteService. Ficam registrados só como alternativa de substituição do Google.
- **Destino livre** escolhido pelo usuário (Fase B) e qualquer consulta em tempo de uso.
- **Google Places**, geocodificação (Google Geocoding está fora do projeto) e qualquer coordenada resolvida por nome.
- **Interface e publicação**: seletor de modo no site, exibição da atribuição, `published/vN`, `current.json`.
- **Deploy e agendamento**: Lambda, ECS, Terraform, MWAA. A coleta é local e única; não há execução periódica.
- **Dados de trânsito em tempo real** e variação por horário além do horário fixo declarado.
- **Chave de API do Google em qualquer arquivo versionado**, inclusive fixtures, exemplos e logs.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Distância em linha reta dos 308 municípios até os polos (Priority: P1)

O operador (o autor do projeto) mantém a lista de polos em `config/poles.yml` e roda um comando que calcula a distância em linha reta do ponto representativo de cada município até cada polo, grava o resultado como dado rastreável e valida a cobertura. Não há chave, API paga nem rede.

**Why this priority**: entrega sozinha o critério "Distância a capitais" em um dos três modos, sem custo, sem risco de termos de uso e sem depender de cota. Mesmo que a US2 nunca rode, o configurador já tem distância utilizável para todos os 308 municípios, inclusive Açores e Madeira.

**Independent Test**: com a dimensão de municípios da spec 001 e um `poles.yml` de fixture, rodar o comando em destino local vazio e conferir `308 × N polos` linhas. Conferir distâncias conhecidas (município até o próprio polo = 0 km; um par de referência com valor esperado dentro de tolerância). Rodar de novo e conferir que o resultado é `unchanged`.

**Acceptance Scenarios**:

1. **Given** os 308 municípios da dimensão e um catálogo de polos válido, **When** o operador executa o cálculo em linha reta, **Then** existem exatamente `308 × N` linhas, uma por município e polo, cada uma com `km` numérico não negativo, `mode = straight_line`, `status = ok` e proveniência (versão da CAOP, versão do catálogo de polos, método, `run_id`, horário).
2. **Given** um polo do tipo `sede_distrito`, `cidade` ou `capital_regional` que referencia o município X, **When** o cálculo roda, **Then** a distância de X até esse polo é 0 km, porque origem e destino usam o mesmo ponto representativo.
3. **Given** um polo que referencia um `dico` inexistente na dimensão, ou um aeroporto sem coordenadas, ou coordenadas fora do intervalo válido, ou identificadores de polo duplicados, **When** o cálculo roda, **Then** o catálogo é rejeitado **antes** de qualquer cálculo, com mensagem que nomeia o polo e o problema, e nenhuma saída é gravada.
4. **Given** um resultado anterior idêntico (mesmos municípios, mesma versão do catálogo de polos), **When** o cálculo roda de novo, **Then** o resultado é `unchanged` e nenhum bruto novo é gravado; se um polo for acrescentado, só os pares novos entram, e os anteriores são preservados.
5. **Given** os 308 municípios e os polos de todos os grupos de roteamento, **When** o cálculo roda, **Then** municípios dos Açores e da Madeira também têm distância em linha reta a todos os polos, inclusive os do continente.

---

### User Story 2 - Cálculo único de tempo e distância de carro (Priority: P2)

O operador roda a CLI local que consulta o Google para os pares elegíveis (município → polo), no modo carro, uma única vez (os modos habilitados vêm do catálogo; hoje só `driving`). Antes de gastar, a CLI mostra quantos elementos vai consultar e a estimativa de custo e pede confirmação. Cada resposta é guardada como bruto imutável. Se a cota ou a conexão falha no meio, o operador roda o mesmo comando e ele continua dos pares pendentes.

**Why this priority**: o tempo de carro complementa a linha reta no critério de distância; o transporte público, que o ADR-002 D8 também previa na v1, ficou para depois por decisão do autor. Fica abaixo da US1 porque tem custo, depende de chave, de cota e de um risco de termos aceito, e porque a US1 já entrega valor sozinha.

**Independent Test**: com um servidor simulado do Google (fixtures de respostas gravadas, incluindo erros) e um catálogo pequeno, rodar a CLI em modo de estimativa e conferir que **nenhuma** chamada é feita; rodar com confirmação e conferir brutos, manifest e staging; interromper no meio (falha simulada) e retomar conferindo que só os pendentes são consultados.

**Acceptance Scenarios**:

1. **Given** municípios, polos elegíveis e nenhuma chave configurada, **When** o operador pede a estimativa, **Then** a CLI informa pares, elementos por modo, total e custo estimado, sem exigir chave e sem rede.
2. **Given** a ausência da chave no `.env` local ou no SSM, **When** o operador tenta consultar de fato, **Then** a CLI falha antes de qualquer chamada, com mensagem que diz onde configurar a chave, sem imprimir valor algum de segredo.
3. **Given** uma estimativa acima do teto de elementos por execução declarado, **When** o operador tenta consultar, **Then** a CLI recusa e informa o teto e a estimativa; só um teto maior, passado explicitamente, permite prosseguir.
4. **Given** uma consulta confirmada, **When** a CLI roda, **Then** cada par e modo é consultado, o bruto é guardado como veio, e o manifest registra: `dico`, polo, modo, coordenadas pedidas e as devolvidas pela fonte, horário de partida usado, `sha256`, tamanho, horário da coleta, licença e status.
5. **Given** uma execução interrompida depois de parte dos pares, **When** o operador roda de novo o mesmo comando, **Then** só os pares sem resultado gravado são consultados; os já gravados não geram nova chamada.
6. **Given** um par sem rota possível (ilhas diferentes, destino inalcançável, `ZERO_RESULTS`, rota excede o limite da API, sem transporte público), **When** a CLI processa a resposta, **Then** o par é gravado com `km` e `minutos` nulos, `status` com o motivo e uma bandeira de "sem rota"; **nunca** com zero, com estimativa por linha reta nem com o valor do outro modo.
7. **Given** uma resposta HTTP 200 cujo corpo traz erro de cota, chave inválida ou requisição negada, **When** a CLI a recebe, **Then** ela é tratada como falha (não como sem rota), a execução para de forma limpa no primeiro erro de cota ou autorização, e os pares restantes ficam pendentes.

---

### User Story 3 - Auditar a cobertura e o que ficou sem rota (Priority: P2)

O operador consulta um relatório que mostra, por modo e por polo, quantos municípios têm valor, quantos ficaram sem rota e por quê, e quantos pares estão pendentes. O relatório torna explícito o que é ausência verdadeira (ilhas, sem transporte) e o que é pendência de execução.

**Why this priority**: constitution III proíbe valor inventado ou imputado em silêncio; sem o relatório, "sem rota" e "ainda não calculado" se confundem e o ranker pode tratá-los igual. Fica em P2 porque só faz sentido depois que há dado (US1) e é indispensável para fechar a US2.

**Independent Test**: sobre um staging de fixture com combinações conhecidas (ok, sem rota, pendente, falha de autorização), gerar o relatório e conferir cada contagem; conferir que `ok + sem_rota + pendente + falha = total de pares esperados`, por modo.

**Acceptance Scenarios**:

1. **Given** um staging com todos os estados possíveis, **When** o relatório é gerado, **Then** para cada modo e polo as contagens `ok`, `sem_rota`, `falha` e `pendente` somam o total esperado (`308 × polos elegíveis` nos modos do Google; `308 × polos` na linha reta).
2. **Given** pares com `sem_rota`, **When** o relatório é gerado, **Then** cada um é listado com `dico`, nome do município, polo, modo e motivo, e a lista distingue ausência esperada (ex.: ilha sem ligação terrestre) de ausência a investigar.
3. **Given** que o operador altera `poles.yml` ou a versão da CAOP, **When** o relatório é gerado, **Then** ele aponta quais pares existentes ficaram desatualizados (origem ou destino mudou) e quais pares novos estão pendentes, sem alterar os resultados já gravados.
4. **Given** qualquer saída gravada ou relatório, **When** auditados, **Then** ele traz a atribuição "Tempos de viagem: Google" e a referência ao risco aceito para os modos do Google, e **não** traz nenhum valor de chave.

---

### Edge Cases

- **Município que coincide com um polo**: distância 0 em linha reta; nos modos do Google, o par é consultado ou dispensado conforme a regra do FR-014, mas nunca omitido sem registro.
- **Ponto representativo fora de via**: o Google ajusta a origem à rede viária; as coordenadas devolvidas ficam no manifest, e uma diferença acima de um limite declarado é sinalizada, não corrigida.
- **Ilhas**: Madeira e Açores têm linha reta a todos os polos; carro e transporte público só para polos do mesmo grupo de roteamento, e pares entre ilhas diferentes dos Açores resultam em sem rota registrada.
- **Transporte público no interior**: ausência frequente de rota em município rural é esperada e mostrada como `sem_rota`, nunca preenchida a partir do carro.
- **Falha parcial**: quando alguns pares falham e outros não, os bons são gravados e o comando termina com código de erro e a lista dos pendentes.
- **Resposta alterada entre execuções** do mesmo par: a nova resposta é gravada como nova revisão imutável; a anterior é preservada (constitution V).
- **Polo removido do catálogo**: seus resultados anteriores permanecem no bruto, mas deixam de entrar no staging vigente e aparecem no relatório como "polo retirado".
- **Horário de partida**: nunca no passado nem sem declaração; o valor usado fica registrado em cada par.
- **Cota do Google já consumida por outra atividade**: a execução para no primeiro erro de cota e informa quantos pares ficaram pendentes.

## Requirements *(mandatory)*

### Functional Requirements

**Catálogo de polos**

- **FR-001**: O sistema DEVE manter os polos em `config/poles.yml`, com `pole_id` único e estável, nome, tipo, grupo de roteamento e, conforme o tipo, o `dico` referenciado ou as coordenadas próprias com a indicação da origem delas.
- **FR-002**: O sistema DEVE validar o catálogo de polos **antes** de qualquer cálculo ou chamada: `pole_id` único, `dico` existente em `dim_municipality`, coordenadas dentro do intervalo válido e dentro de uma caixa que contenha Portugal e as regiões autónomas, grupo de roteamento reconhecido, tipo reconhecido.
- **FR-003**: A lista inicial de polos DEVE conter as cidades Lisboa e Porto e os aeroportos de Lisboa, Porto, Faro, Funchal e Ponta Delgada (decisão do autor, 2026-11-21). Sedes de distrito, capitais regionais e outros aeroportos entram depois, por mudança de catálogo. As coordenadas dos aeroportos são conferidas pelo autor antes do cálculo do Google.
- **FR-004**: Polos de tipo `cidade`, `sede_distrito` e `capital_regional` DEVEM usar o ponto representativo da CAOP do município referenciado, sem geocodificar por nome. Aeroportos DEVEM trazer coordenadas declaradas e a referência pública de onde vieram.

**Linha reta**

- **FR-005**: O sistema DEVE calcular, para cada município da dimensão e cada polo do catálogo, a distância geodésica em linha reta com método e raio terrestre declarados e registrados na proveniência.
- **FR-006**: O resultado em linha reta DEVE cobrir todos os pares `308 × N`, sem exceção por região, sem API e sem chave.

**Cálculo do Google**

- **FR-007**: O sistema DEVE calcular tempo e distância de carro pelo Google, uma única vez por par, do ponto representativo do município ao ponto do polo, conforme os modos habilitados no catálogo (hoje só `driving`). Se o transporte público for habilitado, DEVE usar horário de partida fixo, dia útil e hora local declarados no catálogo e registrado em cada par.
- **FR-008**: O sistema DEVE oferecer uma estimativa de pares, elementos e custo que não faz nenhuma chamada de rede e não exige chave.
- **FR-009**: O sistema DEVE impor um teto de elementos por execução, declarado no catálogo, e exigir confirmação explícita do operador antes de qualquer consulta paga.
- **FR-010**: A chave do Google DEVE vir de `.env` local (listado no `.gitignore`) ou do SSM Parameter Store, e NUNCA de argumento de linha de comando, arquivo versionado, fixture, log, manifest ou mensagem de erro.
- **FR-011**: O sistema DEVE guardar cada resposta do Google como bruto imutável, com `sha256`, tamanho, coordenadas pedidas e devolvidas, parâmetros da consulta (sem a chave), horário da coleta, licença e atribuição; um bruto gravado NÃO DEVE ser sobrescrito.
- **FR-012**: O sistema DEVE respeitar limites de taxa e usar retry com backoff para erros transitórios, e DEVE parar de forma limpa no primeiro erro de cota ou de autorização, mantendo os pares restantes como pendentes.
- **FR-013**: O sistema DEVE consultar o Google somente para pares **elegíveis**, definidos no catálogo: município e polo no mesmo grupo de roteamento. Polos nacionais (cidades e aeroportos) DEVEM ser elegíveis para municípios do continente; quando o catálogo tiver sedes de distrito, cada município DEVE ser pareado com a do próprio distrito; municípios das regiões autónomas DEVEM ser pareados com os polos do mesmo grupo (no plano, da mesma ilha).
- **FR-014**: O sistema DEVE registrar, para um par em que origem e destino coincidem, o resultado conforme a regra do catálogo (consulta ou valor zero declarado), nunca omitindo o par em silêncio.
- **FR-015**: O sistema DEVE retomar uma execução interrompida a partir dos pares sem resultado gravado, sem repetir os já gravados e sem nova cobrança.
- **FR-016**: O sistema DEVE tratar um erro dentro de resposta HTTP 200 como falha de coleta, distinta de "sem rota", e NÃO DEVE gravar bruto parcial ou inválido como resultado.

**Ausência honesta**

- **FR-017**: O sistema DEVE representar um par sem rota com `km` e `minutos` nulos, `status` com o motivo e uma bandeira de ausência. NÃO DEVE preencher o valor com zero, com a linha reta, com o valor do outro modo, com a média da vizinhança ou com qualquer imputação.
- **FR-018**: O sistema DEVE distinguir quatro estados em todo par e modo: `ok`, `sem_rota` (resposta válida sem rota), `falha` (erro de coleta ou autorização) e `pendente` (ainda não consultado).

**Staging e proveniência**

- **FR-019**: O sistema DEVE produzir um staging em formato longo com, no mínimo: `dico`, `pole_id`, `mode` (`straight_line`, `driving`, `transit`), `km`, `minutes`, `status`, `no_route_reason`, `departure_time`, `calculado_em`, `source_run_id`, versão da CAOP, versão do catálogo de polos, licença, atribuição e período de referência.
- **FR-020**: A chave do staging DEVE ser `(dico, pole_id, mode)` vigente, única e sem duplicidade; todo `dico` DEVE existir em `dim_municipality` e todo `pole_id` no catálogo vigente; um `dico` sem correspondência DEVE falhar o build (constitution III).
- **FR-021**: O staging DEVE ter testes dbt: `not_null`, `unique` sobre a chave, `relationships` com `dim_municipality`, faixas aceitáveis para `km` e `minutes` (não negativos e plausíveis), `minutes` e `km` nulos somente quando `status ≠ ok`, e consistência `ok + sem_rota + falha + pendente = esperado` por modo.
- **FR-022**: Toda linha publicável DEVE carregar fonte, período de referência e licença (constitution III), e a atribuição "Tempos de viagem: Google" DEVE acompanhar toda linha de modo `driving` ou `transit`.

**Relatório e idempotência**

- **FR-023**: O sistema DEVE gerar um relatório de cobertura por modo e por polo, com contagens por estado, lista dos pares `sem_rota` com motivo e lista dos pares pendentes.
- **FR-024**: Um par já calculado NÃO DEVE ser recalculado, a menos que a origem, o destino, o horário de partida ou o modo mudem; um polo ou município novo DEVE gerar só os pares novos, e um resultado anterior idêntico DEVE resultar em `unchanged` (constitution V).
- **FR-025**: O sistema DEVE listar como desatualizados os pares cuja origem ou destino mudou desde o cálculo, sem alterá-los.

**Catálogo de fonte, conformidade e qualidade**

- **FR-026**: A entrada da fonte em `config/sources.yml` DEVE existir **antes** do coletor e declarar: publicador, licença, método, frequência (cálculo único), responsável, atribuição, restrições de uso, teto de elementos, horário de partida e o risco aceito (constitution IV), com a alternativa documentada de substituição.
- **FR-027**: O sistema DEVE enviar User-Agent identificado em toda chamada de rede.
- **FR-028**: A suíte de testes DEVE rodar sem rede, com fixtures gravadas (incluindo respostas de erro dentro de HTTP 200, `ZERO_RESULTS`, cota e chave inválida), e nenhuma fixture, log ou saída DEVE conter uma chave real; o scan de segredos do CI DEVE continuar passando.
- **FR-029**: A documentação DEVE acompanhar a mudança: `config/sources.yml` e `.docs/fontes_de_dados.md` atualizados, estimativa de custo no `plan.md` (constitution VII) e, se o provedor for trocado de Distance Matrix para a Routes API, a decisão registrada.

### Key Entities

- **Polo**: ponto de referência fixo e declarado (cidade, aeroporto, sede de distrito, capital regional), com identificador estável, grupo de roteamento e coordenadas (próprias ou herdadas de um município).
- **Distância município–polo**: observação por `(município, polo, modo)` com `km`, `minutos`, estado, motivo de ausência, horário de partida e proveniência.
- **Execução de cálculo**: um `run_id` com o manifest dos pares consultados, parâmetros (sem segredo), estimativa, confirmação e resultado por par.
- **Relatório de cobertura**: contagens por modo, polo e estado, e as listas de ausências e pendências.
- **Entrada de fonte**: registro em `config/sources.yml` com licença, atribuição, risco aceito e alternativa.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A linha reta cobre **100%** dos pares `308 × N polos`, sem nenhum valor nulo.
- **SC-002**: Para cada município e polo, o resultado vigente é único: **0** duplicidades na chave `(município, polo, modo)`.
- **SC-003**: **0** pares com valor inventado: todo par `sem_rota`, `falha` ou `pendente` tem `km` e `minutos` nulos, e o relatório explica cada um.
- **SC-004**: A estimativa de pares, elementos e custo é produzida em **0** chamadas de rede e **0** uso de chave.
- **SC-005**: Uma execução interrompida e retomada consulta **0** pares já gravados.
- **SC-006**: Rodar o cálculo duas vezes sobre as mesmas entradas grava **0** brutos novos na segunda vez.
- **SC-007**: **0** ocorrências de chave de API em arquivos versionados, fixtures, logs e manifests, e o scan de segredos do CI passa.
- **SC-008**: Para os modos do Google, a cobertura por modo e polo elegível é medida e publicada no relatório, com o total de `ok`, `sem_rota`, `falha` e `pendente` somando o esperado.
- **SC-009**: A execução real única fica dentro do teto de elementos declarado e do custo estimado aprovado pelo autor, e o custo recorrente após o cálculo é **zero**.
- **SC-010**: Todas as linhas dos modos do Google trazem a atribuição e a licença; todas as linhas trazem fonte e período de referência.

## Assumptions

- **A execução real do Google é uma etapa manual do autor**, fora do trabalho automatizado: exige chave própria, billing ativo e confirmação. O agente que implementar entrega a CLI, as fixtures, os testes e o roteiro de execução; **não** roda a coleta real nem pede a chave.
- **O risco de termos de uso do Google foi aceito pelo autor em 2026-11-03** (ADR-002 D8; `.docs/fontes_de_dados.md`, "Risco aceito"). Mitigações: execução única de volume baixo, atribuição visível e a alternativa registrada de substituição (OpenRouteService para carro; GTFS da CP para comboio). Esta spec não reabre a decisão.
- A chave do Google, por ser do pipeline, segue a regra de ADR-003 e constitution I: `.env` local ou SSM, nunca versionada nem enviada ao navegador. Não se aplica BYOK do visitante a este cálculo, que é em lote.
- **Pares estimados**: com os 7 polos iniciais, cerca de 5 polos consultados por município (estimativa do plano: ~1.404 pares, só carro, ≈ 1.404 elementos; a documentação antiga previa ~8 polos e ~5 mil elementos). O número exato, a tabela de preços e a cota gratuita vigentes são medidos no `sdd-plan` (constitution VII).
- **Provedor e produto da API** (Distance Matrix legada ou Routes API `computeRouteMatrix`) são decisão do `sdd-plan`, com base na documentação atual do Google, em preço, cota, limite de elementos por requisição e suporte a `transit` [NEEDS CLARIFICATION: confirmar produto, preço e cota vigentes no momento do plano].
- O ponto de partida é o `representative_lat`/`representative_lon` da CAOP (spec 001), o mesmo usado por clima (spec 003). Municípios e polos usam o mesmo ponto, o que garante distância 0 de um município até o próprio polo.
- O tempo de carro usa o modo sem tráfego em tempo real, sem horário de partida (decisão do plano, a confirmar pelo autor). Se o transporte público for habilitado depois, o horário de partida é um dia útil futuro às 08:00 de Lisboa, fixado no catálogo e registrado em cada par.
- **Padrões a reaproveitar** (sem repetir a descoberta): o catálogo e a validação em `pipelines/collectors/_shared/catalog.py`; o armazenamento com o mesmo layout de chaves local/S3 simulado das specs 001–003 e 008; as coletas por unidade, retomáveis e por estado da spec 003 (clima) e da spec 008 (Wikipedia); o staging longo e os testes dbt das specs 002 e 003; os relatórios de cobertura em `.docs/reports/`.
- **Ambiente**: Python 3.12, `uv`, `httpx`, Parquet e dbt/DuckDB, como nas specs anteriores. Este documento descreve o quê; o como (módulos, nomes de CLI, schemas, formato do manifest) é do `sdd-plan`.
- Fora de escopo desta etapa e já planejado para depois: seleção do polo mais próximo, normalização e o `criteria_catalog` (Fase 3 do roteiro).

## Clarifications

<!-- Preenchido pelo sub-fluxo de clarify do sdd-specify. Não remover esta
     seção mesmo que fique vazia — sessões futuras podem adicionar aqui. -->

### Sessão 2026-11-21

Esta spec foi escrita **sem entrevista com o autor**, a pedido dele, para entrega a outro agente. As decisões abaixo foram **herdadas da documentação**, não respondidas nesta sessão. Se alguma estiver errada, corrigir antes do `sdd-plan`.

- Q: Quais modos de mobilidade entram agora? → A: linha reta e carro. O transporte público, previsto no ADR-002 D8 (atualização de 2026-11-03), fica de fora por decisão do autor em 2026-11-21; o modo continua suportado por catálogo. A emenda do ADR-002 D8 está registrada no ADR-004.
- Q: Quando o Google é consultado? → A: uma única vez, por CLI local, e só de novo se a lista de polos ou a CAOP mudar (`.docs/fontes_de_dados.md`).
- Q: Quem herda a distância na freguesia? → A: decisão da camada de marts, fora desta spec; a freguesia herda do município com sinalização (`.docs/fontes_de_dados.md`; constitution III).
- Q: O que acontece quando não há rota? → A: valor nulo com bandeira e motivo, nunca imputado (`.docs/fontes_de_dados.md`; constitution III).
- Q: O risco de termos do Google foi aceito? → A: sim, em 2026-11-03, com mitigações e alternativa documentada (constitution IV).
- Q: A coleta real do Google roda neste trabalho? → A: não; é etapa manual do autor, com chave própria e confirmação (decisão de enquadramento desta spec, a confirmar).
- Q: Quais são os polos iniciais? → A: só cidades (Lisboa e Porto) e aeroportos (LIS, OPO, FAO, FNC, PDL), 7 no total; o autor decidiu em 2026-11-21 (resolve o pendente da lista de polos). Faltam só as coordenadas dos aeroportos, conferidas antes da coleta real.
- Pendente 2: produto, preço e cota vigentes do Google no momento do plano (Assumptions).
- Q: A Routes API não devolve as coordenadas ajustadas à via; aceitar que não haverá sinalização de "ponto fora de via" nem coordenadas devolvidas (FR-011, US2-AC4 e o edge case)? → A: sim, aceito pelo autor em 2026-11-21. O manifest grava só as coordenadas pedidas e `returned_coordinates: unavailable`; o Google encaixa a origem na estrada mais próxima e o desvio não é medido (T035, item a).
- Q: Na linha reta o tempo não se aplica; aceitar `minutes` nulo com `status = ok` nesse modo (ajuste do FR-021)? → A: sim, aceito pelo autor em 2026-11-21. Nos modos de rota, `km` e `minutes` continuam nulos só quando `status ≠ ok` (T035, item b).
- Q: A linha reta é derivada no build, sem coleta e sem bruto; aceitar que a idempotência seja o mesmo resultado (hash do conteúdo) em vez de `unchanged` no manifest (US1-AC4)? → A: sim, aceito pelo autor em 2026-11-21 (T035, item c).
