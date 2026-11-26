"""Fixture da camada Gold, sempre offline: um lake mínimo com as entradas das specs 001–009 e um catálogo pequeno.

Quatro municípios (um na Madeira), cinco freguesias e um critério de cada `kind` (observação, clima, mobilidade,
aluguel e Censos na freguesia), mais um critério `fonte_pendente`.
"""
import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

PORDATA = {"source_id": "pordata", "license_id": "not_granted_by_source", "attribution": "Fonte: PORDATA",
           "unit": "u", "source_run_id": "ci-gold"}
OPEN_METEO = {"source_id": "open_meteo", "license_id": "CC-BY-4.0", "attribution": "Dados meteorológicos: Open-Meteo.com",
              "usage_restriction": "plano gratuito: uso não comercial (risco aceito R-001)"}
CAOP = {"license_id": "CC-BY-4.0", "attribution": "Fonte: Direção-Geral do Território (DGT), CAOP2025",
        "usage_restriction": None}
GOOGLE = {"license_id": "not_granted_by_source", "attribution": "Tempos de viagem: Google",
          "usage_restriction": "termos da Google Maps Platform; guardar a matriz de tempos é risco aceito (ADR-002 D8)"}
IDEALISTA = {"source_id": "idealista", "snapshot_month": "2026-11", "license_id": "not_granted_by_source",
             "attribution": "Fonte: Idealista, extração manual; período informado pelo operador"}
CENSOS = {"license_id": "CC-BY-4.0", "attribution": "Fonte: INE, Recenseamento da população e habitação — Censos 2021",
          "period": "2021", "dataset_id": "pop_2025_batch_ci"}

MUNICIPALITIES = [("0101", "Águeda", None, 335.3), ("0102", "Albergaria-a-Velha", None, 155.4),
                  ("1106", "Lisboa", None, 100.1), ("3101", "Calheta", "Região Autónoma da Madeira", 110.3)]
PARISHES = [("010101", "0101", 20.0), ("010102", "0101", 15.0), ("010201", "0102", 30.0), ("110601", "1106", 2.0),
            ("310101", "3101", 12.0)]
AGES = ("25 - 29 anos", "30 - 34 anos", "35 - 39 anos")
CENSUS_AGES = ("25_29", "30_34", "35_39", "65_69", "70_74", "75_79", "80_84", "85_plus")


def _write(root: Path, layer: str, table: str, rows: list[dict]) -> None:
    path = root / "lake" / layer / table / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _observation(dataset_id, dico, period, value, symbol=None, filter_1="", filter_2=""):
    return {**PORDATA, "dataset_id": dataset_id, "dico": dico, "source_name": dico, "period": period,
            "filter_1": filter_1, "filter_2": filter_2, "filter_3": "", "value": value, "symbol": symbol}


def observations() -> list[dict]:
    rows = []
    population = {"0101": 20000.0, "0102": 25000.0, "1106": 545000.0, "3101": 11000.0}
    for dico, total in population.items():
        rows.append(_observation("populacao_residente_sexo_idade", dico, 2023, total - 100, filter_1="Total",
                                 filter_2="Total"))
        rows.append(_observation("populacao_residente_sexo_idade", dico, 2024, total, filter_1="Total",
                                 filter_2="Total"))
        rows += [_observation("populacao_residente_sexo_idade", dico, 2024, total * 0.06, filter_1="Total",
                              filter_2=age) for age in AGES]
    rows += [_observation("recintos_cinema", "0101", 2024, 2.0), _observation("recintos_cinema", "0102", 2024, None, "-"),
             _observation("recintos_cinema", "1106", 2024, 40.0), _observation("recintos_cinema", "3101", 2023, 1.0)]
    rows += [_observation("ganho_medio_mensal", "0101", 2023, 1100.0),
             _observation("ganho_medio_mensal", "0102", 2023, 1050.0, "r"),
             _observation("ganho_medio_mensal", "1106", 2023, 1800.0),
             _observation("ganho_medio_mensal", "3101", 2023, None, "x")]
    return rows


def climate() -> list[dict]:
    rows = []
    month = [date(2024, 11, 1) + timedelta(days=offset) for offset in range(30)]
    base = {"temperature_2m_mean": 15.0, "temperature_2m_max": 20.0, "temperature_2m_min": 10.0,
            "apparent_temperature_max": 19.0, "apparent_temperature_min": 8.0, "relative_humidity_2m_mean": 70.0,
            "precipitation_sum": 1.0, "snowfall_sum": 0.0, "sunshine_duration": 6 * 3600.0,
            "wind_speed_10m_mean": 12.0}
    for position, (dico, *_rest) in enumerate(MUNICIPALITIES):
        for when in month:
            values = {**base, "temperature_2m_mean": 13.0 + position, "temperature_2m_max": 18.0 + position}
            if dico == "0102" and when.day == 5:
                values["temperature_2m_max"] = 36.0  # um dia de calor extremo
            for variable, value in values.items():
                rows.append({**OPEN_METEO, "dico": dico, "variable": variable, "date": when, "value": value,
                             "unit": "u", "model": "era5", "window_start": month[0], "window_end": month[-1],
                             "source_run_id": "ci-gold"})
    return rows


def poles() -> list[dict]:
    return [{"pole_id": "lisboa", "name": "Lisboa", "kind": "cidade", "routing_group": "continente",
             "scope": "national", "dico": "1106", "latitude": 38.7, "longitude": -9.1},
            {"pole_id": "aeroporto_lis", "name": "Aeroporto de Lisboa", "kind": "aeroporto",
             "routing_group": "continente", "scope": "national", "dico": None, "latitude": 38.77, "longitude": -9.13},
            {"pole_id": "aeroporto_fnc", "name": "Aeroporto da Madeira", "kind": "aeroporto", "routing_group": "madeira",
             "scope": "island", "dico": None, "latitude": 32.69, "longitude": -16.77}]


def _pair(dico, pole_id, mode, km, minutes=None, status="ok", method=None):
    google = mode == "driving"
    provenance = GOOGLE if google else CAOP
    return {"source_id": "google_distances" if google else "caop", "dico": dico, "pole_id": pole_id, "mode": mode,
            "km": km, "minutes": minutes, "status": status,
            "method": method or ("google_routes_v2" if google else "haversine"), "stale": False,
            "reference_period": "2026-12" if google else "2025", **provenance}


def distances() -> list[dict]:
    straight = {"0101": (220.0, 225.0, 900.0), "0102": (240.0, 245.0, 920.0), "1106": (0.0, 7.0, 970.0),
                "3101": (960.0, 965.0, 25.0)}
    rows = []
    for dico, (lisbon, airport, funchal) in straight.items():
        rows += [_pair(dico, "lisboa", "straight_line", lisbon, method="identity" if lisbon == 0 else None),
                 _pair(dico, "aeroporto_lis", "straight_line", airport),
                 _pair(dico, "aeroporto_fnc", "straight_line", funchal)]
    rows += [_pair("0101", "lisboa", "driving", 250.0, 150.0), _pair("0101", "aeroporto_lis", "driving", 255.0, 155.0),
             _pair("0102", "lisboa", "driving", 270.0, 165.0), _pair("0102", "aeroporto_lis", "driving", None, None,
                                                                    status="falha"),
             _pair("1106", "lisboa", "driving", 0.0, 0.0, method="identity"),
             _pair("1106", "aeroporto_lis", "driving", 8.0, 12.0), _pair("3101", "aeroporto_fnc", "driving", 30.0, 35.0)]
    return rows


def listings() -> list[dict]:
    def listing(number, dico, dicofre, typology, rent, level="municipio", region="Centro"):
        return {**IDEALISTA, "listing_id": f"CI{number:03d}", "dico": dico, "dicofre": dicofre,
                "locality_level": level, "source_region": region, "typology": typology, "asking_rent_eur": rent,
                "area_m2": 60.0, "has_conflict": False}

    rows = [listing(i, "0101", "010101", "T2", 900.0 + 10 * i) for i in range(12)]
    rows.append(listing(12, "0101", "010101", "T2", 4000.0))  # outlier do grupo 0101 × T2
    rows += [listing(20 + i, "0102", "010201", "T1", 700.0 + 5 * i) for i in range(3)]
    rows += [listing(40 + i, None, None, "T2", 950.0, level="regiao", region="Madeira") for i in range(2)]
    return rows


def census() -> list[dict]:
    rows = []
    for position, (dicofre, dico, _area) in enumerate(PARISHES):
        total = 1000 * (position + 1)
        coverage = "inherited" if dicofre == "010102" else "own"
        values = {"T": total, **{code: total // 20 for code in CENSUS_AGES}}
        for code, value in values.items():
            rows.append({**CENSOS, "dicofre": dicofre, "dico": dico, "age_code": code, "is_total": code == "T",
                         "value": value, "value_status": "observed", "coverage_status": coverage,
                         "indicator": "0014632"})
    return rows


def criteria() -> dict:
    def item(criterion_id, category, compute, *, weight=1.0, levels=("municipio",), modes=("peso", "faixa"), **extra):
        return {"id": criterion_id, "category": category, "label_pt": criterion_id, "label_en": criterion_id,
                "unit": "u", "direction": "maior_melhor", "levels": list(levels), "modes": list(modes),
                "default_range": [None, None], "weight": weight, "status": "disponivel", "pending_reason": None,
                "methodology_pt": "fixture", "options": None, "compute": compute, **extra}

    rent = {"kind": "rent", "metric": "median", "variants": ["ALL", "T2"]}
    return {"schema_version": 1,
            "categories": [{"id": name, "label_pt": name, "label_en": name}
                           for name in ("custo", "clima", "cultura", "emprego", "populacao", "distancia")],
            "criteria": [
                item("custo_aluguel_mediana", "custo", rent, levels=("municipio", "freguesia"), compute_parish=rent),
                item("clima_tci_anual", "clima", {"kind": "climate", "metric": "tci_anual"}),
                item("clima_dias_extremos_pct", "clima", {"kind": "climate", "metric": "dias_extremos_pct"},
                     weight=0.0, modes=("faixa",)),
                item("cultura_cinemas_10k", "cultura",
                     {"kind": "observation", "source_id": "pordata", "dataset_id": "recintos_cinema",
                      "filters": [{}], "dash_is_zero": True,
                      "per_population": {"scale": 10000, "age_groups": None}}),
                item("emprego_ganho_medio_mensal", "emprego",
                     {"kind": "observation", "source_id": "pordata", "dataset_id": "ganho_medio_mensal",
                      "filters": [{}], "dash_is_zero": False}),
                item("populacao_residentes", "populacao",
                     {"kind": "observation", "source_id": "pordata", "dataset_id": "populacao_residente_sexo_idade",
                      "filters": [{"filter_1": "Total", "filter_2": "Total"}], "dash_is_zero": True},
                     weight=0.5, levels=("municipio", "freguesia"),
                     compute_parish={"kind": "census", "metric": "residentes"}),
                item("populacao_pct_25_39", "populacao",
                     {"kind": "observation", "source_id": "pordata", "dataset_id": "populacao_residente_sexo_idade",
                      "filters": [{"filter_1": "Total", "filter_2": age} for age in AGES], "dash_is_zero": True,
                      "share": {"filters": {"filter_1": "Total", "filter_2": "Total"}, "scale": 100}},
                     weight=0.5, levels=("municipio", "freguesia"),
                     compute_parish={"kind": "census", "metric": "pct_25_39"}),
                item("distancia_lisboa_carro_min", "distancia",
                     {"kind": "mobility", "mode": "driving", "measure": "minutes", "pole_id": "lisboa"}),
                item("distancia_aeroporto_km", "distancia",
                     {"kind": "mobility", "mode": "straight_line", "measure": "km", "nearest_kind": "aeroporto"},
                     weight=0.0, modes=("faixa",)),
                {**item("distancia_sede_distrito_km", "distancia", None, weight=0.0, modes=("faixa",)),
                 "status": "fonte_pendente", "pending_reason": "fixture: polos de sede de distrito não configurados"},
            ]}


def seed(root) -> dict:
    """Grava o lake mínimo e `criteria.yml` em `root`; devolve as contagens e o catálogo."""
    root = Path(root)
    _write(root, "silver", "dim_municipality", [
        {"dico": dico, "official_name": name, "normalized_name": name.lower(), "autonomous_region": region,
         "area_km2": area, "caop_version": "fixture-2025", "license_id": "CC-BY-4.0"}
        for dico, name, region, area in MUNICIPALITIES])
    _write(root, "silver", "dim_parish", [
        {"dicofre": dicofre, "dico": dico, "official_name": dicofre, "area_km2": area, "caop_version": "fixture-2025",
         "license_id": "CC-BY-4.0"} for dicofre, dico, area in PARISHES])
    _write(root, "bronze", "stg_observation", observations())
    _write(root, "bronze", "stg_climate_daily", climate())
    _write(root, "bronze", "dim_mobility_pole", poles())
    _write(root, "bronze", "stg_municipality_pole_distance", distances())
    _write(root, "silver", "idealista_listings", listings())
    _write(root, "silver", "census_parish_observation", census())
    catalog = criteria()
    (root / "criteria.yml").write_text(yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False),
                                       encoding="utf-8")
    return {"municipalities": len(MUNICIPALITIES), "parishes": len(PARISHES), "criteria": catalog}


def main():
    parser = argparse.ArgumentParser(description="Gera o lake mínimo e o catálogo sintético da camada Gold (offline).")
    parser.add_argument("--root", type=Path, default=Path(".data/ci-gold"))
    args = parser.parse_args()
    if args.root.exists() and any(args.root.iterdir()):
        parser.error(f"{args.root} já existe e não está vazio; use outro --root")
    seed(args.root)
    print(f"fixture Gold em {args.root}")


if __name__ == "__main__":
    main()
