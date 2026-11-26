# Research: spec 011

Medições feitas em 2026-11-24 sobre o lake real (`.data/lake`), com DuckDB.

## 1. Símbolo `-` em datasets de contagem

- **Decisão**: em datasets de contagem (`dash_is_zero: true` no catálogo), valor nulo com símbolo `-` vira
  0, com `value_status = zero_convencao_fonte` e o símbolo preservado. Nas taxas, índices e médias, continua
  ausente. É decisão do autor, de 2026-11-24 (R-001).
- **Justificativa**: o INE define `-` como "dado nulo ou não aplicável". No lake, `-` aparece onde a contagem
  é zero: `ensino_superior` tem 63 municípios com valor e 245 com `-` em 2025, e há
  `crimes_por_categoria` (7 556 linhas) e `ensino_nao_superior` (66 366 linhas) com `-`. Sem a regra,
  "ensino superior no município" não distingue "não há" de "sem dado".
- **Alternativas**: sempre ausente (cobertura artificialmente baixa); zero em tudo (arriscado em médias).

## 2. Sede de distrito

- **Decisão**: `distancia_sede_distrito_km` entra como `fonte_pendente`.
- **Justificativa**: `config/poles.yml` só tem `lisboa`, `porto` e 5 aeroportos; não existe polo
  `sede_distrito`. Criar esses polos exige recoleta (spec 009), o que está fora do escopo.
- **Alternativas**: calcular a linha reta aqui a partir da CAOP, o que duplicaria a lógica da spec 009 fora
  do coletor.

## 3. Onde fica a lógica: Python (pandas) + dbt para tipos e testes

- **Decisão**: os cálculos ficam em `pipelines/gold/*.py`, com funções puras sobre DataFrames. O dbt (tag
  `gold`) lê o parquet preparado, fixa os tipos e roda os testes, como nas specs 005–009.
- **Justificativa**: os golden tests do TCI e do IQR (FR-018) ficam diretos e rápidos em pytest. O
  repositório já prepara em Python e tipa/testa em dbt (`idealista_listings`, mobilidade). O volume é
  pequeno: o clima diário tem 2,25 M linhas nas 10 variáveis usadas, e o resto tem menos de 300 mil.
- **Alternativas**: tudo em SQL dbt, com testes só por build completo, que é lento e deixa as faixas do TCI
  difíceis de isolar; macros dbt testadas por pytest, que duplicaria o motor.

## 4. Percentis

- **Decisão**: interpolação linear (`numpy.percentile` padrão), em IQR, mediana, P25/P75 e P5/P95.
- **Justificativa**: é o mesmo método do relatório da spec 007 ("interpolação linear") e do
  `quantile_cont` do DuckDB.

## 5. Faixas das opções categóricas (provisórias, R-003)

- Temperatura média anual (janela 2024-11 a 2026-10, 308 municípios): mín 11,5; P25 14,7; mediana 16,4;
  P75 17,4; máx 19,6 °C. Opções: fresco < 14,5; ameno 14,5–17; quente ≥ 17.
- Residentes em 2024: 186 municípios < 20 mil, 96 entre 20 e 100 mil e 26 ≥ 100 mil. Opções: vila,
  cidade média e grande centro.

## 6. Achados de cobertura que o mart de qualidade vai mostrar

- `desemprego_registado`: 278/308 com valor (30 com `x`).
- `rendas_novos_contratos` (INE): 247 municípios em 2025, 255 em algum ano (fallback de período).
- `ensino_superior`: 77 municípios já tiveram valor; 63 em 2025.
- Idealista 2026-11: 42 municípios com n ≥ 10; 123 grupos município × tipologia com n ≥ 10; 136 freguesias
  com n ≥ 10. Preço de €250 a €30 000 e área de 10 a 640 000 m² (daí o filtro 10–1 000 m² no €/m²).
- Neve: 124 dias com `snowfall_sum` entre 0 e 0,1 cm (ruído do ERA5) contam como dia de neve pela regra
  legada `> 0` (R-004).
- Mobilidade: 2 156 pares de linha reta e 1 406 de carro, todos `ok`, nenhum `stale`. As ilhas não têm
  carro até Lisboa nem até o Porto.
