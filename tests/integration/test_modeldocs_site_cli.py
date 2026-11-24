"""CLI `dbt_docs_site` com o dbt real (spec 010, T022): site gerado, aresta fonte-modelo e nada fora da saída."""
import json

import pytest

from pipelines.cli import dbt_docs_site as cli
from tests.fixtures.modeldocs.lake import snapshot, write_table

DIM = "model.caop_territory.dim_municipality"
SOURCE = "source.caop_territory.caop_silver.dim_municipality"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    write_table(root / "lake", "silver", "dim_municipality", {"dico": ["0101", "0102"], "extra": [1, 2]})
    before = snapshot(root)
    assert cli.main(["--root", str(root)]) == 0
    return root, root / "dbt-docs", before


def test_the_site_has_the_index_the_manifest_with_the_linked_source_and_the_real_catalog(site):
    _, output, _ = site
    assert (output / "index.html").stat().st_size > 100_000
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["child_map"][DIM].count(SOURCE) == 1 and manifest["parent_map"][SOURCE] == [DIM]
    assert len([n for n in manifest["nodes"].values() if n["resource_type"] == "model"]) >= 25
    catalog = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
    assert list(catalog["nodes"]) == [DIM]  # only the table that exists in the lake
    assert list(catalog["nodes"][DIM]["columns"]) == ["dico", "extra"]  # includes the undeclared column


def test_the_lake_is_not_touched_and_nothing_is_created_outside_the_output(site):
    root, output, before = site
    after = snapshot(root)
    assert {path: digest for path, digest in after.items() if not path.startswith("dbt-docs")} == before
    assert (output / "never-used.duckdb").exists()  # the connection dbt opens stays inside the output


def test_without_a_lake_the_site_is_still_generated_with_an_empty_catalog(tmp_path):
    assert cli.main(["--root", str(tmp_path)]) == 0
    assert json.loads((tmp_path / "dbt-docs" / "catalog.json").read_text(encoding="utf-8"))["nodes"] == {}


def test_without_the_dbt_executable_the_command_exits_with_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("pipelines.cli.dbt_docs_site.shutil.which", lambda name: None)
    assert cli.main(["--root", str(tmp_path)]) == 2
    assert "dbt" in capsys.readouterr().err


def test_serve_binds_only_to_localhost(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "generate", lambda root, output, executable: 0)

    class Done:
        returncode = 0

    monkeypatch.setattr(cli.subprocess, "run", lambda command, **kwargs: calls.append(command) or Done())
    assert cli.main(["--root", str(tmp_path), "--serve", "--port", "8099"]) == 0
    served = calls[0]
    assert served[1:3] == ["docs", "serve"] and served[served.index("--host") + 1] == "127.0.0.1"
    assert "--no-browser" in served and served[served.index("--port") + 1] == "8099"


def test_serve_refuses_a_port_that_is_already_taken(tmp_path, capsys):
    import socket

    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        assert cli.main(["--root", str(tmp_path), "--serve", "--port", str(port)]) == 2
    assert f"porta {port}" in capsys.readouterr().err
    assert not (tmp_path / "dbt-docs").exists()  # fails before generating anything
