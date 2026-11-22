"""Relatório de cobertura da mobilidade com os quatro estados e polos alterados (spec 009, US3, FR-023/025)."""
import pandas as pd
import yaml

from pipelines.cli import build_mobility as builder
from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from tests.fixtures.mobility.ci_seed import seed

BRONZE = "lake/bronze"


def build(root):
    return builder.build_mobility(root, catalog=load_catalog(root / "catalog.yml"), poles_path=root / "poles.yml")


def csv(root, name):
    return pd.read_csv(root / BRONZE / name, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)


def test_the_four_states_add_up_to_the_expected_pairs_and_the_absences_are_explained(tmp_path):
    seed(tmp_path, collect=True)
    result = build(tmp_path)
    coverage = result["coverage"].set_index(["mode", "pole_id"])
    sums = coverage[["ok", "sem_rota", "falha", "pendente"]].sum(axis=1)
    assert (sums == coverage["expected"]).all()  # US3-AC1
    driving = coverage.loc["driving"]
    assert driving.loc["aeroporto_x", ["expected", "ok", "sem_rota", "falha", "pendente"]].tolist() == [3, 1, 1, 1, 0]
    assert driving.loc["cidade_a", ["expected", "ok", "sem_rota", "falha", "pendente"]].tolist() == [3, 2, 1, 0, 0]
    assert coverage.loc[("straight_line", "aeroporto_x"), "ok"] == 5  # every municipality has a straight line

    no_route = csv(tmp_path, "mobility_no_route.csv")
    found = no_route[no_route["reason"] == "ROUTE_NOT_FOUND"]
    assert set(zip(found["dico"], found["pole_id"], found["mode"], strict=True)) == {
        ("0201", pole, mode) for pole in ("aeroporto_x", "cidade_a") for mode in ("driving", "transit")}
    assert (found["expected_absence"] == "False").all() and set(found["name"]) == {"Gama"}  # to investigate
    islands = no_route[no_route["reason"] == "sem_polo_elegivel"]
    assert set(islands["dico"]) == {"3102"} and (islands["expected_absence"] == "True").all()  # US3-AC2

    pending = csv(tmp_path, "mobility_pending.csv")
    assert pending[["dico", "pole_id", "mode", "status"]].values.tolist() == [
        ["0102", "aeroporto_x", "driving", "falha"]]
    assert "status 8" in pending["error"].iloc[0] and csv(tmp_path, "mobility_stale.csv").empty
    staging = pd.read_parquet(tmp_path / BRONZE / "stg_municipality_pole_distance/data.parquet")
    routed = staging[staging["mode"] != "straight_line"]
    assert routed[routed["status"] != "ok"]["km"].isna().all()  # nothing is invented for the absences


def test_a_changed_pole_lists_its_stored_pairs_as_stale_without_touching_their_results(tmp_path):
    seed(tmp_path, collect=True)
    build(tmp_path)
    before = pd.read_parquet(tmp_path / BRONZE / "stg_municipality_pole_distance/data.parquet")
    document = yaml.safe_load((tmp_path / "poles.yml").read_text(encoding="utf-8"))
    next(pole for pole in document["poles"] if pole["pole_id"] == "aeroporto_x")["latitude"] = 38.79
    (tmp_path / "poles.yml").write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    build(tmp_path)
    stale = csv(tmp_path, "mobility_stale.csv")
    assert set(zip(stale["dico"], stale["mode"], strict=True)) == {
        ("0101", "driving"), ("0101", "transit"), ("0102", "transit"), ("0201", "driving"), ("0201", "transit")}
    assert set(stale["pole_id"]) == {"aeroporto_x"} and set(stale["status"]) == {"ok", "sem_rota"}  # FR-025
    after = pd.read_parquet(tmp_path / BRONZE / "stg_municipality_pole_distance/data.parquet")
    key = ["dico", "pole_id", "mode"]
    pairs = after[after["stale"]][key]
    merged = after.merge(pairs, on=key).merge(before, on=key, suffixes=("_new", "_old"))
    assert (merged["km_new"].fillna(-1) == merged["km_old"].fillna(-1)).all()
    assert (merged["status_new"] == merged["status_old"]).all()
    coverage = csv(tmp_path, "mobility_coverage.csv")
    assert int(coverage[(coverage["mode"] == "driving") & (coverage["pole_id"] == "aeroporto_x")]["stale"].iloc[0]) == 2


def poles_args(root):
    return ["--local", "--root", str(root), "--catalog", str(root / "catalog.yml"), "--poles", str(root / "poles.yml")]


def test_every_report_carries_the_google_attribution_and_the_accepted_risk(tmp_path, capsys):
    seed(tmp_path, collect=True)
    build(tmp_path)
    for name in ("mobility_coverage.csv", "mobility_no_route.csv", "mobility_pending.csv", "mobility_stale.csv",
                 "mobility_retired.csv"):
        frame = csv(tmp_path, name)
        assert {"attribution", "usage_restriction"} <= set(frame.columns), name  # US3-AC4
        assert set(frame[frame["mode"] != "straight_line"]["attribution"]) <= {"Tempos de viagem: Google"}, name
        assert (frame[frame["mode"] == "straight_line"]["attribution"] == "").all(), name
    coverage = csv(tmp_path, "mobility_coverage.csv")
    google = coverage[coverage["mode"] == "driving"]
    assert not google.empty and set(google["attribution"]) == {"Tempos de viagem: Google"}
    assert all("risco aceito" in value for value in google["usage_restriction"])
    assert builder.main(poles_args(tmp_path)) == 0
    assert "Tempos de viagem: Google" in capsys.readouterr().out


def test_a_retired_pole_lists_its_stored_pairs_and_leaves_the_staging(tmp_path, capsys):
    seed(tmp_path, collect=True)
    build(tmp_path)
    assert csv(tmp_path, "mobility_retired.csv").empty
    document = yaml.safe_load((tmp_path / "poles.yml").read_text(encoding="utf-8"))
    document["poles"] = [pole for pole in document["poles"] if pole["pole_id"] != "aeroporto_x"]
    (tmp_path / "poles.yml").write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    assert builder.main(poles_args(tmp_path)) == 0
    assert "mobility_retired.csv" in capsys.readouterr().out
    retired = csv(tmp_path, "mobility_retired.csv")
    assert set(zip(retired["dico"], retired["mode"], strict=True)) == {
        ("0101", "driving"), ("0101", "transit"), ("0102", "transit"), ("0201", "driving"), ("0201", "transit")}
    assert set(retired["pole_id"]) == {"aeroporto_x"} and set(retired["source_run_id"]) == {"ci-mobility"}
    assert set(retired["attribution"]) == {"Tempos de viagem: Google"}
    staging = pd.read_parquet(tmp_path / BRONZE / "stg_municipality_pole_distance/data.parquet")
    assert "aeroporto_x" not in set(staging["pole_id"])  # out of the staging, still in the immutable raw layer
    assert len(LocalStorage(tmp_path).list_keys("raw/")) == 9  # 5 ok + 4 sem_rota; the failed pair stores nothing
