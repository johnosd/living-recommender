# Marts Gold 011 — achados do planejamento (2026-11-24)

Feature: `.sdd/specs/011-marts-indicadores-catalogo/`. Medições com DuckDB sobre `.data/lake`, em 2026-11-24.

## Achados duráveis sobre os dados

- **Símbolo `-` do Pordata/INE.** O INE o define como "dado nulo ou não aplicável". No lake, ele aparece com
  `value` nulo onde a contagem é zero: `ensino_superior` tem 245 municípios com `-` em 2025, e também há
  `crimes_por_categoria` e `ensino_nao_superior`. Decisão do autor: `-` vira 0 só em datasets de contagem
  (`dash_is_zero`), com marca própria. O normalizador Python nunca converte em zero (`pordata/transform.py`);
  a regra fica na Gold.
- **Rótulos do Pordata com NBSP**, como `"A. \xa0Agricultura…"` em `pessoal_ao_servico_empresas`. Um filtro
  por rótulo precisa normalizar os espaços.
- **Valores com símbolo e não nulos** existem (`r` retificado, `Pro` provisório, `Quebra de série`). São
  valores válidos; o símbolo é só informativo.
- **Idealista:** a freguesia resolvida aparece com `locality_level = municipio` e `dicofre` preenchido
  (10 748 anúncios); só 3 têm `locality_level = freguesia`. Para filtrar por freguesia, use `dicofre is not
  null`, nunca o `locality_level`.
- **Mobilidade:** `config/poles.yml` não tem polo `sede_distrito` (só Lisboa, Porto e 5 aeroportos), embora
  o coletor da 009 suporte o tipo. A linha reta existe para todos os 308 × 7 pares; as ilhas não têm carro
  até Lisboa/Porto.
- **Poder de compra** existe por duas vias: INE `poder_compra_per_capita` (2023, 308) e Pordata
  `poder_compra_per_capita_xlsx` (até 2021).
- **Clima:** a janela é de 24 meses (2024-11-01 a 2026-10-31), sem nulos nas 13 variáveis. A média anual
  varia de 11,5 a 19,6 °C (P25 14,7; P75 17,4). 124 dias têm `snowfall_sum` entre 0 e 0,1 cm.

## Padrão adotado

A lógica Gold fica em funções puras (`pipelines/gold/`, pandas) e o dbt só tipa e testa, como no Idealista e
na mobilidade. Isso permite golden tests rápidos (TCI, IQR) sem rodar o dbt.
