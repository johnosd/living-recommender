# Quickstart
1. `uv run --locked python -m pipelines.cli.import_idealista_snapshot --local --directory "J:/IdealistaScraper/.data/municipios/202611" --snapshot-month 2026-11`
2. Repetir: esperar unchanged e nenhum raw novo.
3. `uv run --locked python -m pipelines.cli.build_idealista --local --snapshot-month 2026-11`
4. Ler `.data/lake/bronze/idealista_reports/report.md`, CSV e JSON. Conferir dbt_run_results.json, hashes e totais. Dados sem município não são cobertura municipal. Publicação não faz parte desta execução.
5. No JSON, comparar `municipality_stats` e `municipality_typology_stats` com os CSV de mesmo nome. No Markdown, conferir a seção `Por município e tipologia`: n total/elegível e quartis devem coincidir, com supressão quando n elegível <10. No lote 2026-11 há 308 registros municipais e 225 grupos município/tipologia.
