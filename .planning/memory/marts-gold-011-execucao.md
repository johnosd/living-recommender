# Marts Gold 011 — achados da execução (2026-11-24)

Feature: `.sdd/specs/011-marts-indicadores-catalogo/`. Complementa `marts-gold-011-planejamento.md`.

## dbt

- **Uma fonte dbt só pode ser declarada uma vez no projeto.** `caop_silver` vive em `models/bronze/schema.yml`
  (lida por `OBS_SILVER_DIR`); a Gold, como a mobilidade, reusa essa fonte e o build passa
  `OBS_SILVER_DIR=<root>/lake/silver`. Redeclarar a fonte com outra variável de ambiente quebra o parse.
- **Escalar YAML com `": "` sem aspas quebra o parse**, tanto no `config/criteria.yml` quanto no `schema.yml` do
  dbt (ex.: "Tempos de viagem: Google" numa descrição). Use `>-` ou aspas.
- O `modeldocs` reconhece a camada `gold` pelo caminho `/lake/gold/` do `location` do modelo. A camada só aparece
  no resumo do `.docs/modelo_de_dados.md` quando há tabela nela, o que manteve estável o contrato da 010.

## Dados (lake real, catálogo `d738fdca5257`)

- O build lê 8 entradas e gera 8 tabelas Gold: 19 712 linhas municipais (64 critério × variante × 308) e 208 576 de
  freguesia (× 3 259). O `prepare` leva cerca de 16 s; a parte pesada é o pivot do clima diário.
- **Aluguel próprio** (ALL, n ≥ 10 sem outliers): 42 municípios e 135 freguesias. 26 municípios das ilhas ficam
  `regional_only`, e 228 ficam `sem_anuncios`.
- **Cobertura por critério:** `emprego_desemprego_100` tem 278/308 (30 com `x`), e `custo_renda_ine_m2` tem 255/308
  (os 53 restantes têm `-` numa taxa, que fica ausente). `educacao_ensino_superior` tem 245 zeros por convenção da
  fonte.
- **Censos por freguesia:** não há coluna `source_id`, e o `dataset_id` muda por lote (`pop_2025_batch_NNN`). Na
  Gold usa-se `source_id = censos` e `dataset_id = census_parish_observation`. Em 2026-11 todas as 3 259 freguesias
  vêm com `coverage_status = own`.
- **TCI legado:** a precipitação usa `<=` nos limites e o vento usa `<` estrito (`W = 15` vale 7, não 10). As faixas
  de temperatura são fechadas nos dois lados de 20–27.

Depois da convergência (fase 7), o catálogo ganhou `clima_temp_max_anual` e `clima_temp_min_anual` e passou para
`160da2ce8218`: 62 critérios (61 disponíveis), 20 328 linhas municipais e 215 094 de freguesia.

## Verificação da versão do catálogo

O mesmo YAML com os mesmos dados repete a `catalog_version`. Ao trocar dois pesos da mesma categoria, a versão
mudou (`01dc08866ff8`); ao desfazer, voltou a `d738fdca5257` (quickstart §4, 2026-11-24).
