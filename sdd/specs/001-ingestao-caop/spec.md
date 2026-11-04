# Feature Specification: Fundação da ingestão e dimensão territorial CAOP

**Slug**: `001-ingestao-caop`

**Created**: 2026-11-03

**Status**: Em Execução

**Input**: "fundação da ingestão + CAOP — referências em .docs/" (ver `.docs/fontes_de_dados.md` §3 e `.docs/plano_plataforma_recomendacao_portugal.md` §5–§6)

## Escopo

### Incluído

- **Catálogo de fontes** (`config/sources.yml`) com a entrada da CAOP: licença, método, frequência e responsável.
- **Base comum dos coletores:**
  - download com identificação e retentativas;
  - cálculo de checksum;
  - escrita do manifest;
  - detecção de `unchanged`;
  - gravação no destino local ou S3, com o mesmo layout de chaves.
- **Coletor da CAOP vigente**, cobrindo Continente, Madeira e Açores, executável por um comando do operador em modo local.
- **Gravador S3** implementado e validado contra um S3 simulado, sem conta AWS real.
- **Projeto de transformação mínimo** seguindo as camadas já definidas no ADR-002: `raw/` preserva os arquivos originais, `lake/bronze/` faz o staging da CAOP e `lake/silver/` reúne as dimensões territoriais harmonizadas `dim_municipality` e `dim_parish` (a camada comum, ou SOT). Cada território inclui:
  - o código oficial;
  - o nome oficial e o nome normalizado;
  - a hierarquia (distrito/ilha → município → freguesia);
  - a área em km²;
  - o ponto representativo **dentro do polígono**.
- **Testes de qualidade** das dimensões.

### Fora de Escopo

- Deploy em AWS (Lambda/ECS), Terraform, workflows de orquestração e agendamento. Ficam para a spec de infraestrutura e para a spec 3.
- Outros coletores (Pordata, INE, Open-Meteo, Wikipedia, Censos, WWO, Idealista, distâncias, AIMA, SNS). Ficam para as specs 2 e 3.
- Geometrias simplificadas para a web (TopoJSON) e publicação em `published/vN`.
- Modelos especializados em `lake/gold/` (a camada especializada, ou spec); serão criados pelas features que consomem as dimensões territoriais.
- Tabela de correspondência de freguesias 2013→2025 (necessária só com os Censos, na spec 2).
- Seeds de sinônimos por fonte (`municipality_synonyms`, `parish_synonyms`).
- Histórico de versões da CAOP nas dimensões (`valid_from`/`valid_to`). As dimensões refletem só a versão vigente, e as versões antigas ficam preservadas no bruto.
- Migração de dados do legado (backfill).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Coletar a CAOP vigente com rastreabilidade (Priority: P1)

O operador (o autor do projeto) roda um único comando, que baixa a CAOP vigente da fonte oficial (Continente, Madeira e Açores) e a guarda como dado bruto imutável, junto com um manifest. O manifest registra de onde veio, quando foi coletada, a versão, a licença e o checksum de cada arquivo. Ao rodar de novo sem que a fonte tenha mudado, nada novo é gravado, e a execução é registrada como `unchanged`.

**Why this priority**: todas as outras fontes dependem do código oficial de município e freguesia (constitution, princípio III). Sem o bruto da CAOP rastreável, não existe dimensão territorial. Esta story também prova o padrão comum que os demais coletores vão seguir.

**Independent Test**: rodar o comando em modo local num diretório vazio e conferir os arquivos e o manifest no layout esperado. Rodar de novo e conferir o status `unchanged`, sem arquivos novos.

**Acceptance Scenarios**:

1. **Given** um destino local vazio, **When** o operador executa a coleta da CAOP, **Then** os arquivos das três regiões ficam gravados em `raw/source=caop/version=<ano>/run_id=<id>/`, e um manifest com status `changed` fica em `manifests/caop/<run_id>.json` com `source_url` como mapa `{continente, acores, madeira}`, `collected_at_utc`, `reference_period`/versão, `license_id`, `collection_method` e, por arquivo, `sha256` e tamanho.
2. **Given** uma coleta anterior bem-sucedida, **When** o operador executa a coleta de novo e a fonte não mudou, **Then** nenhum arquivo bruto novo é gravado e um manifest com status `unchanged` registra a verificação.
3. **Given** uma falha de rede no meio do download, **When** a coleta termina, **Then** nenhum arquivo parcial fica em `raw/`, um manifest com status `failed` registra o erro, e o comando sai com código de erro.
4. **Given** um arquivo baixado que não tem as camadas ou colunas esperadas, **When** a validação do bruto roda, **Then** a coleta falha com uma mensagem que identifica o arquivo e o campo ausente, e nada é marcado como `changed`.

---

### User Story 2 - Dimensões oficiais de município e freguesia (Priority: P2)

A partir do bruto mais recente da CAOP, o operador executa a transformação e obtém duas tabelas oficiais: municípios e freguesias. Cada território traz o código, o nome oficial, o nome normalizado, a hierarquia, a área e um ponto representativo garantidamente dentro do seu território. As tabelas passam por testes de qualidade, e uma violação interrompe a execução.

**Why this priority**: estas tabelas são a "chave universal" do projeto. As specs seguintes (clima por ponto, distâncias, junção do Pordata por nome) dependem delas. Esta story depende da US1 só pela existência do bruto.

**Independent Test**: com um bruto da CAOP já presente (real ou fixture), rodar a transformação e os testes, e conferir as contagens, a unicidade dos códigos, a integridade da hierarquia e que todo ponto representativo cai dentro do próprio polígono.

**Acceptance Scenarios**:

1. **Given** o bruto da CAOP vigente, **When** a transformação roda, **Then** `dim_municipality` tem exatamente 308 linhas, com `dico` único de 4 dígitos, e `dim_parish` tem uma linha por código de freguesia distinto da CAOP vigente, com `dicofre` único de 6 caracteres (`[0-9]{4}[0-9A-Z]{2}`), preservando os códigos oficiais alfanuméricos do campo `dtmnfr`.
2. **Given** as dimensões geradas, **When** os testes de qualidade rodam, **Then**:
   - toda freguesia referencia um município existente;
   - os 4 primeiros dígitos do `dicofre` são iguais ao `dico` do município;
   - nenhum nome, área ou ponto representativo é nulo;
   - toda área é maior que zero.
3. **Given** um município formado por várias partes (por exemplo, uma ilha com mais de um polígono, ou um município com exclave), **When** o ponto representativo é calculado, **Then** ele cai dentro de uma das partes do território, e nunca no mar nem num município vizinho.
4. **Given** um nome oficial com acentos ou caracteres especiais (por exemplo, "Vila Real de Santo António" ou "Calheta"), **When** a dimensão é gerada, **Then** o nome oficial é preservado exatamente como na fonte, e o nome normalizado segue uma regra única e documentada (minúsculas, sem acentos, espaços normalizados).
5. **Given** dois municípios homônimos em regiões diferentes (como Lagoa e Calheta), **When** a dimensão é gerada, **Then** eles são distinguidos pelo código e pela região autônoma ou distrito, nunca só pelo nome.

---

### User Story 3 - Mesmo coletor gravando no S3 (Priority: P3)

O operador escolhe o destino S3 (por configuração ou parâmetro), e a mesma coleta grava as mesmas chaves e o mesmo manifest no bucket indicado. Assim, quando a infraestrutura existir, o coletor roda na AWS sem mudar de lógica.

**Why this priority**: o modo local já entrega valor (US1 e US2). O destino S3 só é necessário quando a conta AWS existir. Mesmo assim, garantir agora que o layout é idêntico evita retrabalho.

**Independent Test**: executar a coleta contra um S3 simulado e comparar a lista de chaves e o conteúdo do manifest com os de uma execução local equivalente.

**Acceptance Scenarios**:

1. **Given** um S3 simulado vazio, **When** a coleta roda com destino S3, **Then** as chaves gravadas são idênticas, no layout, às da execução local, e o manifest tem o mesmo conteúdo, a menos de `run_id` e horários.
2. **Given** um destino S3 sem permissão de escrita, **When** a coleta roda, **Then** ela falha antes de baixar a fonte, com uma mensagem clara sobre o destino.
3. **Given** que nenhuma credencial está configurada, **When** o destino escolhido é o local, **Then** a coleta funciona normalmente, sem exigir nenhuma credencial.

---

### Edge Cases

- **CAOP em várias partes:** a fonte publica Continente, Madeira e Açores separadamente, possivelmente com sistemas de coordenadas diferentes. A dimensão precisa unificar as três num único referencial, com áreas calculadas num referencial métrico adequado a cada região.
- **Versão nova da CAOP com códigos alterados:** as dimensões passam a refletir só a nova versão. O bruto anterior permanece intacto e identificado pela versão.
- **URL da fonte mudou ou retornou HTML em vez do arquivo:** a validação do bruto falha com mensagem explícita. Nada é marcado como `changed`.
- **Execução concorrente da mesma fonte:** dois runs simultâneos não podem corromper um ao outro, porque cada `run_id` grava num prefixo próprio. O `unchanged` compara com o último manifest **bem-sucedido**.
- **Uniões de freguesias e freguesias desagregadas em 2025:** são tratadas como estão na CAOP vigente, cada `dicofre` como uma linha, com o tipo (freguesia ou união) preservado quando a fonte o informa.
- **Diretório local inexistente:** é criado automaticamente. Um bruto local já existente nunca é sobrescrito.
- **Download grande ou lento:** a coleta tem tempo limite e retentativas com espera crescente. Se esgotar, falha como no cenário 3 da US1.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE manter um catálogo de fontes versionado (`config/sources.yml`). A entrada da CAOP DEVE conter identificador, órgão publicador, licença, URL ou URLs, método de coleta, frequência e nível territorial.
- **FR-002**: Um coletor DEVE recusar a execução de uma fonte que não esteja no catálogo.
- **FR-003**: Toda requisição de coleta DEVE enviar um User-Agent identificado do projeto, respeitar um tempo limite e fazer retentativas com espera crescente.
- **FR-004**: O sistema DEVE gravar o bruto em `raw/source=<id>/<partição>/run_id=<id>/` sem nunca sobrescrever um bruto existente.
- **FR-005**: Toda execução, bem-sucedida, inalterada ou com falha, DEVE gerar um manifest com:
  - `source_id`, `run_id`, `collection_method`, `collected_at_utc`;
  - `source_release_date` ou versão, `reference_period`, `source_url` como mapa de URLs por região na CAOP, `license_id`;
  - por arquivo: chave, `sha256`, bytes e contagem de registros quando aplicável;
  - `schema_version`, `status` (`changed`, `unchanged` ou `failed`) e `error`.
- **FR-006**: Se o checksum de todos os arquivos for igual ao do último manifest `changed` da mesma fonte, o sistema DEVE registrar `unchanged` e não DEVE gravar bruto novo.
- **FR-007**: Uma falha em qualquer etapa DEVE deixar `raw/` sem arquivos parciais daquela execução e DEVE terminar o comando com código de erro.
- **FR-008**: O sistema DEVE validar o bruto da CAOP (presença das camadas e dos campos de código e nome esperados) antes de marcá-lo como `changed`.
- **FR-009**: O destino de gravação DEVE ser selecionável entre local e S3, e a lógica de coleta DEVE ser a mesma nos dois casos. O modo local DEVE usar, sob um diretório raiz configurável, o mesmo layout de chaves do S3.
- **FR-010**: O modo local NÃO DEVE exigir nenhuma credencial. Nenhuma credencial DEVE ser lida de arquivos versionados (constitution, princípio I).
- **FR-011**: O operador DEVE poder executar a coleta da CAOP por um comando único, com opções de destino e de "forçar verificação", e DEVE receber ao final um resumo com status, versão, arquivos e caminho do manifest.
- **FR-012**: O sistema DEVE gerar `dim_municipality` com: `dico`, nome oficial, nome normalizado, distrito ou ilha, região autônoma (quando houver), área em km² e latitude/longitude do ponto representativo dentro do polígono.
- **FR-013**: O sistema DEVE gerar `dim_parish` com: `dicofre`, `dico`, nome oficial, nome normalizado, tipo (quando informado pela fonte), área em km², latitude/longitude do ponto representativo dentro do polígono e a versão da CAOP de origem.
- **FR-014**: O staging da CAOP DEVE partir do bruto `changed` mais recente em `raw/` e compor a camada `lake/bronze/`. As dimensões `dim_municipality` e `dim_parish` DEVEM compor a camada comum `lake/silver/` e refletir só a versão vigente da CAOP. A versão da fonte, o período de referência e a data da coleta DEVEM permanecer identificáveis separadamente; a data de processamento não substitui a versão da fonte.
- **FR-015**: Testes de qualidade DEVEM verificar:
  - unicidade e formato dos códigos;
  - integridade da hierarquia freguesia → município (incluindo o prefixo do `dicofre`);
  - ausência de nulos nos campos obrigatórios;
  - área positiva;
  - ponto representativo contido no polígono;
  - 308 municípios.

  Uma falha DEVE interromper a execução.
- **FR-016**: A regra de normalização de nomes DEVE ser única, documentada e reutilizável pelas próximas fontes (para as seeds de sinônimos).
- **FR-017**: Toda a lógica de coleta e de transformação DEVE ser testável sem acesso à rede, usando fixtures gravadas (constitution, Quality Gates).

### Key Entities

- **Fonte (catálogo)**: identificador, publicador, licença, URLs, método, frequência e nível territorial.
- **Execução (run)**: uma tentativa de coleta de uma fonte, identificada por `run_id`, com status e horário.
- **Manifest**: o registro auditável de uma execução, com origem, versão, licença e arquivos com checksum.
- **Arquivo bruto**: os bytes como vieram da fonte, imutáveis, endereçados por fonte, partição e execução.
- **Município**: território oficial identificado por `dico`, com nome, hierarquia, área e ponto representativo.
- **Freguesia**: território oficial identificado por `dicofre`, pertencente a um município, com nome, tipo, área e ponto representativo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Num ambiente limpo, um único comando produz o bruto da CAOP e o manifest, e uma segunda execução sem mudança na fonte termina como `unchanged` sem gravar bruto novo.
- **SC-002**: As dimensões contêm 308 municípios e todas as freguesias da CAOP vigente, com 100% dos códigos únicos, 100% das freguesias ligadas a um município existente e 100% dos pontos representativos dentro do próprio território.
- **SC-003**: As execuções com destino local e destino S3 (simulado) produzem o mesmo conjunto de chaves e manifests equivalentes.
- **SC-004**: A suíte de testes da feature roda sem acesso à rede e passa no CI.
- **SC-005**: Uma falha simulada (rede, arquivo inválido ou destino sem permissão) nunca deixa arquivo parcial em `raw/` e sempre gera um manifest `failed`, ou uma mensagem de erro antes de qualquer gravação.

## Assumptions

- A DGT publica a CAOP vigente (versão de 2025, com a reorganização de freguesias) em formato geográfico para download, separada em Continente, Madeira e Açores, sob licença aberta que permite reutilização com atribuição. A licença exata e as URLs serão confirmadas no início da implementação e registradas no catálogo.
- A estrutura base do monorepo (projeto Python, pastas `pipelines/`, `config/` e `analytics/dbt/`, e CI básico) está sendo criada na Fase 0. Se ainda não existir, o primeiro bloco de tasks a cria no mínimo necessário para esta feature.
- O operador roda os comandos localmente, numa máquina com acesso à internet. Não há agendamento nesta feature.
- O número de freguesias não é fixado na spec, porque depende da versão vigente da CAOP. O de municípios (308) é estável.

## Clarifications

### Sessão 2026-11-03

- Q: Onde a fundação precisa rodar ao final desta spec? → A: Localmente (`--local`, com layout idêntico ao do S3), com o gravador S3 implementado e validado contra um S3 simulado. O deploy na AWS fica fora.
- Q: As dimensões entram nesta spec? → A: Sim, com um projeto de transformação mínimo (staging da CAOP + `dim_municipality` e `dim_parish`, testadas).
- Q: Quais derivados da CAOP entram agora? → A: Só centroides (pontos representativos) e áreas. Seeds de nomes por fonte, TopoJSON e a correspondência 2013→2025 ficam fora.
- Q: A fundação deve ser validada com um segundo coletor? → A: Não. Só a CAOP; o Pordata valida o padrão HTTP na spec 2.
- Q: Qual ponto representa cada território? → A: Um ponto garantidamente dentro do polígono (point-on-surface), não o centroide geométrico.
- Q: Como as dimensões tratam versões da CAOP? → A: Só a versão vigente; as versões antigas ficam preservadas no bruto.

### Sessão 2026-11-04

- Q: Como `raw`, SOT e base especializada se relacionam com a arquitetura do projeto? → A: São nomes conceituais para a arquitetura medalhão já adotada: `raw/` guarda os arquivos originais, `lake/bronze/` faz o staging, `lake/silver/` é a base comum harmonizada (SOT) e `lake/gold/` contém modelos especializados. Esta spec entrega `raw`, staging `bronze` e dimensões `silver`; modelos `gold` ficam fora do seu escopo.
- Q: Como preservar os 18 códigos de freguesia alfanuméricos encontrados na CAOP2025? → A: O autor aprovou manter exatamente os códigos oficiais de seis caracteres do campo `dtmnfr`, inclusive os que terminam em letras; `dicofre` é o nome da coluna normalizada nesta feature.
