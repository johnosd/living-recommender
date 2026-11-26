# DuckDB 2.0 no projeto e notebook de exploração (2026-11-24)

- **O DuckDB instalado é o 2.0.0 (Python).** Uma relação (`duckdb.sql(...)` ou `con.sql(...)`) não tem mais
  `fetchone()`: a chamada dá `AttributeError`, porque a relação não guarda resultado e roda de novo a cada chamada.
  Use `.fetchall()[0][0]`, `.df()` ou `.show()`. Evidência: erro reproduzido ao contar linhas da Gold.
- **Notebook de exploração:** `analytics/notebooks/explorar_gold.ipynb` registra como views as tabelas Gold e,
  do Silver, só `dim_municipality` e `dim_parish`. Os anúncios do Idealista (`idealista_listings`) não viram view,
  para não exibir dados individuais. Pela constitution, só agregados são publicados.
- **Aluguel por distrito e região:** o protótipo que vivia no notebook (view `aluguel_regional`) virou a spec 012.
  Desde 2026-11-26 o notebook lê `gold_rent_by_district_typology`, `gold_rent_by_region_typology` e `origin_level`
  nos perfis; não calcula nada a partir dos anúncios.
- **Dependências do notebook:** ficam no grupo opcional `notebook` do `pyproject.toml` (jupyterlab, ipykernel,
  matplotlib), fora do pipeline. Para verificar sem abrir a interface, rode
  `uv run --locked --group notebook jupyter nbconvert --to notebook --execute <nb> --output-dir <tmp>`.
- **Saídas:** o arquivo versionado fica sem saídas. Limpe antes de commitar, porque as tabelas exibidas são dados
  do lake.
