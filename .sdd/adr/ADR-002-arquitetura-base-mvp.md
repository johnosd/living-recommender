# ADR-002: Arquitetura base do MVP

## Status

Aceita. Dois pontos ficam em aberto e dependem dos gates do plano:

- a **região AWS** (`eu-west-1` ou `eu-south-2`) depende da disponibilidade do MWAA Serverless (G1);
- o **formato do recomendador** (D6) está aceito como direção, mas será validado no protótipo.

O motor de transformação está decidido em [ADR-001](ADR-001-duckdb-producao-databricks-laboratorio.md) e não é repetido aqui.

## Data

2026-11-03

## Contexto

O living-recommender é uma plataforma web pública, anônima e bilíngue (PT-BR + EN) que recomenda onde morar em Portugal. A pessoa informa quanto pode pagar de aluguel e qual tipologia quer, escolhe o clima preferido e, para cada critério (cultura, economia, emprego, educação, população, comunidade estrangeira, saúde, segurança, distância a capitais…), indica "não importa", dá um peso de 0 a 5 ou define uma faixa de valores aceitáveis. O sistema aplica essas preferências sobre uma **base vigente já processada** e mostra o resultado como infográfico. Ao abrir um município, a pessoa vê as freguesias dele ordenadas pelos mesmos critérios.

Restrições que orientaram as escolhas, definidas na entrevista de 2026-11-03 (detalhes em `.docs/plano_plataforma_recomendacao_portugal.md`):

- **Objetivo em fases:** portfólio primeiro (Fase A) e produto depois (Fase B).
- **Custo:** até US$ 16,67/mês durante os créditos AWS e menos de US$ 10/mês depois. A estimativa atual é de US$ 1–4/mês.
- **Capacidade:** uma pessoa, de 5 a 10 h por semana. Operação e manutenção precisam ser mínimas.
- **Dados:** o volume fica abaixo de 1 GB. As fontes públicas mudam no máximo uma vez por mês, e um snapshot do Idealista tem cerca de 17 mil anúncios.
- **Idealista:** a API oficial já foi solicitada e está pendente. Até lá, a coleta precisa ser sustentável e respeitar as regras do site.
- **Legado:** os repositórios `MPAlugueisLisboa` e `IdealistaScraper` tinham segredos versionados e um scraper com proxy. O projeto novo começa limpo.

## Decisão

### D1. Entrega estática e ranking no navegador, sem API no MVP

O pipeline mensal publica arquivos estáticos (JSON, TopoJSON e `criteria_catalog`). O site, também estático, baixa esses arquivos pelo CloudFront e calcula o ranking **no dispositivo**. As preferências nunca vão para um servidor. Ficam no `localStorage` e podem ser compartilhadas na URL.

### D2. Orquestração com MWAA Serverless

O MWAA Serverless executa os workflows mensais. Como ele só aceita operadores do Amazon Provider, toda tarefa vira uma Lambda (`LambdaInvokeFunctionOperator`) ou uma tarefa ECS Fargate (`EcsRunTaskOperator`). Os workflows são publicados pela AWS CLI no CI, já que não há recurso Terraform confirmado para eles.

**Plano B:** se a PoC da Fase 1 reprovar o MWAA Serverless em disponibilidade na região, elegibilidade aos créditos ou custo, o projeto passa a usar Step Functions + EventBridge Scheduler, sem mudar as tarefas.

### D3. Armazenamento em camadas e publicação versionada

O S3 é organizado em camadas:

```text
s3://<bucket>/
  raw/<fonte>/<data>/…           # imutável, com manifest por lote
  bronze/ silver/ gold/          # Parquet, produzido pelo dbt
  published/v<N>/…               # JSON/TopoJSON consumidos pelo site
  published/current.json         # ponteiro para a versão vigente
```

O `current.json` só é atualizado depois que todos os testes dbt e a checagem de regressão passam. O rollback consiste em apontá-lo de volta para `v<N-1>`.

### D4. Coleta

- **Fontes públicas:** uma Lambda Python por fonte (CAOP, Pordata/INE, Censos, Open-Meteo, WWO, Wikipedia). Cada uma grava em `raw/` com manifest.
- **Idealista:** coleta **manual e mensal** pela extensão Chrome, enviada com a CLI de upload, até a API oficial sair. O código de conduta é obrigatório: sem proxy, sem resolver captcha, a coleta para ao primeiro bloqueio, respeita o `robots.txt` e roda no máximo uma vez por mês. O produto publica **só agregados** (mediana, P25–P75 e n) e nenhum anúncio individual.

### D5. Granularidade: município, com drill-down por freguesia

O território vem da CAOP (DGT), com os códigos DICO (município) e DICOFRE (freguesia). O ranking principal é feito por município. O drill-down por freguesia usa indicadores próprios quando existem, como os Censos e o aluguel com amostra suficiente. Os demais são herdados do município, e a herança aparece sinalizada na interface. Uma tabela de correspondência trata a reorganização das freguesias de 2013 a 2025. A v0 sai só com municípios, e as freguesias entram na v1.1.

### D6. Recomendador multicritério explicável, em TypeScript

O recomendador é uma biblioteca TypeScript pura (`packages/ranker/`), guiada pelo `criteria_catalog` publicado pelo pipeline. Cada critério aceita quatro modos: não importa, peso de 0 a 5, faixa (filtro eliminatório) e opção categórica. O score é uma média ponderada transparente de indicadores normalizados. Um território só entra no ranking se a cobertura dos critérios escolhidos for de pelo menos 0,7. A biblioteca tem golden tests no CI e precisa calcular o ranking em menos de 100 ms. Um JSON Schema em `packages/contracts/` define o contrato entre a saída do dbt e o ranker.

### D7. Frontend

React com exportação estática, mapas com MapLibre GL, i18n PT-BR + EN, sem conta e sem rastreamento. O resultado é um painel infográfico: mapa, os melhores territórios, o motivo de cada um aparecer, a comparação com a média de Portugal, o aluguel em relação ao orçamento, o clima mês a mês e as distâncias. Até haver um domínio próprio, o site usa o domínio padrão do CloudFront.

### D8. Métodos de dados do MVP

- **Aluguel:** estatística descritiva dos anúncios mais as rendas medianas do INE. A mediana só é exibida com n ≥ 10; abaixo disso, a interface mostra "amostra insuficiente". O modelo de ML fica para a Fase B, com previsões em lote (ADR-001).
- **Clima:** médias históricas de 10 a 30 anos do Open-Meteo, mais a janela recente do WWO (uma chave, guardada como segredo), calculadas por centroide do município.
- **Mobilidade:** distâncias pré-calculadas até polos fixos (Lisboa, Porto, Faro, aeroportos e sede de distrito).

  **Atualização (2026-11-03):** a mobilidade tem três modos selecionáveis na v1: linha reta (haversine), carro e transporte público. Os tempos de carro e de transporte vêm do Google Distance Matrix, **calculados uma única vez** por uma CLI local e guardados em `raw/`. O autor aceitou o risco de termos de uso do Google, porque a alternativa com motor de rotas próprio (`r5py` + OSM + GTFS da CP) foi considerada complexa demais. Ela fica registrada como substituição caso o Google conteste ou o projeto entre na Fase B comercial. O Google Places entra como enriquecimento **online** no navegador, sob demanda e sem gravar resultados. O clima usa o Open-Meteo como fonte principal e o WWO como fallback. Detalhes em `.docs/fontes_de_dados.md` §3.3.

### D9. Plataforma, repositório e segurança

- AWS serverless (Lambda, ECS Fargate, S3, CloudFront com OAC, SSM Parameter Store, ECR, CloudWatch, Budgets), toda provisionada com **Terraform**.
- GitHub Actions com **OIDC**, sem chaves de acesso de longa duração. Todo PR passa por lint, testes, testes dbt e `terraform plan`.
- Monorepo privado `living-recommender` com `apps/web`, `packages/{ranker,contracts}`, `pipelines/`, `extension/idealista`, `analytics/dbt`, `databricks/`, `infrastructure/terraform` e `config/sources.yml`.
- **Nenhum segredo no Git.** As credenciais ficam no SSM ou em `.env` local, que o Git ignora. As credenciais expostas nos repositórios legados são rotacionadas, e o histórico deles é limpo antes de qualquer reaproveitamento.

## Alternativas Consideradas

### API dinâmica (FastAPI em Lambda ou container) para calcular o ranking

- O cliente envia as preferências e o servidor devolve o ranking.
- **Rejeitada:** o ranking depende só de dados que mudam uma vez por mês e de poucas centenas de territórios. Uma API acrescentaria cold start, superfície de ataque, custo por requisição e operação contínua sem nenhum ganho para quem usa. Também enviaria as preferências a um servidor, contrariando a privacidade por padrão. Fica como opção na Fase B se surgir inferência por imóvel ou conta de usuário.

### Ranker em Python, no pipeline ou na API

- Calcular o ranking em Python e publicar resultados prontos, ou servi-los pela API.
- **Rejeitada:** as combinações de pesos e faixas são infinitas, então não dá para pré-calcular. Manter um ranker em Python e outro em TypeScript criaria duas implementações que podem divergir.

### Step Functions + EventBridge como orquestrador principal

- Mais barato e com suporte nativo no Terraform.
- **Rejeitada como primeira opção:** a escolha do autor foi o MWAA Serverless, pelo valor de portfólio do Airflow. Fica registrada como **plano B** (D2), com as mesmas tarefas Lambda e ECS.

### MWAA provisionado (ambiente Airflow tradicional)

- Airflow completo, com qualquer provider (inclusive o Databricks).
- **Rejeitada:** o custo fixo do ambiente provisionado, que fica ligado o tempo todo, estoura a meta de menos de US$ 10/mês.

### Scraper automatizado do Idealista (Selenium/Lambda com proxy)

- Continuar a abordagem do `IdealistaScraper.py` legado.
- **Rejeitada:** contornar bloqueios com proxy e captcha viola as regras do site e expõe o projeto a bloqueio e risco jurídico. A coleta manual, de baixa frequência e só com publicação de agregados é o compromisso sustentável até a API oficial.

### Granularidade apenas por município

- O modelo mais simples, com todos os indicadores disponíveis no mesmo nível.
- **Rejeitada:** o autor quer recomendar algo menor que o município. Lisboa e Porto, por exemplo, escondem diferenças grandes entre bairros.

### Ranking principal por freguesia

- Usar as cerca de 3 mil freguesias como unidade principal.
- **Rejeitada:** a maior parte dos indicadores (Pordata/INE) só existe por município, e o aluguel só tem amostra suficiente (n ≥ 10) em cerca de 195 localidades. Um ranking nacional por freguesia seria feito quase todo com dados herdados, o que daria uma falsa precisão.

### Modelo de ML de aluguel no MVP

- Reaproveitar o CatBoost do TCC (R² ≈ 0,78, só Lisboa, 2023).
- **Rejeitada para o MVP:** o modelo foi treinado em outra região e período, com divisão aleatória, sem validação temporal. Um modelo nacional precisa de pelo menos 3 snapshots. Fica para a Fase B.

### SPA com framework de servidor (Next.js com SSR)

- Renderização no servidor para SEO e páginas dinâmicas.
- **Rejeitada:** exige computação em tempo de requisição. A exportação estática atende ao SEO das páginas de município e cabe no S3 + CloudFront.

## Consequências

### Positivas

- O custo não cresce com o número de usuários. O tráfego é só CDN, e a computação acontece uma vez por mês.
- A privacidade é garantida por construção: nenhuma preferência sai do navegador.
- A operação se resume a uma execução mensal com publicação atômica e rollback trivial.
- O recomendador é testável de forma isolada (golden tests) e explicável na interface.
- O Idealista é coletado de forma defensável, e os dados individuais nunca são expostos.

### Negativas

- **Tamanho do download:** o navegador baixa a base vigente inteira. Isso funciona com centenas de municípios e com as freguesias carregadas sob demanda por município, mas não escala para dados por imóvel.
- **Sem dados em tempo real:** os indicadores têm a defasagem do ciclo mensal e das próprias fontes.
- **Dependência do autor:** a coleta manual do Idealista exige ação humana todo mês. Se ela atrasar, o aluguel fica desatualizado, e a interface mostra a data de referência.
- **Riscos do MWAA Serverless:** o serviço é recente e restrito ao Amazon Provider, e os workflows ficam fora do Terraform. Esses riscos foram aceitos e têm plano B.
- **Herança de indicadores:** o drill-down por freguesia mostra indicadores herdados do município. A sinalização na interface é obrigatória para não sugerir uma precisão que não existe.
- **Risco aceito no Idealista:** mesmo a coleta manual depende da tolerância do site até a API oficial (§14 do plano).

### Caminho de Migração / Evolução Futura

| Gatilho | Revisão |
|---|---|
| Inferência por imóvel, contas de usuário ou base publicada acima de ~5 MB por carga | Introduzir uma API (Lambda + HTTP API) só para essa função, mantendo o ranking no cliente |
| PoC do MWAA Serverless reprovada (G1) ou custo acima do previsto | Migrar para Step Functions + EventBridge; as tarefas Lambda e ECS não mudam |
| API oficial do Idealista aprovada | Substituir a extensão por um coletor Lambda; o contrato do `raw/` e do Silver se mantém |
| Fontes com indicadores por freguesia (saúde e educação georreferenciadas) | Reduzir a herança no drill-down; avaliar o ranking principal por freguesia |
| Pelo menos 3 snapshots do Idealista | Modelo de aluguel da Fase B (ADR-001) |

Cada subdecisão (D1–D9) pode ser emendada isoladamente por um ADR novo que aponte para a seção afetada.
