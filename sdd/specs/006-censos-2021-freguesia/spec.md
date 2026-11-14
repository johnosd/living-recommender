# Feature Specification: Censos 2021 por freguesia — coleta e preparação de população e faixas etárias

**Slug**: `006-censos-2021-freguesia`

**Created**: 2026-11-13

**Status**: Em Execução

**Input**: Censos 2021 por freguesia.

## Scope

### Included

- Coleta rastreável dos resultados definitivos oficiais dos Censos 2021 para população residente total e faixas etárias detalhadas por freguesia, em Portugal continental, Açores e Madeira.
- Preservação das contagens e categorias oficiais necessárias para permitir, futuramente, os recortes exatos de 25–39 anos e de 65 anos ou mais, além das demais faixas detalhadas do conjunto etário selecionado.
- Preparação dos dados e associação aos códigos oficiais da dimensão territorial vigente do projeto, priorizando dados oficiais com geografia comprovadamente compatível.
- Uso da correspondência 2013→2025 da spec 004 quando necessário e compatível com as versões territoriais envolvidas; herança explícita e ausência quando seria necessário estimar.
- Relatório legível de qualidade e cobertura de todas as freguesias vigentes, inclusive as sem valor utilizável.
- Operação pelos comandos do projeto, com resultados verificáveis localmente, instruções de execução e diagnóstico de falhas para o operador e para quem prepara os indicadores posteriores.

### Out of Scope

- Cálculo dos percentuais etários, densidade populacional, índices, scores, ranking ou demais indicadores finais.
- Site, mapas, fichas e apresentação do detalhamento de freguesias ao visitante.
- Repartição por área ou população, interpolação espacial e estimativa de valores para territórios alterados.
- Ingestão de microdados pessoais, outras temáticas dos Censos (habitação, emprego etc.), outros censos ou estimativas populacionais anuais entre censos.
- Recriação da correspondência da spec 004 ou extensão dela para outras reorganizações territoriais.
- Implantação em nuvem, agendamento recorrente e publicação da base para visitantes. A execução local não demonstra operação em produção.

## User Scenarios & Testing

### User Story 1 - Obter uma edição censitária auditável (Priority: P1)

Como operador, quero coletar e preservar os dados oficiais de população total e faixas etárias dos Censos 2021, com sua documentação, para ter uma base reproduzível para as próximas etapas.

**Why this priority**: os dados de origem preservados já permitem inspeção e reutilização, independentemente da preparação territorial.

**Independent Test**: executar a coleta contra uma fonte controlada com dados e metadados representativos, verificar conteúdo e proveniência, repetir sem alterações e simular uma resposta inválida; a entrega pode ser demonstrada sem a saída territorial preparada.

**Acceptance Scenarios**:

1. **Given** fontes oficiais selecionadas e documentadas, **When** o operador coleta a edição 2021, **Then** os originais e metadados ficam preservados com origem, edição, geografia, licença, horário da coleta, identificação da execução e impressão digital do conteúdo.
2. **Given** uma coleta anterior válida e conteúdo equivalente na fonte, **When** a coleta se repete, **Then** o resultado informa ausência de mudança sem duplicar os dados brutos nem substituir a versão preparada vigente.
3. **Given** indisponibilidade, resposta vazia, página de erro ou estrutura incompatível, **When** a coleta é executada, **Then** a falha identifica a fonte e o motivo, não aceita conteúdo inválido e preserva os resultados válidos anteriores.
4. **Given** uma revisão oficial do mesmo censo, **When** a coleta detecta mudança, **Then** preserva a revisão anterior e distingue a nova revisão sem alterar o período de referência de 2021 para a data da coleta.

### User Story 2 - Preparar dados associados à geografia vigente (Priority: P2)

Como responsável pelos dados, quero uma base censitária utilizável por freguesia vigente, com contagens, categorias e origem territorial explícitas, para preparar indicadores futuros sem inventar precisão.

**Why this priority**: transforma a origem auditável em dados consumíveis pelas próximas etapas, mantendo a distinção entre dado próprio e herdado.

**Independent Test**: fornecer originais censitários previamente preservados ou fixtures, dimensão territorial e correspondência conhecidas; verificar a saída sem executar a coleta nem acessar a rede.

**Acceptance Scenarios**:

1. **Given** dados oficiais com códigos e geografia comprovadamente compatíveis com a dimensão vigente, **When** a preparação é executada, **Then** usa esses dados diretamente, registra a compatibilidade e os distingue dos valores herdados pelo projeto.
2. **Given** ausência de dado oficial compatível para uma unidade e correspondência territorial aplicável, **When** a preparação ocorre, **Then** usa a correspondência e preserva códigos, versão e valores da origem; uma união desfeita pode fornecer valores herdados a seus destinos, com sinalização explícita.
3. **Given** relação parcial ou múltiplas origens e destinos sem equivalência territorial comprovada, **When** não é possível obter um valor sem estimar ou somar indevidamente, **Then** registra ausência e motivo; não divide nem soma valores por suposição.
4. **Given** categorias detalhadas oficiais, **When** a base é preparada, **Then** preserva contagens e limites etários que permitam obter exatamente 25–39 e 65+ no futuro, sem produzir os percentuais ou esses indicadores finais.
5. **Given** resultados válidos anteriores, **When** a preparação falha, **Then** a versão utilizável anterior permanece intacta e o resultado informa a reprovação.

### User Story 3 - Conhecer cobertura e impedimentos de uso (Priority: P2)

Como operador, quero inspecionar um relatório nacional de qualidade, para distinguir ausências legítimas de defeitos da coleta ou preparação e decidir se os dados estão prontos para a etapa seguinte.

**Why this priority**: torna verificável a cobertura completa e honesta escolhida na entrevista.

**Independent Test**: gerar o relatório a partir de dados preparados de fixture, dimensão vigente e registros de validação, incluindo ausências e heranças, sem executar a coleta.

**Acceptance Scenarios**:

1. **Given** a dimensão territorial vigente, **When** o relatório é produzido, **Then** todas as suas freguesias aparecem, vinculadas ao município, com cobertura por população total e faixa exigida, classificação próprio/herdado/ausente e motivo quando aplicável.
2. **Given** ausência oficial, supressão estatística ou ambiguidade territorial comprovada, **When** a qualidade é avaliada, **Then** o relatório admite a lacuna documentada e informa seu impacto sem transformá-la em zero.
3. **Given** falha de coleta, perda de registros ou faixas exigidas cuja disponibilidade não foi verificada, **When** a prontidão é avaliada, **Then** o resultado é reprovado e lista os impedimentos; não declara a feature concluída.
4. **Given** valores herdados repetidos entre destinos de uma união desfeita, **When** a qualidade é avaliada, **Then** o relatório evidencia essa herança e não apresenta sua soma como total municipal ou nacional reconciliado.

### Edge Cases

- Código com zero inicial ou sufixo alfanumérico: preservar como identificador oficial, sem conversão destrutiva para número.
- Mudança de nome sem mudança territorial: resolver por identificação e metadados oficiais, sem correspondência baseada apenas no nome.
- Dado censitário rotulado como geografia 2025: verificar códigos, cobertura e semântica territorial; o rótulo isolado não comprova compatibilidade com a CAOP vigente.
- CAOP posterior ao alcance da correspondência 2013→2025: não aplicar a correspondência como se estivesse atualizada; registrar incompatibilidade que impede aceitar essa preparação.
- Zero, ausência, supressão e idade ignorada são estados distintos. Uma categoria de idade ignorada deve ser preservada quando publicada.
- Faixas amplas, como 25–64, não permitem inferir 25–39. A fonte selecionada deve comprovar o detalhe exigido ou a insuficiência impede concluir.
- Totais e subtotais sobrepostos, ambos os sexos junto de masculino/feminino, ou categorias de nacionalidade: não duplicar residentes ao selecionar a população total.
- Duplicatas conflitantes, contagens negativas ou não inteiras e códigos sem município resolvido: reprovar a preparação, com diagnóstico.
- Freguesia de origem sem destino: emitir aviso e incluir no relatório de cobertura; não descartá-la silenciosamente.
- Divergência entre soma etária e total oficial: identificar categorias ignoradas, supressões ou regras oficiais de confidencialidade antes de aceitar qualquer diferença; diferenças sem explicação reprovam.
- Disponibilidade parcial numa execução e falha de uma das fontes: registrar o que ocorreu, sem promover uma combinação incompleta como versão válida.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE coletar resultados definitivos oficiais dos Censos 2021 de população residente por freguesia, com abrangência de Portugal continental, Açores e Madeira.
- **FR-002**: DEVE preservar a população total e todas as categorias do conjunto etário detalhado selecionado, incluindo códigos, rótulos e limites de idade, com detalhe suficiente para obter exatamente 25–39 e 65+; DEVE documentar a população de referência e evitar dupla contagem de dimensões adicionais.
- **FR-003**: DEVE registrar a fonte antes de coletá-la, incluindo método, licença e atribuição, responsável e frequência por nova edição ou revisão oficial. Licença não comprovada DEVE ser explicitada e tratada segundo a constitution, sem apresentá-la como confirmada.
- **FR-004**: DEVE preservar originais imutáveis e proveniência por execução, incluindo fonte, identificador do conjunto, edição 2021, versão geográfica, revisão quando disponível, coleta, tamanho e impressão digital do conteúdo.
- **FR-005**: DEVE identificar conteúdo equivalente como sem mudança e registrar revisões oficiais sem sobrescrever originais. A data de coleta ou revisão NÃO DEVE substituir o período de referência censitário.
- **FR-006**: DEVE validar conteúdo e estrutura recebidos e expor falhas ao operador; respostas inválidas ou incompletas NÃO DEVEM ser aceitas como dados válidos.
- **FR-007**: DEVE usar os códigos oficiais da dimensão territorial vigente, preservar sua representação e vincular cada destino ao município; município sem correspondência DEVE reprovar a preparação, e freguesia sem correspondência DEVE gerar aviso e constar no relatório.
- **FR-008**: DEVE priorizar dados oficiais com compatibilidade territorial comprovada, por população total e categoria etária. DEVE registrar a evidência de compatibilidade e a proveniência da geografia publicada pelo INE, inclusive eventuais métodos oficiais de reexpressão territorial.
- **FR-009**: Quando não houver dado oficial compatível, DEVE aplicar a correspondência 2013→2025 apenas se sua origem e destino forem compatíveis com os dados e a dimensão vigente. DEVE preservar a relação usada e sinalizar a herança de valores de uniões desfeitas.
- **FR-010**: NÃO DEVE estimar ou repartir contagens nem somar origens sem equivalência territorial comprovada. Relações sem solução válida DEVEM resultar em ausência motivada. Dado oficial diretamente compatível tem precedência sobre herança; conflito entre fontes de mesma precedência DEVE ser diagnosticado e impedir a aceitação do valor conflitante.
- **FR-011**: DEVE distinguir próprio, herdado e ausente por observação. Um valor herdado DEVE manter a identificação do território de origem e NÃO DEVE ser apresentado como contagem exclusiva do território de destino.
- **FR-012**: DEVE preservar zeros, ausências, supressões e categorias ignoradas como estados distintos; NÃO DEVE imputar valores silenciosamente.
- **FR-013**: DEVE verificar unicidade, integridade territorial, contagens inteiras não negativas e coerência dos totais com categorias etárias mutuamente exclusivas, considerando as regras oficiais documentadas. Falhas inexplicadas DEVEM reprovar a preparação.
- **FR-014**: DEVE produzir relatório legível que cubra todas as freguesias vigentes e cada medida exigida, com município, versões territoriais, edição, estado de cobertura, motivo, fontes e momento da execução; DEVE resumir resultados nacionais, regionais e municipais sem somar heranças como população própria.
- **FR-015**: DEVE aceitar como cobertura honesta ausências oficiais e ambiguidades territoriais documentadas, mas reprovar a prontidão diante de falhas de coleta, perdas de registros ou detalhe etário obrigatório não verificado ou insuficiente.
- **FR-016**: DEVE preservar a versão preparada válida anterior em caso de falha e só tornar uma nova versão utilizável após todas as validações obrigatórias.
- **FR-017**: DEVE fornecer instruções reproduzíveis de coleta, preparação e leitura do relatório, com diagnóstico e indicação de sucesso ou falha pelos comandos do projeto. DEVE permitir validar a preparação com originais preservados, sem nova coleta.

### Key Entities

- **Conjunto censitário**: identificação oficial, edição, revisão, população de referência, dimensões, categorias, geografia e licença.
- **Original coletado**: conteúdo imutável, origem, execução, horário, tamanho e impressão digital.
- **Categoria etária**: código, rótulo, limites inclusivos/exclusivos, eventual limite superior aberto e indicação de total ou idade ignorada.
- **Observação censitária**: território de origem, população ou faixa, contagem ou estado de ausência/supressão e proveniência.
- **Observação por freguesia vigente**: destino e município, observação de origem, relação territorial, classificação próprio/herdado/ausente e motivo.
- **Relatório de qualidade e cobertura**: universo territorial, versões e fontes, cobertura por medida, avisos, falhas e resultado de prontidão.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% das freguesias da dimensão vigente, nas três regiões, aparecem no relatório, com classificação explícita para a população total e cada faixa obrigatória; a contagem esperada vem da dimensão, sem número nacional fixado no código.
- **SC-002**: 100% dos valores aceitos são rastreáveis ao conjunto e território oficiais de origem, edição 2021, geografia, licença ou situação documentada desta e execução de coleta/preparação.
- **SC-003**: O conjunto etário selecionado permite delimitar exatamente 25–39 e 65+ para territórios com observações utilizáveis; a disponibilidade foi verificada para todo o universo, e qualquer ausência aceita tem motivo documentado.
- **SC-004**: Todos os cenários de compatibilidade direta, herança de união desfeita, ambiguidade territorial, código alfanumérico e ausência/supressão têm resultado verificável, sem qualquer valor criado por estimativa do projeto.
- **SC-005**: Repetir a coleta sem mudança não duplica os originais; falhas simuladas de coleta ou preparação preservam integralmente a versão válida anterior.
- **SC-006**: O relatório não deixa registros descartados sem explicação nem impedimentos técnicos ocultos; falha de coleta, perda de registros ou detalhe obrigatório insuficiente/não verificado sempre resulta em reprovação.
- **SC-007**: Antes de declarar a implementação concluída, uma execução local com dados oficiais reais demonstra a cobertura e a prontidão exigidas, com evidências distintas das verificações com dados simulados; não há alegação de publicação ou operação em nuvem.

## Assumptions

- Usuários desta entrega são o operador do pipeline e os responsáveis pelos indicadores posteriores; o ponto de entrada segue os comandos do projeto, sem interface nova. Esta é uma premissa derivada do recorte de ingestão e das convenções existentes.
- A dimensão territorial vigente e a correspondência da spec 004 são dependências existentes; sua compatibilidade deve ser verificada a cada preparação.
- A prioridade para dado oficial compatível não pressupõe que o INE disponha de todas as faixas exigidas para todas as freguesias na geografia vigente; isso é objeto de verificação no plano e de aceite na execução.
- “Faixas detalhadas” significa preservar o conjunto oficial escolhido com resolução suficiente para 25–39 e 65+; não exige todas as tabelas etárias ou todas as combinações de sexo, nacionalidade e outras dimensões publicadas pelo INE.
- O período é 2021, mesmo se a publicação oficial usar geografia posterior; a feature não representa população atual estimada.
- Preparar os dados inclui validar a possibilidade dos recortes futuros, mas não entregar percentuais, densidade ou indicadores finais.

## Clarifications

### Session 2026-11-13

- Q: Qual deve ser o resultado desta feature? → A: Coleta e preparação dos dados: população e faixas etárias, cobertura nacional, correspondência com a CAOP vigente e relatório de qualidade; indicadores finais e site ficam para depois.
- Q: Qual detalhe etário devemos exigir? → A: Total e faixas detalhadas, preservando contagens oficiais que permitam obter 25–39 e 65+ no futuro, sem calcular percentuais nesta feature.
- Q: Quando uma freguesia ou faixa ficar sem dado utilizável, qual é o critério de conclusão? → A: Cobertura completa e honesta: todas as freguesias constam com dado próprio, herdado ou ausente e motivo; ausência oficial ou ambiguidade documentada é aceita, mas falhas de coleta, registros perdidos e faixas exigidas não verificadas impedem concluir.
- Q: Qual regra territorial adotar? → A: Priorizar dado oficial compatível com a geografia vigente; recorrer à correspondência 2013→2025 quando necessário, com herança sinalizada e ausência quando seria necessário estimar.

### Ambiguity Review

- Escopo, domínio/dados, integração territorial e sinais de conclusão foram esclarecidos na entrevista.
- Interação/UX foi resolvida pelas convenções de operação do projeto: comandos, relatório legível e diagnóstico; não há fluxo de visitante nesta feature.
- Requisitos não funcionais e casos de borda seguem a constitution e as regras de integridade, rastreabilidade, ausência e preservação descritas acima; não foi imposta uma meta de tempo sem necessidade identificada.
- Terminologia distingue período censitário, geografia oficial, data da coleta, dado próprio e herança. Formatos, mecanismos de acesso e organização técnica ficam para o sdd-plan.

## Source Evidence and Planning Handoff

- O catálogo oficial [População residente — indicador INE 0014632](https://dados.gov.pt/pt/datasets/populacao-residente-n-o-0014632/) descreve população dos Censos 2021 por local de residência, sexo, grupo etário e nacionalidade, com “NUTS - 2024 - geografia 2025”, e declara CC BY 4.0. Consultado em 2026-11-13. Isso comprova a descrição do catálogo, não a cobertura das freguesias, o detalhe etário nem a compatibilidade de todos os dados.
- O acesso ao detalhe do indicador no portal do INE não foi concluído nesta entrevista. O plano deve verificar fontes candidatas, categorias, códigos, totais, regras estatísticas, licença e evidência territorial antes de fixar a seleção e os contratos de dados.
- A spec 004 já define a correspondência sem pesos e a herança sinalizada. Esta spec não presume que sua aplicação resolva todos os casos censitários.
- Próximo passo: rodar sdd-plan nesta spec. A criação desta especificação não autoriza afirmar que a ingestão foi implementada ou validada com dados reais.
