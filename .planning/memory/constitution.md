<!--
Relatório de Impacto de Sincronização
- Mudança de versão: (nenhuma) -> 1.0.0
- Princípios modificados: nenhum (versão inicial)
- Seções adicionadas: Princípios Fundamentais (I–VII), Restrições do Projeto, Fora do Escopo do MVP, Quality Gates, Governança
- Seções removidas: nenhuma
- Pendências: região AWS (gate G1); confirmação das fontes condicionais AIMA e SNS
-->

# Constitution do living-recommender

## Princípios Fundamentais

### I. Nenhum segredo fora do cofre

- Nenhuma credencial (chave de API, token, senha, cookie de sessão, URL com credencial) DEVE ser versionada no Git, incluindo notebooks, fixtures de teste e arquivos de exemplo.
- Segredos do pipeline DEVEM vir do AWS SSM Parameter Store ou de um `.env` local listado no `.gitignore`.
- Nenhuma credencial de produção DEVE existir fora da conta AWS e do SSM (por exemplo, no laboratório Databricks, conforme o ADR-001).
- O CI DEVE rodar uma verificação de segredos em todo PR.

### II. Núcleo do produto estático e sem chave

- O ranking, o mapa, as fichas e o infográfico DEVEM funcionar só com os arquivos estáticos publicados em `published/vN`, sem servidor do projeto em tempo de consulta e sem nenhuma chave de API (ADR-002 D1).
- Integrações que exigem chave em tempo de uso DEVEM seguir BYOK (ADR-003): primeiro a chave do visitante, depois a chave do projeto (só se for restrita e habilitada em `config/providers.yml`), e por fim a funcionalidade desativada com explicação.
- Uma chave de LLM do projeto NÃO DEVE ser entregue ao navegador.
- Qualquer servidor ou API dinâmica DEVE ser aprovado antes por um ADR.

### III. Dados honestos e rastreáveis

- Nenhum valor DEVE ser inventado ou imputado em silêncio. Um indicador ausente aparece como ausente.
- Todo indicador publicado DEVE levar fonte, período de referência e licença.
- A junção entre fontes DEVE usar os códigos oficiais da CAOP (DICO/DICOFRE), resolvidos por seeds de sinônimos. Um município sem correspondência DEVE falhar o build, e uma freguesia sem correspondência DEVE gerar aviso e entrar no relatório de cobertura.
- A mediana de aluguel por anúncios só DEVE ser exibida com n ≥ 10. Abaixo disso, a interface mostra "amostra insuficiente".
- Indicadores herdados do município (ou do ACES) DEVEM aparecer sinalizados no drill-down.

### IV. Coleta responsável e licenciada

- Toda fonte DEVE estar registrada em `config/sources.yml`, com licença, método, frequência e responsável, antes de ter um coletor.
- Coletores DEVEM enviar um User-Agent identificado, limitar a taxa de requisições, usar retry com backoff e respeitar os termos da fonte e o `robots.txt`.
- A coleta do Idealista DEVE seguir o código de conduta (§3.4 do plano): manual, mensal, sem proxy, sem resolver captcha e parando ao primeiro bloqueio. Só agregados (mediana, P25–P75, n) DEVEM ser publicados.
- Uma exceção a termos de uso só é admitida como **risco aceito registrado** (por exemplo, as distâncias do Google em `.docs/fontes_de_dados.md`), com mitigação e uma alternativa documentada.

### V. Bruto imutável e publicação atômica

- Dados em `raw/` NÃO DEVEM ser sobrescritos nem editados. Cada ingestão grava um `run_id` novo com manifest (checksum, período de referência, método e licença).
- Um checksum igual ao do run anterior DEVE resultar em status `unchanged`, sem republicação.
- O `current.json` só DEVE apontar para uma versão nova depois de passarem todos os testes dbt e o quality gate de publicação. Uma falha em qualquer etapa mantém a versão vigente.

### VI. Privacidade por padrão

- O produto NÃO DEVE exigir cadastro nem usar rastreamento ou analytics de terceiros.
- As preferências do usuário NÃO DEVEM sair do navegador, exceto na URL compartilhável que o próprio usuário gera.
- Chamadas a serviços de terceiros a partir do navegador (Google Places, LLM) DEVEM ocorrer só por ação explícita do usuário, com aviso de qual serviço recebe a consulta.
- Dados pessoais de terceiros (endereço, coordenadas exatas e nome do anunciante) NÃO DEVEM ser publicados nem levados ao repositório.

### VII. Custo como requisito

- Toda feature que introduza um recurso com custo recorrente (serviço AWS, API paga, armazenamento relevante) DEVE trazer no plano a estimativa mensal e o impacto sobre a meta: menos de US$ 16,67/mês durante os créditos e menos de US$ 10/mês depois.
- Recursos AWS DEVEM ser criados só via Terraform, com tags de projeto, e cobertos pelo AWS Budgets.

## Restrições do Projeto

Fatos já decididos. Mudá-los exige um ADR novo ou uma emenda.

| Tema | Decisão | Origem |
|---|---|---|
| Nuvem e IaC | AWS serverless; Terraform; GitHub Actions com OIDC | ADR-002 D9 |
| Orquestração | MWAA Serverless (só operadores do Amazon Provider). Plano B: Step Functions + EventBridge | ADR-002 D2 |
| Transformação | dbt Core + DuckDB em ECS Fargate | ADR-001 |
| Laboratório | Databricks Free Edition fora do caminho crítico, só com extratos manuais | ADR-001 |
| Coletores | Python, um por fonte, executáveis como Lambda e em modo `--local` com o mesmo layout do S3 | ADR-002 D4; `.docs/fontes_de_dados.md` |
| Armazenamento | S3 `raw/` → `lake/{bronze,silver,gold}` → `published/vN` + `current.json` | ADR-002 D3 |
| Território | CAOP vigente; ranking por município; drill-down por freguesia; correspondência 2013→2025 | ADR-002 D5 |
| Recomendador | Biblioteca TypeScript pura (`packages/ranker/`), guiada pelo `criteria_catalog`, com contrato em JSON Schema (`packages/contracts/`) | ADR-002 D6 |
| Frontend | React com exportação estática, MapLibre GL, PT-BR + EN | ADR-002 D7 |
| Chaves de API | BYOK por padrão | ADR-003 |
| Região AWS | `eu-west-1` ou `eu-south-2`; **pendente** do gate G1 | Plano §4.5 |

## Fora do Escopo do MVP

Um plano que inclua algum destes itens DEVE ser sinalizado (FLAG) e precisa de aprovação explícita ou de um ADR:

- API dinâmica ou backend próprio em tempo de consulta;
- contas de usuário, login ou armazenamento de dados do usuário no servidor;
- modelo de ML de aluguel em produção (Fase B, só como previsões em lote, ADR-001);
- coleta automatizada do Idealista sem a API oficial;
- ranking principal por freguesia (a freguesia é só drill-down).

## Quality Gates

Uma mudança só está pronta quando:

1. **Lint e testes passam no CI:** `ruff` e `pytest` (Python), ESLint e testes (TypeScript).
2. **Coletores testados sem rede:** com fixtures gravadas e validação do schema do bruto.
3. **Modelos dbt alterados têm testes** (`not_null`, `unique`, `relationships` com `dim_*`, faixas aceitáveis), e `dbt build` passa.
4. **Mudanças no ranker passam nos golden tests** e no orçamento de desempenho (menos de 100 ms para o ranking completo).
5. **Mudanças de infraestrutura** apresentam `terraform plan` revisado no PR.
6. **A documentação acompanha a mudança:**
   - fonte nova ou alterada → `config/sources.yml` e `.docs/fontes_de_dados.md`;
   - decisão de arquitetura → ADR;
   - mudança de critério → `criteria_catalog`.
7. **Mensagens de commit** curtas, em inglês.

## Governança

- O autor do projeto é o único aprovador de emendas.
- Emendas são editadas à mão neste arquivo, com o Relatório de Impacto atualizado.
- Um ADR que contrarie um princípio DEVE citar a emenda correspondente; ADR e emenda são feitos juntos.
- Exceções pontuais em uma feature DEVEM ser registradas no Constitution Check do `plan.md`, com justificativa. Uma exceção recorrente indica que é preciso emendar.

A constitution usa versionamento semântico. Uma versão MAJOR denota remoção ou
redefinição incompatível de um princípio. Uma versão MINOR denota um novo
princípio ou expansão material da governança. Uma versão PATCH denota
esclarecimentos, correções ou mudanças de texto não semânticas.

**Versão**: 1.0.0 | **Ratificada**: 2026-11-03 | **Última Emenda**: 2026-11-03
