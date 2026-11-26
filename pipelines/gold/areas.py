"""Aluguel por distrito (ou ilha) e por região da fonte, e a herança marcada no município (spec 012).

Regras: `.sdd/specs/012-aluguel-distrito-regiao/logic/heranca.md`. Como em `rent.py`, nenhuma linha por anúncio
sai deste módulo (constitution IV e VI).
"""
import pandas as pd

from pipelines.collectors.idealista.territory import read_seed
from pipelines.gold import rent
from pipelines.gold.common import ORIGIN_COLUMNS, available

# Nas ilhas, a fonte escreve o nome de outro jeito que o CAOP (`dim_municipality.district_or_island`). A
# correspondência é uma seed explícita (`logic/heranca.md` §2); um nome sem par falha o build.
ISLAND_SEED = "idealista_island_aliases.csv"
AREA_STATS_COLUMNS = tuple(column for column in rent.STATS_COLUMNS if column != "rent_coverage")


class AreaError(ValueError):
    """Área da fonte sem par no CAOP, ou distrito com mais de uma região; a mensagem nomeia a área."""


def _text(values: pd.Series) -> pd.Series:
    """Texto com vazio ou só espaços como nulo (o formato antigo grava `source_region = ""`)."""
    cleaned = [(value.strip() or None) if isinstance(value, str) else None for value in values]
    return pd.Series(cleaned, index=values.index, dtype=object)


def _autonomous_regions(municipalities: pd.DataFrame) -> dict:
    """Região da fonte dos distritos das regiões autónomas: a reserva quando a fonte não a informa."""
    if "autonomous_region" not in municipalities.columns:
        return {}
    pairs = zip(municipalities["district_or_island"], municipalities["autonomous_region"], strict=True)
    return {district: rent.REGIONS[region] for district, region in pairs if region in rent.REGIONS}


def _placed(listings: pd.DataFrame, municipalities: pd.DataFrame) -> pd.DataFrame:
    """Anúncios do snapshot vigente com `district_or_island` e `source_region` resolvidos (§2).

    A marca de outlier de `rent._current` é a do grupo municipal e é descartada: cada área calcula a sua.
    """
    current = rent._current(listings).drop(columns="outlier")
    districts = municipalities.set_index("dico")["district_or_island"]
    unknown = sorted(set(current["dico"].dropna()) - set(districts.index))
    if unknown:
        raise AreaError(f"anúncio com município fora da CAOP: {', '.join(map(str, unknown))}")
    aliases = {row["source_subregion"]: row["district_or_island"] for row in read_seed(ISLAND_SEED)}
    named = _text(current["source_subregion"]).map(lambda name: aliases.get(name, name))
    # Com município, o distrito é o da CAOP: o nome da fonte pode ser outro (`Horta`, na Ilha do Faial).
    district = current["dico"].map(districts).astype(object).where(current["dico"].notna(), named)
    unknown = sorted(set(district.dropna()) - set(districts))
    if unknown:
        raise AreaError(f"distrito da fonte sem par na CAOP: {', '.join(unknown)} (ilha nova: acrescente em "
                        f"analytics/dbt/seeds/{ISLAND_SEED})")
    region = _text(current["source_region"])
    region = region.where(region.notna(), district.map(_autonomous_regions(municipalities)))
    return current.assign(district_or_island=district, source_region=region)


def _district_regions(placed: pd.DataFrame, municipalities: pd.DataFrame) -> dict:
    """Região de cada distrito conhecido; mais de uma região no mesmo distrito falha (FR-005)."""
    autonomous = pd.DataFrame(list(_autonomous_regions(municipalities).items()),
                              columns=["district_or_island", "source_region"])
    pairs = pd.concat([placed[["district_or_island", "source_region"]], autonomous], ignore_index=True)
    pairs = pairs.dropna().drop_duplicates()
    ambiguous = pairs[pairs["district_or_island"].duplicated(keep=False)]
    if not ambiguous.empty:
        detail = "; ".join(f"{district}: {', '.join(sorted(group['source_region']))}"
                           for district, group in ambiguous.groupby("district_or_island"))
        raise AreaError(f"distrito com mais de uma região na fonte: {detail}")
    return dict(zip(pairs["district_or_island"], pairs["source_region"], strict=True))


def _area_rows(placed: pd.DataFrame, key: str) -> list[dict]:
    """6 linhas (tipologias) por área com anúncios, com os outliers marcados no grupo área × tipologia."""
    located = placed[placed[key].notna()].copy()
    located["outlier"] = rent._outliers(located, key)
    provenance = rent._provenance(placed)
    rows = []
    for area, group in located.groupby(key, sort=True):
        rows.extend({**row, **provenance} for row in rent._territory_rows(group, key, area))
    return rows


def territory_hierarchy(listings: pd.DataFrame, municipalities: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por município: `dico`, `district_or_island`, `source_region` (nula se desconhecida)."""
    regions = _district_regions(_placed(listings, municipalities), municipalities)
    frame = municipalities[["dico", "district_or_island"]].reset_index(drop=True)
    return frame.assign(source_region=frame["district_or_island"].map(regions))


def district_rent_stats(listings: pd.DataFrame, municipalities: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por distrito (ou ilha) com anúncios no snapshot vigente × tipologia (`ALL`, `T0`...`T4+`)."""
    placed = _placed(listings, municipalities)
    regions = _district_regions(placed, municipalities)
    rows = _area_rows(placed, "district_or_island")
    for row in rows:
        row["source_region"] = regions.get(row["district_or_island"])
    return rent._frame(rows, ["district_or_island", "source_region"], AREA_STATS_COLUMNS)


def region_rent_stats(listings: pd.DataFrame, municipalities: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por região da fonte com anúncios no snapshot vigente × tipologia."""
    placed = _placed(listings, municipalities)
    _district_regions(placed, municipalities)  # a mesma validação da hierarquia
    return rent._frame(_area_rows(placed, "source_region"), ["source_region"], AREA_STATS_COLUMNS)


def _area_reference(hierarchy: pd.DataFrame, district_stats: pd.DataFrame, region_stats: pd.DataFrame):
    """Função `(dico, tipologia, medida) -> (nível, linha de origem)` da área mais fina com valor (§5).

    A cadeia começa no distrito: o valor próprio do município é decidido por quem chama.
    """
    places = hierarchy.set_index("dico").to_dict("index")
    levels = []
    for level, key, table in (("distrito", "district_or_island", district_stats),
                              ("regiao", "source_region", region_stats)):
        levels.append((level, key, {(row[key], row["typology"]): row for row in table.to_dict("records")}))

    def resolve(dico: str, typology: str, column: str) -> tuple[str | None, dict | None]:
        place = places.get(dico, {})
        for level, key, rows in levels:
            row = rows.get((place.get(key), typology))
            if row is not None and pd.notna(row[column]):
                return level, row
        return None, None

    return resolve


def reference_levels(stats: pd.DataFrame, hierarchy: pd.DataFrame, district_stats: pd.DataFrame,
                     region_stats: pd.DataFrame) -> pd.DataFrame:
    """A tabela municipal com `district_or_island`, `source_region`, `reference_level` e `reference_level_eur_m2`.

    `rent_coverage`, as contagens e as medidas continuam falando só do próprio município (FR-010).
    """
    resolve = _area_reference(hierarchy, district_stats, region_stats)
    places = hierarchy.set_index("dico")
    result = stats.reset_index(drop=True).copy()
    for column in ("district_or_island", "source_region"):
        result[column] = result["dico"].map(places[column])
    for target, measure in (("reference_level", "rent_median"), ("reference_level_eur_m2", "eur_m2_median")):
        keys = zip(result["dico"], result["typology"], result[measure], strict=True)
        result[target] = pd.Series(["municipio" if pd.notna(own) else resolve(dico, typology, measure)[0]
                                    for dico, typology, own in keys], index=result.index, dtype=object)
    return result


def apply_rent_inheritance(indicators: pd.DataFrame, hierarchy: pd.DataFrame, district_stats: pd.DataFrame,
                           region_stats: pd.DataFrame, criteria: dict) -> pd.DataFrame:
    """O perfil municipal com `origin` e `origin_level` em todas as linhas e o aluguel ausente herdado da área.

    O herdado é cópia exata da área (valor e proveniência) e sempre marcado: nada é imputado em silêncio
    (constitution III). Sem referência em nenhum nível, a linha fica como estava, com o motivo próprio.
    """
    resolve = _area_reference(hierarchy, district_stats, region_stats)
    measures = {item["id"]: rent.METRICS[item["compute"]["metric"]][0] for item in available(criteria, "rent")}
    rows = indicators.to_dict("records")
    for row in rows:
        own = pd.notna(row["value"])
        row.update(origin="proprio" if own else "ausente", origin_level="municipio" if own else None)
        measure = measures.get(row["criterion_id"])
        if own or measure is None:
            continue
        level, source = resolve(row["dico"], row["variant"], measure)  # cada variante decide sozinha (FR-009)
        if level is None:
            continue
        # `usage_restriction` fica a da linha: é a da fonte, já preenchida por `rent_indicators`.
        row.update(value=float(source[measure]), origin="herdado", origin_level=level, value_status="observado",
                   missing_reason=None, period=source["snapshot_month"],
                   dataset_latest_period=source["snapshot_month"], source_id=source["source_id"],
                   dataset_id=rent.DATASET_ID, license_id=source["license_id"], attribution=source["attribution"],
                   is_older_period=False, is_stale=False)
    added = [column for column in ORIGIN_COLUMNS if column not in indicators.columns]
    result = pd.DataFrame(rows, columns=[*indicators.columns, *added])
    result["value"] = pd.to_numeric(result["value"], errors="coerce").astype("float64")
    return result
