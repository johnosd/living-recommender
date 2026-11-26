# Quickstart: verificar a spec 012

## 1. Pré-requisitos

- Lake local com as 8 entradas do build Gold (specs 001–009).
- Nenhuma chave, nenhuma rede.

**Antes de rodar o build novo**, guarde a normalização atual, para conferir a SC-004:

```powershell
Copy-Item .data/lake/gold/gold_criteria_normalization/data.parquet .data/normalizacao_antes_012.parquet
```

## 2. Checagens automatizadas

```powershell
uv run --locked ruff check pipelines tests
uv run --locked python -m pytest -q --basetemp .pytest_tmp        # leva ~12 min
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 012-aluguel-distrito-regiao
.\.planning\scripts\powershell\check-contract-tests.ps1 -Slug 011-marts-indicadores-catalogo
uv run --locked python -m tests.fixtures.gold.ci_seed --root .data/ci-gold   # a pasta precisa estar vazia
uv run --locked python -m pipelines.cli.build_gold --local --root .data/ci-gold --criteria .data/ci-gold/criteria.yml
uv run --locked python -m pipelines.cli.model_docs --check
```

## 3. Build real

```powershell
uv run --locked python -m pipelines.cli.build_gold --local --root .data
```

Cole o script em um arquivo temporário e rode com `uv run --locked python <arquivo>`. Os números esperados valem
para o snapshot `2026-11` (`research.md`).

```python
import duckdb

con = duckdb.connect()
for name in ("gold_municipality_indicator", "gold_parish_indicator", "gold_rent_by_district_typology",
             "gold_rent_by_region_typology", "gold_rent_by_municipality_typology", "gold_criteria_normalization",
             "gold_data_quality"):
    con.sql(f"create view {name} as select * from read_parquet('.data/lake/gold/{name}/data.parquet')")

# SC-001: 150 linhas / 25 distritos; 42 linhas / 7 regiões; nenhuma mediana com n < 10
for table, key in (("gold_rent_by_district_typology", "district_or_island"),
                   ("gold_rent_by_region_typology", "source_region")):
    print(con.sql(f"select count(*), count(distinct {key}), "
                  f"count(*) filter (where n_eligible < 10 and rent_median is not null) from {table}").fetchall())

# SC-002: ALL = proprio/municipio 42, herdado/distrito 254, herdado/regiao 12, ausente 0
print(con.sql("""select criterion_id, variant, origin, origin_level, count(*) from gold_municipality_indicator
    where criterion_id like 'custo_aluguel%' group by all order by all""").df().to_string())

# SC-003: 0 divergências
print(con.sql("""
with i as (select * from gold_municipality_indicator
           where origin_level in ('distrito','regiao') and criterion_id = 'custo_aluguel_mediana'),
m as (select distinct dico, district_or_island, source_region from gold_rent_by_municipality_typology)
select count(*) filter (where i.value is distinct from
         case i.origin_level when 'distrito' then d.rent_median else r.rent_median end) as divergentes,
       count(*) as herdados
from i join m using (dico)
left join gold_rent_by_district_typology d
  on d.district_or_island = m.district_or_island and d.typology = i.variant
left join gold_rent_by_region_typology r on r.source_region = m.source_region and r.typology = i.variant
""").fetchall())

# Freguesia ALL: freguesia 135, municipio 284, distrito 2777, regiao 63
print(con.sql("""select origin, origin_level, count(*) from gold_parish_indicator
    where criterion_id = 'custo_aluguel_mediana' and variant = 'ALL' group by all order by all""").fetchall())

# FR-014: with_value + missing = esperados; inherited = soma dos três níveis (0 linhas)
print(con.sql("""select * from gold_data_quality
    where with_value + missing <> territories_expected
       or inherited <> inherited_municipio + inherited_distrito + inherited_regiao""").fetchall())

# SC-004: 0 diferenças contra a normalização guardada no passo 1
print(con.sql("""
with antes as (select criterion_id, level, variant, n, min, p5, p95, max
               from read_parquet('.data/normalizacao_antes_012.parquet') where criterion_id like 'custo_aluguel%'),
depois as (select criterion_id, level, variant, n, min, p5, p95, max
           from gold_criteria_normalization where criterion_id like 'custo_aluguel%')
(select * from antes except select * from depois) union all (select * from depois except select * from antes)
""").fetchall())

# Amostra: Braga herda o distrito (T2 1000, T3 1150)
print(con.sql("""select variant, value, origin, origin_level from gold_municipality_indicator i
    join read_parquet('.data/lake/silver/dim_municipality/data.parquet') m using (dico)
    where m.official_name = 'Braga' and criterion_id = 'custo_aluguel_mediana' order by variant""").fetchall())
```

SC-005 (distrito e região usam a mesma regra do município) é coberta pelo teste unitário da T010.

## 4. Checagens manuais

- Abrir `analytics/notebooks/explorar_gold.ipynb`, rodar tudo e conferir que o aluguel de distrito e região vem da
  Gold. **Limpar as saídas antes de commitar.**
- Verificar sem abrir a interface:
  `uv run --locked --group notebook jupyter nbconvert --to notebook --execute analytics/notebooks/explorar_gold.ipynb --output-dir <pasta temporária>`.
- Conferir no `.docs/modelo_de_dados.md` que as duas tabelas novas aparecem com todas as colunas descritas.

## 5. Gates da constitution

| Princípio | Como verificar |
| --- | --- |
| III | Nenhuma mediana com n < 10; todo herdado tem `origin_level`; proveniência preenchida |
| IV e VI | Nenhuma tabela Gold tem `listing_id`; notebook sem saídas |
| V | Um teste dbt que falha preserva o `lake/gold/` anterior (teste de integração) |
| VII | Nenhum recurso com custo |
