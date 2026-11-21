"""Contratos da estrutura e dos espelhos das skills SDD."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ("adhoc", "adr", "assess", "bugfix", "converge", "execute", "plan", "specify")


def test_project_layout():
    assert (ROOT / ".sdd/specs").is_dir()
    assert (ROOT / ".docs/runbooks/coletas.md").is_file()
    assert (ROOT / ".docs/fontes_de_dados.md").is_file()
    assert not (ROOT / "sdd").exists()
    assert not (ROOT / "docs").exists()


@pytest.mark.parametrize("name", SKILLS)
def test_skill_mirrors_and_memory(name):
    relative = Path("skills") / f"sdd-{name}" / "SKILL.md"
    agents = (ROOT / ".agents" / relative).read_bytes()
    assert agents == (ROOT / ".claude" / relative).read_bytes()
    assert agents == (ROOT / ".claude/.agents" / relative).read_bytes()
    content = agents.decode("utf-8").lower()
    assert ".planning/memory/" in content
    assert "longo prazo" in content
    assert "constitution.md" in content
    assert not re.search(r"(?<![\w.:-])(?:sdd|docs)[/\\]", content)


@pytest.mark.parametrize("name", ("AGENTS.md", "CLAUDE.md"))
def test_agent_instructions(name):
    content = (ROOT / name).read_text(encoding="utf-8").lower()
    for path in (".sdd/", ".docs/", ".planning/memory/", "constitution.md"):
        assert path in content


def test_scripts_create_artifacts_in_hidden_root(tmp_path):
    powershell = shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")
    if powershell is None:
        pytest.skip("PowerShell indisponível")
    planning = tmp_path / ".planning"
    shutil.copytree(ROOT / ".planning/scripts/powershell", planning / "scripts/powershell")
    shutil.copytree(ROOT / ".planning/templates", planning / "templates")

    def run(script, *args):
        result = subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(planning / "scripts/powershell" / script), *args, "-Json"],
            cwd=tmp_path, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
        )
        return json.loads(result.stdout.lstrip("\ufeff"))

    feature = run("new-feature.ps1", "Teste migracao")
    adr = run("new-adr.ps1", "Teste migracao")
    bug = run("resolve-bug.ps1", "-Slug", "teste")
    assessment = run("resolve-assessment.ps1", "-Slug", "teste")
    assert Path(feature["SPEC_FILE"]).is_file()
    assert Path(feature["FEATURE_DIR"]).parent == tmp_path / ".sdd/specs"
    assert Path(adr["ADR_FILE"]).parent == tmp_path / ".sdd/adr"
    assert Path(bug["BUG_DIR"]).parent == tmp_path / ".sdd/bugs"
    assert Path(assessment["ASSESS_DIR"]).parent == tmp_path / ".sdd/assessments"
    assert not (tmp_path / "sdd").exists()
