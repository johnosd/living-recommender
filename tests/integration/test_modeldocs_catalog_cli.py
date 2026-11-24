"""CLI `lake_catalog` (spec 010, T010): resumo, falha com o arquivo em uso e raiz sem lake."""
import json

import duckdb

from pipelines.cli import lake_catalog as cli
from tests.fixtures.modeldocs.lake import write_manifest, write_table
from tests.fixtures.modeldocs.manifests import column, make_manifest, model


def prepare(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(make_manifest([model("a", columns=[column("x")]), model("b")])), encoding="utf-8")
    root = tmp_path / "data"
    write_table(root / "lake", "bronze", "a", {"x": [1, 2]})
    (root / "lake" / "bronze" / "report.csv").write_text("a\n1\n", encoding="utf-8")
    write_manifest(root / "manifests", "caop", "r1")
    return manifest, root


def test_the_default_output_is_catalog_duckdb_under_the_root_and_the_summary_counts_everything(tmp_path, capsys):
    manifest, root = prepare(tmp_path)
    assert cli.main(["--root", str(root), "--manifest", str(manifest)]) == 0
    out = capsys.readouterr().out
    assert "1 ok, 1 não construídas, 0 sem modelo" in out and "ignoradas (não são tabelas): 1" in out
    assert "1 lidos, 0 ignorados" in out
    connection = duckdb.connect(str(root / "catalog.duckdb"), read_only=True)
    assert connection.execute("select count(*) from bronze.a").fetchone() == (2,)
    connection.close()


def test_a_root_without_a_lake_still_succeeds(tmp_path, capsys):
    manifest, _ = prepare(tmp_path)
    assert cli.main(["--root", str(tmp_path / "empty"), "--manifest", str(manifest)]) == 0
    assert "0 ok, 2 não construídas" in capsys.readouterr().out


def test_a_locked_output_exits_with_1_asks_to_close_the_client_and_keeps_the_old_file(tmp_path, capsys, monkeypatch):
    manifest, root = prepare(tmp_path)
    assert cli.main(["--root", str(root), "--manifest", str(manifest)]) == 0
    before = (root / "catalog.duckdb").read_bytes()
    capsys.readouterr()

    def locked(source, target):
        raise PermissionError("em uso")

    monkeypatch.setattr("pipelines.modeldocs.catalog.os.replace", locked)
    assert cli.main(["--root", str(root), "--manifest", str(manifest)]) == 1
    assert "Feche o cliente SQL" in capsys.readouterr().err
    assert (root / "catalog.duckdb").read_bytes() == before


def test_an_unreadable_manifest_file_exits_with_2(tmp_path, capsys):
    assert cli.main(["--root", str(tmp_path), "--manifest", str(tmp_path / "missing.json")]) == 2
    assert "dbt" in capsys.readouterr().err
