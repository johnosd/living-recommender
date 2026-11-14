# Quickstart

Requer uv sync --locked e dimensões CAOP construídas na raiz local escolhida.

```powershell
uv run --locked python -m pipelines.cli.import_idealista_snapshot --local --directory "C:/Users/johns/Documents/Projetos/IdealistaScraper/Bases/202508" --snapshot-month 2025-08
uv run --locked python -m pipelines.cli.build_idealista --local --snapshot-month 2025-08
```

Repetir a importação deve retornar unchanged, sem novos brutos. Verificar hashes,
summary.json, coverage.csv e duplicates.csv em .data/lake/bronze/idealista_reports.
O período é agosto/2025, independentemente da data de importação. Não representa
preços atuais. Não publicar nem versionar anúncios individuais.
