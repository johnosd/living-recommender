# Backlog

Painel único de ideias futuras e status de features/bugs geridas pelo
sistema sdd-*. Mantido automaticamente por update-feature-status.ps1 e
update-bug-status.ps1.

## Ideias Futuras

- **2026-11-17 — Enriquecimento geográfico posterior dos anúncios Idealista:** recuperar município/freguesia combinando nomes e contexto territorial com a CAOP; geocodificar endereços parciais dos títulos quando necessário, preservando proveniência e precisão. A exploração encontrou 2.792 candidatos municipais únicos entre 6.371 anúncios regionais, ainda sem validação ou promoção ao lake. Próximo passo: definir um piloto de 100 anúncios para medir acurácia, ganho de cobertura e custo; escolher provedor e verificar licença/persistência (OpenCage como candidato; Google condicionado ao enquadramento contratual; não depender do Nominatim público para lotes recorrentes). Provedor, orçamento e implementação permanecem pendentes de decisão. [Avaliação e diagnóstico](../.sdd/assessments/enriquecimento-geogrfico-posterior-dos-anncios-idealista/explora.md).

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
| 008-ingestao-wikipedia | Ingestão Wikipedia — textos municipais rastreáveis e organizados por seções | Em Execução | 41/43 tasks | 2026-11-20 |

## Melhorias Ad-hoc

| Data | Área | Resumo |
| --- | --- | --- |
| 2026-11-12 | Ingestão Pordata (catálogo) | Dataset Pordata 845 (pessoal ao serviço nas empresas por ramo de atividade) adicionado a `config/sources.yml` como `pessoal_ao_servico_empresas`. A URL `Modelo_20/845.csv` foi achada testando os `Modelo_N` do blob; 200 e 15.775.480 bytes. As 158.212 linhas são idênticas às do legado (a única diferença é que a escala "pessoas" agora vem preenchida). Considerada e descartada a busca de fonte alternativa no INE, porque o Pordata já cobre 308 municípios de 2008 a 2023. Sem mudança de código: o validador e o transform leem as colunas pelo rótulo, e a ordem delas mudou (`Símbolo` antes de `Escala`). Contagens atualizadas em 6 arquivos de teste (16→17 CSV e derivadas) e na documentação. Validado com `ruff check` limpo, suíte completa 227/228 antes do último ajuste de contagem (`test_build_observations`, corrigido e reexecutado), coleta real (16 `unchanged`, 845 `changed`) e `build_observations` com 308/308 municípios no 845 e sem órfãos. |

## Bugs

| Slug | Título | Fase Atual | Veredito/Status | Próximo Passo | Última Atualização |
| --- | --- | --- | --- | --- | --- |
