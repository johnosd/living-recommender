# Feature Specification: Idealista atual e relatório descritivo

**Slug**: `007-idealista-formato-atual-relatorio`
**Created**: 2026-11-17
**Status**: Implementada

## Scope
Revisitar a implementação 005, importar o lote atualizado de `J:/IdealistaScraper/.data/municipios/202611` e produzir relatório local reproduzível. Inclui hierarquia territorial nova, compatibilidade antiga, estatísticas descritivas e auditoria real. Fora: alterar/coletar no scraper, rede, nuvem, publicação, ranking, Gold e comparação temporal de preços entre amostras distintas.

## User Scenarios & Testing
### US1 — Importar e preparar o formato atual (P1)
Como operador, quero preservar JSON originais e aproveitar a hierarquia explícita, sem confundir distrito, ilha, município ou freguesia. O lote antigo continua funcionando; duplicatas e conflitos continuam auditáveis.
### US2 — Ler relatório confiável (P1)
Como analista, quero tamanho, cobertura CAOP, ausências, conflitos, tipologias e preços pedidos por município com amostra explícita. Região sem município não infla cobertura municipal.

## Functional Requirements
- **FR-001**: DEVE importar bytes do lote selecionado, com manifest, hashes e repetição unchanged, preservando raw anterior.
- **FR-002**: DEVE validar o conjunto opcional Região/Sub-região/Município/Freguesia: todos ausentes é legado; presença parcial ou tipo diferente de texto/nulo reprova. No formato novo, município nulo mantém nível regional, sem inferir pelo arquivo.
- **FR-003**: DEVE resolver por CAOP/seeds exatas, priorizando freguesia explícita sobre título. Município declarado desconhecido reprova; freguesia desconhecida fica nula. Freguesia rotulada como município pelo exportador exige seed explícita validada.
- **FR-004**: DEVE preservar metadados territoriais na preparação, deduplicação determinística e conflitos, sem dados pessoais. Falha mantém saídas vigentes e outras fontes.
- **FR-005**: DEVE gerar Markdown, JSON e CSV por município e município/tipologia, com n total e elegível. Preços ausentes ou conflitantes não entram em quartis; mediana/P25/P75 só com 10 preços elegíveis. Ausência não vira zero.
- **FR-006**: DEVE explicitar fonte, período, licença, run/hash, horário de coleta desconhecido, regra territorial, restrições de cobertura, preços pedidos versus contratos e não comparabilidade temporal dos lotes.
- **FR-007**: DEVE executar importação/build reais locais, verificar integridade e não publicar anúncios nem modificar origem.

## Success Criteria
- **SC-001**: Origem e raw idênticos; segunda importação não cria raw.
- **SC-002**: Contratos antigo/novo passam; distrito homônimo não recebe DICO municipal.
- **SC-003**: Totais e estatísticas reconciliam com dados locais reais e gates dbt passam.
- **SC-004**: Relatório entregue sem identificadores de anúncios/dados pessoais e com limitações explícitas.

## Clarifications
### Sessão 2026-11-17
O autor solicitou revisão, ingestão atualizada e relatório, indicando ambos os repositórios em J:. Inspeção: 74 JSON e 18.059 ocorrências em 202611; catálogo de links separado não é lista de anúncios. Relatório é descritivo/local, sem alterar critérios ou publicação.

## Assumptions
Mês da pasta é a referência declarada, sem comprovar instante individual de coleta. Hierarquia explícita descreve contexto de coleta, sem comprovar endereço de cada imóvel. Não presumir cobertura nacional completa ou esgotamento das páginas.
