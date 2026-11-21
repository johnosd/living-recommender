"""Relatório agregado local; não é um indicador publicado ou estimativa nacional."""

import json
from pathlib import Path

import pandas as pd


def _stats(frame):
    conflicts = frame.conflict_fields.fillna("").str.split("|").apply(lambda fields: "asking_rent_eur" in fields)
    prices = frame.loc[~conflicts, "asking_rent_eur"].dropna()
    prices = prices[prices > 0]
    n = len(prices)
    quantiles = prices.quantile([0.25, 0.5, 0.75], interpolation="linear") if n >= 10 else [None] * 3
    return {"n_listings": len(frame), "n_eligible": n, "n_price_conflicts": int(conflicts.sum()),
            "p25_eur": None if n < 10 else float(quantiles.loc[0.25]),
            "median_eur": None if n < 10 else float(quantiles.loc[0.5]),
            "p75_eur": None if n < 10 else float(quantiles.loc[0.75]),
            "status": "amostra suficiente" if n >= 10 else "amostra insuficiente"}


def _money(value):
    return "—" if value is None or pd.isna(value) else f"€ {value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _table(rows, *, typology=False):
    lines = ["| Território / grupo | Anúncios | n elegível | P25 | Mediana | P75 | Situação |",
             "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for row in rows:
        name = str(row["typology"] if typology else row["name"]).replace("|", " ").replace("\n", " ")
        lines.append(f"| {name} | {row['n_listings']} | {row['n_eligible']} | {_money(row['p25_eur'])} | "
                     f"{_money(row['median_eur'])} | {_money(row['p75_eur'])} | {row['status']} |")
    return lines


def write_report(listings, municipalities, summary, output_dir):
    """Grava somente agregados, sem IDs de imóveis, URLs, endereços ou anunciantes."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    provenance = {key: summary[key] for key in ("snapshot_month", "source_run_id", "snapshot_sha256",
                                               "license_id", "attribution")}
    municipal, by_type = [], []
    for municipality in municipalities.sort_values("dico").itertuples(index=False):
        selected = listings[listings.dico.eq(municipality.dico).fillna(False)]
        base = {"dico": municipality.dico, "name": municipality.official_name}
        municipal.append({**base, **_stats(selected), **provenance})
        for typology, group in selected.groupby("typology", dropna=False):
            by_type.append({**base, "typology": "não informada" if pd.isna(typology) else typology,
                            **_stats(group), **provenance})
    municipality_stats = pd.DataFrame(municipal)
    type_columns = ["dico", "name", "typology", *list(_stats(listings)), *provenance]
    pd.DataFrame(by_type, columns=type_columns).to_csv(output_dir / "municipality_typology_stats.csv",
                                                     sep=";", index=False, encoding="utf-8-sig")
    municipality_stats.to_csv(output_dir / "municipality_stats.csv", sep=";", index=False, encoding="utf-8-sig")
    typologies = [{"typology": "não informada" if pd.isna(typology) else typology, **_stats(group)}
                  for typology, group in listings.groupby("typology", dropna=False)]
    regional = []
    if "locality_level" in listings.columns:
        for (region, locality), group in listings[listings.locality_level.eq("regiao")].groupby(
                ["source_region", "locality_raw"], dropna=False):
            regional.append({"name": locality, "source_region": None if pd.isna(region) else region,
                             **_stats(group), **provenance})
    regional_columns = ["name", "source_region", *list(_stats(listings)), *provenance]
    pd.DataFrame(regional, columns=regional_columns).to_csv(output_dir / "regional_stats.csv",
                                                           sep=";", index=False, encoding="utf-8-sig")
    sampled = sum(row["n_listings"] > 0 for row in municipal)
    sufficient = sum(row["n_eligible"] >= 10 for row in municipal)
    statistics = {**provenance, "lot": _stats(listings), "municipalities_expected": len(municipal),
                  "municipalities_with_listings": sampled, "municipalities_with_sufficient_sample": sufficient,
                  "municipality_stats": municipal, "municipality_typology_stats": by_type,
                  "typologies": typologies, "regional_groups": regional}
    (output_dir / "statistics.json").write_text(json.dumps(statistics, ensure_ascii=False, indent=2,
                                                          allow_nan=False) + "\n", encoding="utf-8")
    lines = [f"# Relatório Idealista — {summary['snapshot_month']}", "",
             f"{summary['attribution']}. Licença: `{summary['license_id']}`; uso restrito, sem publicação de anúncios.",
             f"Run: `{summary['source_run_id']}`. SHA-256 do snapshot: `{summary['snapshot_sha256']}`.",
             f"Importado em: {summary.get('imported_at_utc', 'não informado')}. Horário original da coleta: desconhecido.", "",
             "## Volume e qualidade", "", "| Medida | Valor |", "| --- | ---: |"]
    labels = {"files": "Arquivos JSON", "raw_bytes": "Bytes originais", "records": "Ocorrências",
              "unique_listings": "Anúncios únicos", "duplicate_occurrences": "Ocorrências excedentes",
              "conflicting_listings": "IDs com campos divergentes", "territorial_conflicts": "Conflitos de município",
              "regional_listings": "Anúncios mantidos no nível regional", "listings_with_parish": "Freguesia resolvida",
              "municipal_listings_without_parish": "Municipais sem freguesia",
              "missing_or_invalid_price": "Preço ausente ou inválido",
              "missing_or_invalid_area": "Área ausente ou inválida",
              "missing_or_invalid_typology": "Tipologia ausente ou inválida"}
    for key, label in labels.items():
        if key in summary:
            lines.append(f"| {label} | {summary[key]} |")
    lines += ["", "## Cobertura e interpretação territorial", "",
              f"{sampled}/{len(municipal)} municípios têm anúncios atribuídos; {sufficient} têm pelo menos 10 preços elegíveis.",
              ("No formato novo, Município vazio mantém o anúncio regional: distrito/ilha homônimo não vira município. "
              "Freguesia explícita é resolvida apenas dentro de um município comprovado por CAOP/seed. "
              "No legado, mantém-se a interpretação do arquivo e do título. A hierarquia é contexto da captura, não endereço verificado."),
              "Ausência de amostra municipal não significa ausência de oferta: anúncios regionais não são distribuídos por palpite.",
              ("As diferenças de escrita entre freguesias do exportador e CAOP só são aceitas por sinônimos explícitos "
               "em idealista_metadata_parish_synonyms.csv. Nomes genéricos ou não resolvidos continuam sem DICOFRE."),
              ("O catálogo de links e o número de páginas no arquivo não comprovam esgotamento da oferta ou coleta completa. "
              "Arquivos com 60 páginas podem ter truncamento; não há evidência suficiente para certificar completude."), "",
              "## Preços pedidos no lote", "",
              ("Valores em EUR/mês de anúncios únicos, não rendas de contratos celebrados. Preço ausente/inválido ou "
              "com conflito entre duplicatas é excluído. Mediana e quartis usam interpolação linear, somente com n elegível ≥ 10. "
              "Nenhum outlier é removido automaticamente. Não há controle aqui de sazonalidade, duração do contrato ou composição dos imóveis."),
              "O resumo do lote mistura territórios e tipologias; não representa a renda mediana de Portugal.", "",
              *_table([{"name": "Lote inteiro (inclui regionais)", **statistics["lot"]}]), "",
              "### Por tipologia (lote inteiro)", "", *_table(typologies, typology=True), "",
              "### Municípios com amostra", "",
              ("Todos os municípios, inclusive sem amostra, constam em municipality_stats.csv e statistics.json. "
              "O recorte município/tipologia também está em municipality_typology_stats.csv e statistics.json."), "",
              *_table(sorted((row for row in municipal if row["n_listings"]),
                             key=lambda row: (-row["n_listings"], row["name"]))), "",
              "### Por município e tipologia", "",
              "Grupos observados, com n total e elegível; anúncios regionais não entram neste recorte.", "",
              *_table([{**row, "name": f"{row['name']} ({row['dico']}) / {row['typology']}"}
                       for row in by_type]), "",
              "### Grupos regionais sem município comprovado", "",
              "Estes anúncios não entram nas tabelas municipais. O recorte está em regional_stats.csv.", "",
              *_table(sorted(regional, key=lambda row: (-row["n_listings"], row["name"]))), "",
              "## Limitações e reprodução", "",
              ("O período é declarado pelo operador; o horário de coleta não é conhecido. Não inferir evolução de preços "
              "comparando diretamente com 2025-08: cobertura, granularidade e composição das amostras diferem. "
              "O método de coleta do app de origem não é certificado pela importação offline."),
              "Dados individuais ficam privados em .data. Este relatório é local e descritivo; não atualiza publicação ou ranking.",
              (f"Reproduzir após importar o mesmo manifest: `uv run --locked python -m pipelines.cli.build_idealista "
              f"--local --snapshot-month {summary['snapshot_month']}`."), ""]
    (output_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return statistics
