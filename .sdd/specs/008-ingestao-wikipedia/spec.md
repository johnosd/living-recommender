# Feature Specification: Ingestão Wikipedia — textos municipais rastreáveis e organizados por seções

**Slug**: `008-ingestao-wikipedia`

**Created**: 2026-11-20

**Status**: Convergida

**Input**: "vamos especificar wikipedia"; analisar o notebook e os TXT de `J:/MPAlugueisLisboa`, avaliar oportunidades além do legado e seguir com `sdd-specify` após as clarificações de conteúdo, idioma, operação e histórico.

## Scope

### Included

- Coleta rastreável de artigos da Wikipedia em português associados aos 308 municípios da dimensão CAOP vigente no projeto, incluindo Continente, Açores e Madeira.
- Identificação territorial validada antes de aceitar um artigo para o município; tratamento explícito de homônimos, redirecionamentos, páginas de desambiguação e artigos sobre cidade/sede em vez do município.
- Preservação dos originais e metadados de origem, com identificação da página, revisão, instante de coleta, licença/atribuição e integridade dos arquivos.
- Preparação da introdução original e do corpo textual completo organizado por seções, preservando limites de parágrafos e listas, hierarquia e ligações/referências disponíveis.
- Metadados do item Wikidata associado e ligação para o artigo em inglês, quando disponibilizados pela fonte e vinculados ao artigo validado. Ausência desses metadados não provoca busca por palpite nem coleta de conteúdo inglês.
- Coleta e preparação por comandos locais, idempotentes, com diagnóstico de falhas, retomada e saída utilizável por um futuro agendador.
- Relatório legível e processável de cobertura dos 308 municípios, qualidade da identificação, disponibilidade de introdução/seções e impedimentos para uso.
- Nova coleta da Wikipedia. Os 308 TXT legados permanecem preservados no projeto antigo e não entram como origem da base nova.
- Documentação operacional e atualização do inventário de fontes para descrever o comportamento entregue.

### Out of Scope

- Coleta de artigos próprios de freguesias, distritos, regiões ou países como substitutos dos artigos municipais; textos sobre a sede só podem participar quando a abrangência do artigo em relação ao município estiver validada e explicitada.
- Coleta ou tradução de texto em inglês; geração de resumos, reescritas ou classificações por IA.
- Ingestão de declarações/propriedades do Wikidata como uma nova fonte; a presença do identificador associado não autoriza importar suas estatísticas.
- Download, seleção ou publicação de fotografias, brasões, bandeiras, mapas e outros arquivos de mídia, incluindo seus pipelines de atribuição.
- Conversão de tabelas/infobox em indicadores tipados; inferência de população, área, clima, segurança, oferta de serviços ou horários de transportes para substituir fontes oficiais.
- Importação/backfill dos TXT antigos, correção ou execução do notebook legado e mudanças em `J:/MPAlugueisLisboa`.
- Site, fichas públicas, busca semântica, ranking, scores, Gold e publicação em `published/vN`.
- Agendamento no computador local, implantação AWS, infraestrutura, publicação e integração com o ciclo geral de todas as fontes. Esta entrega prepara a execução para essas etapas posteriores.

## User Scenarios & Testing

### User Story 1 - Obter artigos municipais corretos e auditáveis (Priority: P1)

Como operador, quero coletar os artigos em português correspondentes aos municípios do projeto, com identidade e versão verificáveis, para obter uma origem confiável sem reproduzir os erros de homônimos do legado.

**Why this priority**: os originais corretamente identificados já têm valor para inspeção e reutilização, independentemente da preparação dos textos.

**Independent Test**: coletar artigos e metadados de uma fonte controlada para municípios conhecidos, incluindo homônimos; conferir a identidade, os originais e as revisões sem executar a preparação.

**Acceptance Scenarios**:

1. **Given** dimensão territorial e correspondências de artigos validadas, **When** a coleta é executada, **Then** os artigos aceitos têm DICO, identidade da página, abrangência territorial, revisão, origem e arquivos íntegros preservados.
2. **Given** títulos como Cuba, Corvo, Gavião, Nazaré ou Santa Cruz, **When** o título encontrado identifica país, ave, outro país ou desambiguação, **Then** não é aceito como artigo do município e há diagnóstico para resolução; correspondência apenas pelo nome não basta.
3. **Given** redirecionamento ou mudança de título, **When** o destino é validado, **Then** a coleta registra a identidade final e a origem da resolução, sem perder a vinculação ao município.
4. **Given** resposta HTTP inválida, erro da API, bloqueio, revisão indisponível ou falha de rede, **When** a consulta falha, **Then** o resultado registra a falha sem aceitar página de erro como artigo nem substituir os dados válidos anteriores.
5. **Given** ausência comprovada de artigo adequado em português, **When** o município é avaliado, **Then** registra ausência e sua evidência, sem fabricar texto, herdar de outro lugar ou confundir a ausência com falha técnica.

### User Story 2 - Preparar textos completos e reutilizáveis (Priority: P2)

Como responsável pelos dados, quero introdução e seções completas a partir dos originais preservados, para permitir futuras fichas e recortes temáticos sem truncar o conteúdo ou misturar assuntos.

**Why this priority**: transforma a origem auditável em conteúdo consumível por outras etapas, mantendo sua estrutura e proveniência.

**Independent Test**: fornecer originais de fixture e suas identidades/revisões, executar a preparação sem rede e comparar introdução, seções, parágrafos, listas, links e referências com o conteúdo preservado.

**Acceptance Scenarios**:

1. **Given** artigo com introdução e várias seções/subseções, **When** a preparação ocorre, **Then** a introdução fica disponível separadamente e todo o corpo textual editorial é representado com sua hierarquia e ordem, sem limitar a extração ao primeiro bloco de cada título.
2. **Given** seção com vários parágrafos ou listas, **When** seu texto é preparado, **Then** todos os blocos são preservados com separação legível; palavras, itens e links não são concatenados indevidamente.
3. **Given** uma seção sem parágrafo seguida de outra seção com conteúdo, **When** a primeira é processada, **Then** não recebe texto da seção seguinte; eventual tabela ou ausência fica identificada dentro dos limites corretos.
4. **Given** tabelas, infobox ou conteúdo aninhado, **When** o texto editorial é representado, **Then** mantém o contexto e os limites de cada bloco, sem misturar entidades ou produzir indicadores numéricos; os originais completos continuam disponíveis.
5. **Given** temas como história, saúde, património, áreas verdes e museus, **When** estão presentes no artigo, **Then** permanecem disponíveis, independentemente da lista restrita de palavras-chave do legado.
6. **Given** metadados de idioma e item Wikidata, **When** a preparação termina, **Then** conserva o identificador e a ligação inglesa disponíveis, sem coletar texto inglês, imagens ou declarações Wikidata.
7. **Given** falha de integridade ou preparação, **When** o candidato é reprovado, **Then** a base preparada válida anterior e os dados de outras fontes permanecem preservados.

### User Story 3 - Atualizar e retomar sem perder histórico (Priority: P2)

Como operador, quero repetir a coleta, detectar revisões e retomar falhas com segurança, para manter os textos atualizáveis por comandos e permitir agendamento posterior.

**Why this priority**: evita duplicação e sobrescrita, e torna possível operar a fonte de maneira recorrente.

**Independent Test**: partir de estado conhecido, simular conteúdo inalterado, revisão nova, mudança de correspondência e interrupção parcial; verificar os estados e os originais sem depender de site ou infraestrutura externa.

**Acceptance Scenarios**:

1. **Given** artigos já coletados e conteúdo/proveniência equivalentes na fonte, **When** a verificação é repetida, **Then** informa `unchanged`, mantém a rastreabilidade da verificação e não duplica os originais nem promove novamente o mesmo conteúdo preparado.
2. **Given** uma nova revisão ou alteração relevante de origem, **When** a mudança é detectada, **Then** preserva a versão anterior e distingue a nova, mantendo separados instante da revisão, coleta e processamento.
3. **Given** mudança de artigo associado a um DICO ou de versão da dimensão/correspondência, **When** ocorre nova execução, **Then** revalida a associação e não aceita silenciosamente o estado antigo apenas porque o código municipal ou o texto coincide.
4. **Given** parte dos municípios concluída e falha/interrupção nos demais, **When** a execução é retomada, **Then** preserva o progresso confirmado, conclui o restante e informa falhas pendentes sem declarar atualização nacional completa.
5. **Given** uma tentativa recente com falha e uma versão anterior válida, **When** os resultados são consultados, **Then** distingue a falha atual do conteúdo anterior preservado e informa suas respectivas datas/revisões.

### User Story 4 - Verificar cobertura e prontidão nacional (Priority: P2)

Como operador, quero um relatório de todos os municípios e das lacunas de conteúdo, para distinguir disponibilidade enciclopédica legítima de problemas de coleta ou associação territorial.

**Why this priority**: a presença de um arquivo não comprova artigo correto nem texto utilizável, como mostrou o legado.

**Independent Test**: produzir o relatório a partir de fixtures de dimensão, estados e textos preparados, incluindo artigos corretos, ausentes, incorretos e falhas, sem executar a coleta.

**Acceptance Scenarios**:

1. **Given** a dimensão vigente, **When** o relatório é gerado, **Then** representa cada um dos 308 municípios uma única vez, com DICO, nome, estado de identificação/coleta/preparação, artigo/revisão quando existentes, cobertura de texto e motivos das lacunas.
2. **Given** um artigo válido sem determinado tema, **When** a cobertura é avaliada, **Then** registra tema não encontrado e preserva o texto existente, sem confundir isso com inexistência do município ou falha técnica.
3. **Given** artigo ausente com evidência suficiente, **When** a prontidão é avaliada, **Then** aceita e explicita a limitação editorial sem inventar conteúdo; a ausência não equivale a valor zero nem aciona substituição por outro território.
4. **Given** falha técnica, identidade ambígua ainda não resolvida, artigo incorreto, revisão incoerente ou perda de conteúdo, **When** a prontidão é avaliada, **Then** reprova e lista os impedimentos, preservando separadamente as versões anteriores válidas.
5. **Given** todos os municípios contabilizados e nenhuma falha técnica ou identificação pendente, **When** os resultados são conferidos, **Then** há evidência legível e processável de prontidão, com ausências editoriais justificadas e limitações de abrangência declaradas.

### Edge Cases

- Homônimos de outros países, países e animais: nome igual e existência de página não comprovam correspondência municipal.
- Município, sede/cidade, ilha, freguesia e distrito com o mesmo nome: registrar abrangência; artigo apenas sobre sede não é automaticamente artigo sobre todo o município.
- Artigo que combina cidade e município: explicitar essa abrangência e não converter afirmações da cidade em indicadores municipais.
- Página de desambiguação, redirecionamento em cadeia, destino trocado ou página movida/apagada: validar destino e manter evidência; não selecionar a primeira opção por conveniência.
- Introdução ou tema inexistente no artigo curto: registrar disponibilidade real; HTML bruto com texto presente, mas extração vazia, é falha de preparação.
- Títulos com acentos, grafias alternativas, espaços, caracteres especiais ou colchetes usados apenas no cadastro legado: não presumir que sejam títulos exatos da Wikipedia.
- Títulos/seções repetidos, hierarquia irregular, tabelas, listas aninhadas e referência sem texto: manter identidade/ordem dos blocos sem atravessar fronteiras.
- HTML com controles de edição, menus, scripts ou avisos de interface: separar do corpo editorial; regras de limpeza devem ser documentadas, sem excluir conteúdo substantivo silenciosamente.
- Conteúdo alterado entre identificação e obtenção: aceitar somente conteúdo e metadados coerentes com a revisão registrada.
- Mesmo artigo revisado por dependências de renderização, ou nova revisão com texto equivalente: registrar a proveniência efetiva; não presumir identidade de conteúdo exclusivamente pelo número da revisão nem inventar revisão editorial.
- Erro apresentado em resposta HTTP 200, resposta não textual, bloqueio ou limitação de taxa: diagnosticar corretamente, respeitar a espera aplicável e não contornar a restrição.
- Coleta parcial, corrupção do bruto, manifesto inconsistente ou execução concorrente: preservar estado válido, diagnosticar e retomar sem sobrescrever originais.
- Metadado Wikidata/ligação inglesa ausente: valor ausente explícito, sem tradução, associação aproximada ou enriquecimento implícito.
- Universo CAOP diferente de 308 ou mudança territorial durante a execução: impedir mistura de versões e exigir revisão explícita do universo/correspondência.

## Requirements

### Functional Requirements

- **FR-001**: O sistema DEVE atender ao universo de 308 municípios da dimensão CAOP vigente no projeto, preservando DICO como identificador textual e distinguindo esse universo de listas legadas por nome.
- **FR-002**: DEVE registrar a fonte no catálogo antes da coleta, com publicador, método, frequência mensal pretendida, idioma, responsável, licença do conteúdo e atribuição verificadas; frequência declarada não significa implantação de agendamento nesta feature.
- **FR-003**: DEVE coletar artigos da edição em português por operação explícita do operador, sem coletar artigos de outros idiomas nesta entrega.
- **FR-004**: DEVE manter associação auditável entre município e artigo, incluindo evidência da identidade e abrangência da página; igualdade de nome, presença de item Wikidata ou mera existência de página não bastam isoladamente.
- **FR-005**: DEVE distinguir artigo municipal, artigo combinado município/sede e artigo apenas da sede ou de outro tipo de entidade; não aceitar equivalência territorial não comprovada nem herdar conteúdo de outro território.
- **FR-006**: DEVE detectar artigos inadequados, desambiguação e identidade pendente, impedindo que sejam apresentados como dados válidos do município; associações manuais devem registrar evidência e ser revisáveis.
- **FR-007**: DEVE resolver redirecionamentos de forma verificável, conservando título consultado, identidade final e diagnóstico quando o destino não puder ser validado.
- **FR-008**: DEVE preservar os originais imutáveis e sua integridade, com origem, idioma, page ID ou equivalente estável, título canônico, identificador/data da revisão, URL permanente, identificação da execução e instantes de coleta e processamento separados.
- **FR-009**: DEVE assegurar que conteúdo, introdução e identificação da revisão sejam coerentes; revisão indisponível ou divergente deve causar falha explícita, sem rotular conteúdo atual como revisão anterior.
- **FR-010**: DEVE disponibilizar a introdução original separada do restante do artigo, sinalizando quando não existe, sem resumo ou tradução gerados.
- **FR-011**: DEVE disponibilizar o corpo textual editorial completo em sua ordem e hierarquia de seções, preservando parágrafos, listas e limites dos blocos; não restringir a captura ao primeiro parágrafo/lista nem à seleção temática do legado.
- **FR-012**: DEVE preservar referências e ligações disponíveis com contexto suficiente para associá-las ao texto de origem; itens e palavras não devem perder a separação legível por causa da limpeza.
- **FR-013**: DEVE manter limites e contexto de tabelas/infobox e preservar os originais completos; a representação de seu conteúdo textual não deve misturar entidades aninhadas nem converter valores em indicadores tipados.
- **FR-014**: DEVE documentar a definição do corpo editorial e as regras de limpeza, distinguindo conteúdo substantivo de navegação/interface; não perder texto silenciosamente nem afirmar extração completa quando a estrutura não for suportada.
- **FR-015**: DEVE preservar título original, identidade/posição e hierarquia das seções; temas podem ser inspecionados por esses títulos, sem classificação semântica obrigatória ou taxonomia fechada nesta entrega.
- **FR-016**: DEVE conservar o identificador Wikidata associado e a ligação para inglês quando fornecidos para a identidade validada, deixando a ausência explícita; isso não inclui obter declarações Wikidata, texto inglês ou arquivos de mídia.
- **FR-017**: DEVE enviar identificação de cliente e contato configurados, limitar requisições, aplicar tentativas/espera compatíveis com as orientações da fonte e respeitar bloqueios, termos e regras aplicáveis, sem contorno de restrições.
- **FR-018**: DEVE identificar falhas de transporte, formato, status HTTP e erros retornados no corpo da resposta; nenhum desses casos pode virar artigo válido ou ausência editorial presumida.
- **FR-019**: DEVE verificar atualizações dos artigos em novas execuções, registrar a verificação e detectar mudanças relevantes de conteúdo/proveniência; um estado previamente coletado não pode permanecer atual indefinidamente sem nova verificação da fonte.
- **FR-020**: DEVE informar `unchanged` quando não houver mudança relevante, preservando referências aos originais e sem duplicar bytes brutos idênticos ou promover novamente conteúdo preparado equivalente; mudanças meramente operacionais não devem produzir falsa revisão de conteúdo.
- **FR-021**: DEVE preservar revisões anteriores e distinguir mudança de origem, coleta e processamento; alterações de correspondência municipal, dimensão ou regra de preparação exigem revalidação/reprocessamento aplicável, mesmo com texto equivalente.
- **FR-022**: DEVE registrar resultados por município, preservar o progresso confirmado e permitir retomada após falha/interrupção, distinguindo sucesso, ausência justificada, pendência e falha técnica; falha de um município não deve apagar o trabalho confirmado dos demais.
- **FR-023**: DEVE preparar os textos a partir dos originais preservados, sem depender de nova rede, verificando integridade e as versões da dimensão/correspondência utilizadas.
- **FR-024**: DEVE validar o candidato antes de substituir a base preparada vigente e preservar essa base e dados de outras fontes em caso de reprovação; concorrência ou interrupção de promoção deve ser detectável e ter recuperação documentada.
- **FR-025**: DEVE emitir relatório legível e processável com os 308 municípios, estados, artigos/revisões, abrangência, disponibilidade/volume de introdução e seções, metadados opcionais, datas pertinentes, motivos das lacunas e impedimentos de prontidão.
- **FR-026**: DEVE distinguir ausência editorial comprovada, tema inexistente, erro de identificação, falha técnica e perda de extração; lacunas documentadas não devem gerar conteúdo inventado nem ser convertidas em zero.
- **FR-027**: DEVE declarar prontidão somente quando todo o universo estiver contabilizado, as identidades aceitas forem validadas, as ausências estiverem justificadas e não houver falhas técnicas, revisão incoerente ou extração incompleta pendentes.
- **FR-028**: DEVE distinguir última tentativa/verificação, última revisão válida e base preparada vigente; manter um resultado antigo após falha não pode ser apresentado como sucesso da atualização recente.
- **FR-029**: DEVE oferecer comandos, status de saída e instruções suficientes para coletar, preparar, inspecionar cobertura e retomar, sem depender de notebook, interface de site, agendador ou conta AWS.
- **FR-030**: DEVE manter os TXT e o notebook legados intactos e fora da origem da base nova; não atribuir retroativamente revisão, licença comprovada ou data de coleta aos arquivos antigos.
- **FR-031**: DEVE tratar os textos como contexto enciclopédico com atribuição; não usá-los para preencher ou substituir indicadores oficiais do projeto nem alegar disponibilidade atual de serviços a partir de narrativa histórica.

### Key Entities

- **Municipality**: DICO, nome e versão/hash da dimensão CAOP que define o universo desta execução.
- **Article Association**: município, identidade/título consultado e final, idioma, abrangência territorial, evidência e estado da validação; preserva mudanças da associação.
- **Article Revision**: identidade da página, revisão, data da revisão, origem/URL permanente, licença/atribuição e metadados opcionais Wikidata/inglês.
- **Collection Attempt**: execução, instantes, resultados por município, integridade/referências dos originais, verificações sem mudança, falhas e pendências.
- **Prepared Article**: introdução e corpo editorial organizado em blocos/seções, com ordem, hierarquia, referências e vínculos à origem/regras de preparação.
- **Coverage and Readiness Report**: universo municipal, estados de identidade/coleta/preparação, conteúdo disponível, ausências justificadas e bloqueadores de uso.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A verificação real representa 308/308 municípios no relatório; cada um tem artigo validado ou ausência editorial justificada. Zero associações incorretas, identidades pendentes, falhas técnicas ou perdas de conteúdo são aceitas como prontidão concluída.
- **SC-002**: Para 100% dos artigos aceitos, identidade, idioma, abrangência, revisão/data, origem permanente, licença/atribuição e integridade dos originais são verificáveis; todos os arquivos referenciados existem e conferem com a integridade registrada.
- **SC-003**: Em exemplos controlados com múltiplos parágrafos/listas, seções vazias, tabelas e estruturas aninhadas, 100% dos blocos textuais editoriais esperados são preservados na ordem e seção corretas, sem texto de outra seção, mistura de entidades ou concatenação destrutiva.
- **SC-004**: A repetição real sem mudança de conteúdo/proveniência registra a nova verificação, reutiliza os originais existentes e não acrescenta cópias brutas nem substitui a base preparada equivalente. Uma revisão simulada e uma mudança de associação territorial são detectadas e preservam o histórico anterior.
- **SC-005**: Testes de artigo incorreto, erro da fonte, conteúdo inconsistente/corrompido e interrupção parcial demonstram diagnóstico e retomada, preservação da versão válida e ausência de falsa conclusão nacional; os casos históricos de Cuba, Corvo, Gavião, Nazaré e Santa Cruz fazem parte das regressões de identidade.
- **SC-006**: A preparação pode ser reproduzida sem rede a partir dos originais e dependências fixados, produzindo o mesmo conteúdo e as mesmas relações de proveniência, salvo metadados operacionais explicitamente definidos; a origem legada e dados de outras fontes permanecem intactos.
- **SC-007**: O operador consegue executar coleta, preparação, consulta de cobertura e retomada com instruções documentadas e resultados verificáveis localmente, sem executar o notebook antigo nem depender de infraestrutura em nuvem. As provas real, simulada e de CI são identificadas separadamente.

## Assumptions

- A dimensão CAOP disponível no projeto define o universo de 308 municípios. Mudança desse universo requer revisão explícita; não será acomodada ignorando municípios ou aceitando mistura de versões.
- A Wikipedia tem cobertura editorial desigual. A feature exige cobertura contabilizada e honesta, sem garantir artificialmente que todos os municípios tenham o mesmo conjunto de temas ou volume de texto.
- Associação inicial e revisão de exceções podem exigir curadoria com evidência. O objetivo é tornar essa associação estável e auditável; não eliminar a curadoria por correspondência aproximada automática.
- Artigos podem combinar cidade e município; a abrangência deve ser explicitada e validada. Nenhum item Wikidata ou nome de página isolado substitui essa validação.
- O operador é o responsável pela ingestão local. O público final usará os textos em uma etapa futura de apresentação, fora desta feature.
- Coleta e preparação seguem as decisões de dados/armazenamento já aprovadas no projeto. Biblioteca, layout detalhado, modelos e estratégias de requisição serão definidos em `sdd-plan`.
- Não há nova credencial, API paga, recurso AWS ou custo recorrente contratado nesta especificação. Mudança dessa premissa deve passar pelos gates aplicáveis.
- Licença/atribuição e condições operacionais serão verificadas antes da coleta de implementação; licença do software/API não deve ser confundida com licença do conteúdo enciclopédico.

## Clarifications

### Session 2026-11-20

- Q: Qual núcleo de conteúdo deve orientar a especificação após a análise do legado? → A: O usuário concordou em seguir com a proposta de identidade municipal validada, bruto preservado, introdução, texto completo por seções, revisão/atribuição e relatório de cobertura.
- Q: Qual cobertura de idiomas deve entrar na primeira entrega da Wikipedia para os 308 municípios? → A: Português, guardando também a ligação para o artigo em inglês quando existir.
- Q: Onde esta feature deve terminar em termos de operação? → A: Coleta e preparação por comandos locais, prontas para futuro agendamento.
- Q: Como tratar os 308 TXT antigos, que incluem textos vazios e artigos incorretos? → A: Preservar no projeto antigo e coletar novamente da Wikipedia nesta feature.
- Escopo de imagens, declarações Wikidata, texto inglês, apresentação e implantação não foi ampliado. Identificador Wikidata e ligação inglesa são apenas metadados do artigo.
- A varredura de ambiguidades de interação, integração, não funcionais e estados de erro foi resolvida com os padrões existentes e a constitution, sem novas escolhas de stack ou infraestrutura. Ausência editorial é distinta de falha técnica, conforme o princípio de dados honestos.

## References

- [Análise do notebook, corpus legado e oportunidades](../../../.docs/reports/wikipedia-legado-oportunidades-2026-11-20.md).
- [Auditoria transversal de ingestão](../../../.docs/reports/auditoria-ingestao-2026-11-20.md).
- [Inventário de fontes, §3.3](../../../.docs/fontes_de_dados.md).
- [Plano geral, §6 e §12](../../../.docs/plano_plataforma_recomendacao_portugal.md).
- [Constitution](../../../.planning/memory/constitution.md) e [ADR-002](../../adr/ADR-002-arquitetura-base-mvp.md).
- Documentação oficial consultada na análise: [conteúdo de páginas](https://www.mediawiki.org/wiki/API:Get_the_contents_of_a_page), [parsing/revisões](https://www.mediawiki.org/wiki/API:Parsing_wikitext), [Pageprops](https://www.mediawiki.org/wiki/API:Pageprops), [ligações entre idiomas](https://www.mediawiki.org/wiki/API:Langlinks) e [conduta de uso](https://www.mediawiki.org/wiki/API:Etiquette). Detalhes de integração devem ser revalidados no planejamento.
