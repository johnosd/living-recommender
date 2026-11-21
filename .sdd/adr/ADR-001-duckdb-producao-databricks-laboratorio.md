# ADR-001: DuckDB como motor de produção e Databricks como laboratório

## Status

Aceita

## Data

2026-11-03

## Contexto

O living-recommender processa, uma vez por mês, as fontes públicas (CAOP, Pordata/INE, Censos, Open-Meteo/WWO, Wikipedia) e os anúncios do Idealista, que são coletados manualmente. A transformação vai das camadas bronze e silver até a gold, e o resultado é publicado como JSON/TopoJSON estático em `published/vN`. As premissas do plano (`.docs/plano_plataforma_recomendacao_portugal.md`) são:

- **Volume pequeno.** Um snapshot real do Idealista tem cerca de 34 MB (17 mil anúncios). Mesmo com anos de coletas mensais, o total processado fica abaixo de 1 GB.
- **Orçamento.** A meta é ficar abaixo de US$ 10/mês na AWS depois dos créditos, e a estimativa atual é de US$ 1–4/mês.
- **Orquestração.** Usamos MWAA Serverless, que aceita só operadores do Amazon Provider (`EcsRunTaskOperator`, `LambdaInvokeFunctionOperator`…).
- **Fases.** A Fase A é portfólio; a Fase B é produto, com possível uso comercial.
- **Capacidade.** O autor tem 5–10 h por semana.
- **Portfólio.** Experiência com Spark, Delta Lake, Unity Catalog e MLflow tem valor de currículo.

O dbt Core fica na transformação em qualquer cenário. A decisão aqui é qual **motor** executa os modelos dbt em produção e qual é o papel do Databricks Free Edition.

## Decisão

**Produção:** dbt Core com o adapter `dbt-duckdb`, executado como tarefa ECS Fargate disparada pelo MWAA Serverless (`EcsRunTaskOperator`). A tarefa lê `s3://…/raw` e escreve bronze, silver e gold em Parquet. Uma tarefa `publish` gera `published/vN`.

**Laboratório:** Databricks Free Edition, **fora do caminho crítico** da produção, com estas entregas planejadas:

1. **EDA:** padrões demográficos, imobiliários e climáticos.
2. **Pipeline espelho do Idealista:** silver e gold do aluguel em PySpark e Delta Lake, com os resultados comparados aos do dbt como teste de consistência.
3. **Modelo de aluguel (Fase B):** experimentos registrados no MLflow. O modelo validado gera **previsões em lote** por município e freguesia, que entram na produção como seed ou arquivo versionado consumido pelo dbt. Não há inferência online nem API.
4. **`dbt-databricks` experimental (opcional):** um target que roda só alguns modelos, sem paridade obrigatória e fora do CI.

Regras do laboratório:

- Nenhuma credencial da conta AWS de produção fica no Databricks. Os dados chegam por extratos enviados manualmente.
- O artefato que volta para a produção (as previsões) passa por PR e pelos testes dbt, como qualquer outro dado.
- O código fica em `databricks/` (`notebooks/`, `experiments/`, `bundles/` com Databricks Asset Bundles). O README da pasta deixa claro que ela não faz parte da produção.

## Alternativas Consideradas

### Databricks Free Edition como motor de produção

- Executar os modelos dbt (`dbt-databricks`) ou jobs PySpark na Free Edition no lugar do DuckDB.
- **Rejeitada:**
  - Os termos da Free Edition **proíbem uso comercial**, o que inviabiliza a Fase B e tornaria certa uma migração futura.
  - O local de armazenamento personalizado não é suportado, e a internet de saída fica restrita a uma lista de domínios não publicada. Ler o S3 raw e escrever em `published/` exigiria credenciais da AWS dentro de um ambiente gratuito de terceiros, sem garantia de que a conexão funcione.
  - Não há operador do Databricks no MWAA Serverless. Seria preciso uma Lambda que chama a API de Jobs e acompanha a execução, com um token adicional em SSM.
  - Não há SLA, e há cotas (um SQL warehouse 2X-Small e no máximo 5 tarefas de job simultâneas). A publicação mensal ficaria dependente de um serviço sem garantia.
  - O CI precisaria de um workspace remoto. Com DuckDB, `dbt build` roda no GitHub Actions e localmente, sem rede e sem custo.
  - Com menos de 1 GB, o Spark não traz ganho de desempenho, e a inicialização do cluster pesa mais que o próprio processamento.

### Databricks pago (AWS) como motor de produção

- Workspace pago, com compute serverless ou jobs clusters, acionado pelo MWAA via Lambda.
- **Rejeitada:** o custo recorrente da plataforma e de DBU ameaça a meta de US$ 10/mês para um volume que uma tarefa Fargate de minutos resolve. A complexidade de operação (workspace, Unity Catalog, credenciais entre contas) também não se justifica para 5–10 h semanais.

### Databricks na Fase A e migração para DuckDB antes da Fase B

- Maximizar o portfólio em Spark usando o Databricks como motor só durante a fase de portfólio.
- **Rejeitada:** a migração seria certa e cairia no meio do roteiro, consumindo a capacidade limitada do autor. O ganho de portfólio é obtido de forma equivalente pelo laboratório.

### Dois targets dbt (DuckDB e Databricks) com paridade obrigatória

- Manter todos os modelos compatíveis com os dois adapters e rodar ambos no CI.
- **Rejeitada:** as diferenças de dialeto SQL (funções de data, tipos, macros) exigem `adapter.dispatch` ou SQL duplicado, um custo de manutenção constante sem benefício para o usuário final.

### DuckDB + dbt em ECS Fargate (escolhida)

- **Aceita:** cabe no volume e no orçamento, tem operador nativo no MWAA Serverless (`EcsRunTaskOperator`), roda igual no notebook, no CI e na produção, e mantém os dados e as credenciais dentro da conta AWS.

## Consequências

### Positivas

- O custo de transformação fica em centavos por mês (uma tarefa Fargate curta).
- `dbt build` é reproduzível localmente e no CI com dados de amostra, sem dependência externa.
- Os dados de produção e as credenciais ficam só na conta AWS.
- O laboratório pode quebrar, expirar ou mudar de termos sem afetar o site.
- O portfólio ganha entregas concretas em Spark, Delta e MLflow, incluindo uma comparação mensurável com o pipeline de produção.

### Negativas

- O Spark e o Databricks não fazem parte do pipeline de produção. A experiência de portfólio é de laboratório, não de operação.
- O pipeline espelho duplica parte da lógica do Idealista em PySpark. Esse trabalho foi aceito como investimento de aprendizado e precisa ser mantido em dia, ou marcado como desatualizado.
- O DuckDB roda em máquina única. Se o volume crescer muito, será preciso migrar (ver abaixo).
- A transferência das previsões em lote do laboratório para a produção é manual na Fase B, o que exige disciplina de PR e testes.

### Caminho de Migração / Evolução Futura

Reavaliar esta decisão se ocorrer qualquer um destes gatilhos:

- os dados processados passam de **~50 GB**, ou o `dbt build` passa de **30 min** no Fargate (até 16 vCPU / 120 GB);
- surge a necessidade de **inferência online** (previsão para um imóvel descrito pelo usuário);
- o orçamento passa a comportar um **Databricks pago**, e há ganho claro (Unity Catalog para vários colaboradores, streaming etc.).

Como migrar: os modelos dbt são o ativo portável. Basta criar um target `dbt-databricks` (ou outro motor de warehouse), ajustar as macros com diferenças de dialeto via `adapter.dispatch` e trocar a tarefa ECS por uma Lambda que dispara um Databricks Job pela API, já que o MWAA Serverless não tem operador do Databricks. Os contratos de saída (`published/vN` e o JSON Schema em `packages/contracts/`) não mudam, então o site não é afetado.
