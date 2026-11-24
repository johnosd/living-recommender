# Backlog

Painel único de ideias futuras e status de features/bugs geridas pelo
sistema sdd-*. Mantido automaticamente por update-feature-status.ps1 e
update-bug-status.ps1.

## Ideias Futuras

- **2026-11-17 — Enriquecimento geográfico posterior dos anúncios Idealista:** recuperar município/freguesia combinando nomes e contexto territorial com a CAOP; geocodificar endereços parciais dos títulos quando necessário, preservando proveniência e precisão. A exploração encontrou 2.792 candidatos municipais únicos entre 6.371 anúncios regionais, ainda sem validação ou promoção ao lake. Próximo passo: definir um piloto de 100 anúncios para medir acurácia, ganho de cobertura e custo; escolher provedor e verificar licença/persistência (OpenCage como candidato; Google condicionado ao enquadramento contratual; não depender do Nominatim público para lotes recorrentes). Provedor, orçamento e implementação permanecem pendentes de decisão. [Avaliação e diagnóstico](../.sdd/assessments/enriquecimento-geogrfico-posterior-dos-anncios-idealista/explora.md).

- **2026-11-22 — Fase 3: marts de indicadores e `criteria_catalog` (próximo passo):** a mobilidade (spec 009) está concluída e a coleta real foi feita (1.404 pares de carro, sem falhas, staging `stg_municipality_pole_distance` com 3.562 linhas), então as fontes principais já estão no lake. Construir os marts municipais (e de freguesia, quando houver dado) com os indicadores do catálogo do MVP e o `criteria_catalog` versionado (plano §8.1 e §8.2), que alimenta o ranker. O catálogo também serve de checagem final da ingestão: cada critério precisa apontar para um dado existente no lake. Confirmar antes o estado das Fases 0 e 1 (segredos, AWS, PoC MWAA), que aparecem desmarcadas no checklist do plano (§16), já que a Fase 3 prevê `dbt build` contra o S3.
- **2026-11-22 — Mobilidade: pendências pós-coleta (não bloqueiam a Fase 3):**
  - Os marts devem usar `stg_municipality_pole_distance` com a atribuição "Tempos de viagem: Google" e o risco aceito de termos de uso (ADR-002 D8, ADR-004); a linha reta (`source_id` `caop`) não tem essa restrição.
  - Conferir a coleta com um par conhecido no Google Maps (Lisboa→Porto: 317,5 km e 181 min no staging, a partir dos centros dos municípios).
  - Coordenadas de OPO, FAO, FNC e PDL seguem aproximadas (erro ~1 km, risco aceito pelo autor em 2026-11-22). Corrigi-las deixa os pares do polo `stale` e custa uma recoleta (~200 elementos por polo).
  - A chave `GOOGLE_CV20_API_KEY` foi mantida, de uso exclusivo deste projeto (decisão do autor). Revisar a restrição de API da chave antes de qualquer uso novo.
  - A cota gratuita divergiu: a página do Google lista 10.000 elementos/mês no nível Essentials, e o autor informou 1.000; o catálogo usa 1.000 (conservador). Conferir o gasto real em Faturamento, no Google Cloud.
  - Ajuste pequeno (`sdd-adhoc`): o texto da estimativa diz "dentro dos tetos gratuitos mensais" mesmo quando há custo (`pipelines/cli/collect_mobility.py:44`).
  - Opcional, só se houver demanda: habilitar o transporte público (`transit`, suportado por catálogo e desabilitado pelo ADR-004) ou ampliar a lista de polos. Só os pares novos são cobrados, e o transporte público traz os riscos R-002 e R-005.
  - Os docs históricos da spec 009 (`plan.md`, `data-model.md`, `quickstart.md`, `research.md`, `contracts/mobility-cli.md`) ainda citam `GOOGLE_ROUTES_API_KEY`; o contrato e o fixture travados usam esse nome como valor fictício.
- **2026-11-20 — Pendências que não bloqueiam a Fase 3:** AIMA/SNS está em `needs-clarification` por falta de enquadramento de reutilização do dataset SNS ([decisão](../.sdd/assessments/viabilidade-das-fontes-aima-sns/decision.md)); o recorte de brasileiros já vem do Pordata 354. O WWO segue apenas como fallback do Open-Meteo.

## Features

| Slug | Título | Status | Progresso | Última Atualização |
| --- | --- | --- | --- | --- |
| 001-ingestao-caop | Fundação da ingestão e dimensão territorial CAOP | Convergida | 50/50 tasks | 2026-11-11 |
| 002-ingestao-pordata-ine | Ingestão Pordata e INE — coleta rastreável e staging por município | Convergida | 54/54 tasks | 2026-11-11 |
| 003-ingestao-clima-open-meteo | Ingestão de clima Open-Meteo — coleta diária por município e staging | Convergida | 62/62 tasks | 2026-11-11 |
| 004-correspondencia-freguesias | Correspondência de freguesias 2013→2025 — coleta das tabelas do INE e tabela de correspondência | Convergida | 46/46 tasks | 2026-11-12 |
| 005-importacao-idealista-manual | Importação de snapshots manuais do Idealista | Convergida | 12/12 tasks | 2026-11-13 |
| 006-censos-2021-freguesia | Censos 2021 por freguesia — coleta e preparação de população e faixas etárias | Convergida | 35/35 tasks | 2026-11-13 |
| 007-idealista-formato-atual-relatorio | Idealista atual e relatório descritivo | Convergida | 17/17 tasks | 2026-11-17 |
| 008-ingestao-wikipedia | Ingestão Wikipedia — textos municipais rastreáveis e organizados por seções | Convergida | 46/46 tasks | 2026-11-20 |
| 009-mobilidade-distancias | Mobilidade — distâncias e tempos de viagem dos municípios até polos fixos | Convergida | 46/46 tasks | 2026-11-22 |
| 010-visibilidade-modelo-dados | Visibilidade do modelo de dados — dicionário, diagrama ER, catálogo DuckDB único e dbt docs | Convergida | 42/42 tasks | 2026-11-24 |

## Melhorias Ad-hoc

| Data | Área | Resumo |
| --- | --- | --- |
| 2026-11-12 | Ingestão Pordata (catálogo) | Dataset Pordata 845 (pessoal ao serviço nas empresas por ramo de atividade) adicionado a `config/sources.yml` como `pessoal_ao_servico_empresas`. A URL `Modelo_20/845.csv` foi achada testando os `Modelo_N` do blob; 200 e 15.775.480 bytes. As 158.212 linhas são idênticas às do legado (a única diferença é que a escala "pessoas" agora vem preenchida). Considerada e descartada a busca de fonte alternativa no INE, porque o Pordata já cobre 308 municípios de 2008 a 2023. Sem mudança de código: o validador e o transform leem as colunas pelo rótulo, e a ordem delas mudou (`Símbolo` antes de `Escala`). Contagens atualizadas em 6 arquivos de teste (16→17 CSV e derivadas) e na documentação. Validado com `ruff check` limpo, suíte completa 227/228 antes do último ajuste de contagem (`test_build_observations`, corrigido e reexecutado), coleta real (16 `unchanged`, 845 `changed`) e `build_observations` com 308/308 municípios no 845 e sem órfãos. |

## Bugs

| Slug | Título | Fase Atual | Veredito/Status | Próximo Passo | Última Atualização |
| --- | --- | --- | --- | --- | --- |
