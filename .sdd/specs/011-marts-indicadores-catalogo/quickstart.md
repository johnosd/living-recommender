# Quickstart: verificação da spec 011

## Pré-requisitos

- `uv sync` feito; o lake local em `.data/lake` tem as tabelas das specs 001–009 (`bronze/` e `silver/`).
- Nenhuma chave, rede ou recurso AWS é necessário. O build só lê o lake e escreve em `lake/gold/`.

## 1. Checagens automatizadas

```powershell
uv run ruff check pipelines tests
uv run python -m pytest tests/contracts/test_gold_indicators_contract.py -q --basetemp .pytest_tmp   # 5/5
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 011-marts-indicadores-catalogo
uv run python -m pytest -q --basetemp .pytest_tmp                                                    # suíte completa
uv run python -m tests.fixtures.gold.ci_seed --root .data/ci-gold
uv run python -m pipelines.cli.build_gold --local --root .data/ci-gold --criteria .data/ci-gold/criteria.yml
uv run python -m pipelines.cli.model_docs --check
```

## 2. Build real

```powershell
uv run python -m pipelines.cli.build_gold --local --root .data
```

Saída esperada: número de critérios disponíveis e pendentes, `catalog_version`, cobertura por categoria e o
caminho de `lake/gold/`. O critério `distancia_sede_distrito_km` aparece como pendente.

## 3. Conferências no lake (DuckDB)

```sql
-- SC-002: 308 municípios por critério disponível, e toda ausência tem motivo
select criterion_id, variant, count(*) n, count(*) filter (where value is null and missing_reason is null) sem_motivo
from '.data/lake/gold/gold_municipality_indicator/data.parquet' group by all having n <> 308 or sem_motivo > 0;
-- (esperado: zero linhas)

-- SC-006: nenhuma mediana com n < 10
select count(*) from '.data/lake/gold/gold_rent_by_municipality_typology/data.parquet'
where rent_median is not null and n_eligible < 10;                                      -- 0

-- FR-008: carro sempre com a atribuição do Google
select distinct attribution, license_id from '.data/lake/gold/gold_municipality_indicator/data.parquet'
where criterion_id like 'distancia_%_carro_%';                                           -- "Tempos de viagem: Google"

-- SC-007: herdado = município
select count(*) from '.data/lake/gold/gold_parish_indicator/data.parquet' p
join '.data/lake/gold/gold_municipality_indicator/data.parquet' m using (dico, criterion_id, variant)
where p.origin = 'herdado' and p.value is distinct from m.value;                         -- 0

-- SC-008: o mart de qualidade lista todo o catálogo
select (select count(distinct criterion_id) from '.data/lake/gold/gold_criteria_catalog/data.parquet') =
       (select count(distinct criterion_id) from '.data/lake/gold/gold_data_quality/data.parquet');   -- true
```

## 4. Cenário ponta a ponta (manual)

1. Mude o `weight` de dois critérios da mesma categoria em `config/criteria.yml`, mantendo a soma em 1, e
   rode o build. A `catalog_version` muda. Desfaça e rode de novo: a versão original volta.
2. Mude um critério disponível para um `dataset_id` inexistente. O build falha com uma mensagem que cita o
   id do critério, e `lake/gold/` continua com a versão anterior (mesmos bytes).
3. Abra o catálogo do lake (`uv run python -m pipelines.cli.lake_catalog`) e confira o schema `gold` com as
   9 tabelas.
4. Confira um par conhecido: Lisboa (`1106`) tem `distancia_lisboa_carro_min = 0`, e um município dos Açores
   não tem `distancia_lisboa_carro_min` (motivo `sem_par_elegivel`).

## 5. Itens cross-cutting (constitution)

- Nenhum segredo: o build não lê `.env` nem chave (princípio I).
- Só agregados de anúncios no lake Gold; nenhuma linha por anúncio (princípios IV e VI).
- Todo indicador com fonte, período e licença (princípio III).
- Sem recurso com custo (princípio VII); a execução no S3 fica para a Fase 1.
