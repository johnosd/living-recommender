# Auditoria da ingestão e da automação das fontes — 2026-11-20

## Resultado

A base de ingestão local já funciona para **sete fontes do catálogo**. O que
falta para operação recorrente é o encadeamento entre coletores e builds, a
política de atualização, o controle de prontidão e a implantação operacional.
Além disso, **Wikipedia, WWO e distâncias** continuam previstos sem implementação
neste repositório. **AIMA e SNS** dependem de avaliação antes de entrar no escopo.

As sete features convergidas não significam ingestão integralmente automatizada:
deploy, agendamento e outras fontes foram explicitamente deixados fora delas.
O Idealista continua com coleta manual por decisão vigente; suas etapas após a
entrega dos arquivos podem ser automatizadas.

## Escopo e método

- Checkout: `feature/007-idealista-formato-atual-relatorio`, HEAD
  `42a5f5982469db0c35e5cc2fb3dd190cc0ee0fd3`; árvore inicialmente limpa.
- Pasta encontrada: `.docs/`; não existe `.doc/` neste checkout.
- Documentos: [inventário de fontes](../fontes_de_dados.md),
  [plano geral](../plano_plataforma_recomendacao_portugal.md),
  [runbook](../runbooks/coletas.md) e
  [relatório Idealista](idealista-2026-11.md).
- Confronto com catálogo, coletores, CLIs, modelos/testes dbt, CI, ADRs,
  constitution, backlog, specs 001–007 e evidências locais em `.data/`.
- Usados os critérios de evidência e classificação de `sdd-converge`. Esta é
  uma auditoria transversal do plano, sem nova convergência formal ou alteração
  do status das features existentes.
- Sem nova coleta externa, build sobre o lake vigente, consulta à conta AWS,
  provisionamento, commit, push ou publicação. Disponibilidade atual dos
  provedores, preços, termos e elegibilidade AWS não foram revalidados.

## Estado por fonte

| Fonte | Implementação e evidência local conferidas | Falta para concluir/automatizar |
| --- | --- | --- |
| CAOP | `collect_caop` e `build_caop`; 308 municípios e 3.259 freguesias. Três ZIPs raw íntegros. | Executar sob agendamento/sob demanda; detectar e revisar nova edição; reconstruir dependentes de forma consistente. O catálogo está fixado em 2025. |
| Pordata | 17 CSV por HTTP e uma planilha manual; todos os 18 datasets têm estado local. Staging e cobertura existem. | Agendamento mensal, alertas de URL/schema, política de atualização e decisão sobre a planilha manual. |
| INE municipal | Três indicadores por API: rendas, criminalidade e poder de compra. | Encadear coleta/build, monitorar atualidade e explicar ausências oficiais. Novos indicadores exigem cadastro e validação próprios. |
| Open-Meteo | 308 municípios, 13 variáveis, 730 dias e 2.922.920 observações; sem lacunas na janela configurada. Retomada por cota e modo contínuo existem. | Renovar janela automaticamente ou por revisão controlada; planejar recoleta de revisões; invalidar estado quando coordenadas/território mudarem; executar em lotes persistentes e acionar o build após conclusão. |
| Correspondência INE de freguesias | Duas planilhas, 3.260 pares; relatório nacional com gate territorial. | Atualização vinculada à CAOP/leis, alerta sobre links/layout/licença e encadeamento com dependentes. |
| Censos | 201 itens raw; 61.921 observações preparadas, cobrindo 3.259 freguesias. `readiness.json`: `ready=true`, sem bloqueadores. | Gatilho por revisão/edição oficial e execução coordenada com dimensões/correspondência. A troca de edição exige revisar indicadores, categorias e universo territorial. |
| Idealista | Importação imutável, normalização, deduplicação e relatórios. Lote 2026-11: 74 JSON, 18.059 anúncios únicos, 54 municípios com amostra e 6.371 anúncios regionais. | Recepção explícita de um lote completo, disparo de importação/build, recibo e lembrete de atraso. A coleta externa permanece manual. Cobertura nacional não está demonstrada. |
| Wikipedia | Prevista em `.docs/fontes_de_dados.md` §3.3; sem fonte no catálogo, coletor ou CLI. | Cadastro, coletor, associação DICO→artigo com homônimos revisados, revisão do artigo, atribuição/licença, bruto/manifest, normalização e eventual backfill dos TXT legados. |
| WWO | Fallback descrito nos documentos; sem fonte no catálogo, coletor ou CLI atuais. A spec 003 o chama de fallback apenas no papel. | Confirmar papel e disponibilidade do acesso; cadastrar; coletar por coordenadas com uma credencial protegida; tratar cotas/schema e importar histórico com proveniência. Fallback automático entre provedores precisa de regra explícita. |
| Distâncias | Fonte `google_distances`, polos e CLI `compute-distances` previstos; ausentes do código/catálogo. | Catálogo de polos, distâncias em linha reta, integração de rotas para carro/transporte, chave, orçamento, ausência de rota e manifest. Prevista para v1, com recálculo quando polos/CAOP mudarem. API/preços/condições devem ser verificados antes da implementação. |
| AIMA | Proposta condicional; sem catálogo/coletor. | Verificar se há nacionalidade por município, formato e licença. Só depois decidir entrada e implementar download/extração, validação e resolução territorial. Dados apenas distritais não satisfazem a proposta. |
| SNS | Proposta condicional; sem catálogo/coletor. | Verificar extração estável e a unidade territorial realmente publicada; validar sua correspondência com municípios e a sinalização de herança. Não presumir que a estrutura ACES descrita no plano permaneça adequada. |
| POIs/OSM | Fase B; sem implementação. | Extrato, filtros de tags, validação e associação espacial a DICOFRE, se essa fase for aprovada. |
| Google Places | Consulta online da Fase B; sem implementação. | Integração futura sob ação do visitante, conforme BYOK. Não é uma ingestão recorrente para o lake. |

Evidência de implementação: [catálogo](../../config/sources.yml),
[coletores](../../pipelines/collectors), [CLIs](../../pipelines/cli),
[modelos dbt](../../analytics/dbt/models) e
[backlog das features](../../.planning/backlog.md).

GADM, Natural Earth, geocodificação Google legada e scraper Selenium foram
retirados pelo plano. Pordata 294, 445, 447, 582 e a planilha de proporção do
poder de compra foram excluídos do escopo da spec 002. Não são pendências
automáticas de migração. O 845 já foi adicionado posteriormente ao catálogo.

## Achados de implementação e operação

| ID | Tipo | Severidade | Origem/evidência | Trabalho restante |
| --- | --- | --- | --- | --- |
| A01 | Ausente | Alta | Plano §6; `.github/workflows/python.yml:3` declara apenas `push` e `pull_request`, com fixtures/testes. Não existem workflows de ingestão nem infraestrutura de execução versionada. | Orquestrar dependências, agenda por fonte, status do ciclo, retomada, timeouts, concorrência e notificações. |
| A02 | Parcial | Alta | Coletores aceitam `--s3`, mas `build_caop.py:94`, `build_observations.py:62`, `build_climate.py:44`, `build_parish_crosswalk.py:48`, `build_censos.py:111` e `build_idealista.py:54` operam sobre arquivos locais. | Preparar um workspace local isolado no executor a partir de um conjunto fixado de manifests/raw/dimensões; executar dbt e transferir/promover saídas validadas no armazenamento durável. Implementação S3 dos coletores não resolve essa passagem. |
| A03 | Parcial | Alta | `config/sources.yml:101–106`: frequência trimestral e janela fixa 2024-11-01→2026-10-31. `open_meteo/handler.py:18` e `collect_open_meteo.py:50` permitem encerrar com todos os municípios atuais sem nova rede. | Definir janela-alvo por ciclo, atraso aceitável e revisão de períodos já coletados. Reexecutar o comando com a configuração inalterada não atualiza a série para novos meses. |
| A04 | Parcial | Alta | `open_meteo/handler.py:18–21` compara período, modelo e variáveis/unidades; não compara ponto solicitado, versão/hash CAOP ou timezone. O build reutiliza esse predicado. | Incluir a identidade relevante da consulta/território na validade do estado, ou exigir invalidação/recoleta controlada ao alterar a dimensão. Evitar reutilizar silenciosamente dados de um ponto anterior com o mesmo DICO. |
| A05 | Ausente | Alta | Plano §6.2/§7.3/§12.2; `build_observations.py:62–86` seleciona últimos estados válidos e lista não coletados; `dataset_manifest.py:114` ignora falhas ao selecionar estado. O build pode concluir usando dados anteriores. | Gate operacional que distinga último sucesso, última tentativa, falha atual, coleta verificada sem mudança e período de referência. Definir fontes obrigatórias/opcionais e política de dados antigos/ausentes. Não transformar preservação da versão anterior em sucesso da atualização. |
| A06 | Parcial | Média | `config/sources.yml:66`: `manual_upload`; `pordata/handler.py:18` seleciona somente HTTP; importador Idealista exige pasta e mês. | Tratar explicitamente as entradas manuais. Poder de compra por API do INE já existe e cobre 308 municípios no lake; decidir se será a referência operacional e o Excel, comparativo/histórico. No Idealista, disparar apenas após confirmação de lote completo. |
| A07 | Parcial | Alta | `build_censos.py:118–123` possui lock de build; os demais builds usam candidatos, mas sem um mecanismo comum de coordenação. `_promote.py` troca diretórios sequencialmente com rollback para erros capturados. | Impedir execuções conflitantes, fixar versões das dependências, registrar o conjunto promovido e prever recuperação de interrupção abrupta. A atualização de várias fontes não é hoje uma transação única. |
| A08 | Ausente | Alta para o escopo integral | Inventário §3.3: Wikipedia, WWO e distâncias; ausentes do catálogo e dos módulos atuais. | Especificar/implementar por fonte. Distâncias são v1; WWO é fallback; preservar essa prioridade em relação ao núcleo já disponível. |
| A09 | Ausente | Média / condicional | Inventário §5: AIMA/SNS só entram se cumprirem condições. | Fazer avaliação de viabilidade; registrar inclusão ou descarte com evidências. Não apresentar essas fontes como entregas aprovadas nem como bloqueadores inevitáveis. |
| A10 | Parcial | Média | Inventário §3.4 ainda lista `censos2021/` como previsto; plano §6.3 usa `living.cli upload-snapshot`, inexistente; README mantém fases já iniciadas como “A fazer”. | Atualizar a visão corrente e os comandos. Preservar checkpoints históricos claramente datados e as decisões aprovadas; não reescrever specs convergidas para esconder diferenças. |

A04 foi conferido também por execução direta: um estado climático com a mesma
janela/modelo/variáveis, mas `requested_lat=0` e `requested_lon=0`, continua
aceito por `is_current_state`. Isso demonstra a falta de comparação no
predicado; não demonstra que os dados atualmente coletados usem pontos errados.

A07 não significa que a promoção atual não tenha proteção: os builds validam
candidatos e possuem rollback para falhas tratadas. Falta a garantia do ciclo
completo entre executores, fontes e interrupções de processo.

O CI existente comprova qualidade com dados simulados. Seus gatilhos não
implementam a rotina de ingestão. A distinção entre `push`/`pull_request` e
eventos de agendamento foi conferida na
[documentação oficial do GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
via Context7. Isso não propõe substituir a orquestração aceita no ADR-002.

## Cobertura e qualidade que a automação precisa interpretar

Conferência do lake existente, sem reconstruí-lo:

| Conjunto | Resultado observado | Implicação |
| --- | --- | --- |
| CAOP | 308 municípios / 3.259 freguesias | Fundação territorial disponível. |
| Pordata/INE | 21 datasets; 1.326.556 observações no staging | Todos os datasets atualmente cadastrados dessas duas fontes têm estado, incluindo o Excel manual. |
| Poder de compra | INE: 308/308 em 2023; Excel Pordata: 308/308 em 2021 | O acesso automático já existe, mas as séries não devem ser confundidas nem substituídas silenciosamente. |
| Rendas INE | 247/308 em 2025 | Há 61 municípios sem valor publicado; repetir a coleta não garante cobertura de 308. |
| Desemprego Pordata | 278/308 em 2024 | Ausências nas ilhas exigem interpretação explícita; não assumir zero. |
| Ensino não superior | 0/308 no período mais recente, 2024; último período com dados: 2023 | O relatório já distingue os dois períodos. Antes do uso analítico, definir a referência e sinalizar eventual uso de período anterior. Não se demonstrou falha do coletor. |
| Ensino superior | 63/308 com valor no período mais recente, 2025 | Verificar a semântica das ausências e símbolos; não confundir ausência com inexistência de estabelecimento. |
| Clima | 13 variáveis com 308/308 completos; zero dias ausentes | Completo para a janela fixada, sem comprovar atualização futura ou normais de longo prazo. |
| Censos | 61.921 próprias; zero herdadas/ausentes; prontidão aprovada | Escopo censitário atual completo localmente. |
| Idealista 2026-11 | 54/308 municípios com anúncios atribuídos; 42 com n elegível ≥10; 6.371 anúncios regionais | Processamento completo do lote recebido não certifica coleta nacional completa. Município nulo deve continuar regional. |

O relatório de observações verifica se existe algum valor por município/dataset
no último período. A cobertura por combinação de filtros fica para a camada
analítica, conforme o comentário de
`analytics/dbt/models/bronze/rpt_observation_coverage.sql`.

As fontes oficiais podem ter ausência legítima. O gate deve reprovar falhas
técnicas e ausências não explicadas, sem exigir valores que a fonte não publica.

## Ordem recomendada de implementação

1. **Contrato de operação das fontes atuais.** Criar uma spec para o ciclo
   automatizado: obrigatório/opcional, frequência, janela/edição,
   atualidade, ausência oficial, comportamento após falha e entradas manuais.
   Definir o papel do Excel sem remover o histórico. Resolver a política
   climática e a invalidação territorial antes do agendamento.
2. **Executor único local e repetível.** Encadear as CLIs existentes,
   registrar recibo do ciclo e versões/hash de dependências, controlar
   concorrência e produzir um relatório consolidado. A ordem é CAOP→dimensões;
   correspondência→Censos quando a compatibilização a exigir; demais builds
   dependem das dimensões. Idealista só começa depois da entrega completa.
   `unchanged` evita trabalho apenas quando código e dependências também
   continuam válidos; mudança de dimensão pode exigir novo processamento.
3. **Fontes ainda sem implementação.** Wikipedia como fonte pública prevista;
   WWO como fallback com histórico separado; mobilidade por polos conforme a
   entrega v1. Cada uma precisa de catálogo, contratos, fixture, coleta real e
   repetição idempotente. Avaliar AIMA/SNS em fluxo próprio antes de incluí-las.
4. **Implantação e agenda conforme o ADR-002.** Verificar G0/G1 e demonstrar
   a PoC G2 antes de assumir disponibilidade/custo do MWAA Serverless.
   Implementar infraestrutura, empacotamento dos executores, acesso ao S3,
   segredos aplicáveis, logs e alertas. Aplicar o plano B somente pelo critério
   já aprovado; esta auditoria não muda a escolha de orquestração.
5. **Aceite operacional.** Executar ciclo real completo, repetição sem
   alteração, alteração isolada de uma fonte, falha parcial, retomada após
   interrupção/cota, entrada manual atrasada e mudança de CAOP. Conferir
   integridade, cobertura, preservação dos dados anteriores e custo medido.

São frentes novas, não tasks implicitamente pendentes das sete features
convergidas. Esta auditoria não cria specs, modifica contratos ou reabre status.

## O que pertence a etapas posteriores

- O plano geral ainda prevê clima por freguesia e séries de 10–30 anos;
  a spec 003 entregou 24 meses por município. Há expansão de dados a planejar
  se esses requisitos do produto forem mantidos, com nova avaliação de cota e
  volume. Não chamar os 24 meses atuais de normais climáticas.
- Indicadores Silver/Gold, scores, TCI, perfis, ranker, TopoJSON,
  `criteria_catalog`, `published/vN` e `current.json` não estão concluídos.
  São etapas analíticas/de publicação posteriores à ingestão, com gates
  próprios. Os agregados locais Idealista da spec 007 não equivalem à
  publicação geral.
- A fonte Pordata e o Idealista têm restrições de uso registradas; o
  Open-Meteo gratuito tem restrição declarada no catálogo; a confirmação
  específica da licença das planilhas de correspondência permanece anotada.
  A auditoria preserva esses registros, sem dar nova aprovação de publicação.
- API oficial Idealista, POIs e Places pertencem à evolução prevista.
  Automatizar scraping externo do Idealista não é requisito desta entrega.

## Verificações executadas nesta auditoria

- **933 arquivos raw únicos referenciados** nos manifests locais foram
  encontrados e conferidos por SHA-256 e tamanho, totalizando 335.878.044
  bytes: CAOP 3; Censos 201; Idealista 398; INE 3; correspondência 2;
  Open-Meteo 308; Pordata 18. Zero divergências e zero referências com hashes
  conflitantes. Inclui os dois snapshots Idealista e não equivale a uma
  validação semântica integral de cada observação.
- Metadados dos Parquet, relatórios agregados e prontidão censitária lidos
  diretamente do lake vigente; manifests e estados de datasets conferidos.
- `uv run --locked python -m pytest tests/contracts -q --basetemp .data/tmp/audit-ingestion-20261120-contracts`:
  **34 passed em 4,89 s**, sem rede.
- Execução direta do predicado de validade climática conforme A04.
- A suíte geral, novos builds dbt, novas coletas, CI remoto e AWS real não
  foram executados. Evidências históricas desses níveis não foram promovidas
  a verificações atuais desta auditoria.

Para considerar a ingestão automatizada concluída, o ciclo precisa funcionar
sem intervenção entre os gatilhos autorizados e a saída validada, explicar
pendências e falhas, retomar com segurança e provar a operação no ambiente
escolhido. A extração manual Idealista permanece a exceção deliberada.
