"""Resolução e redação da chave (spec 009, FR-010, constitution I)."""
from urllib.parse import quote

import pytest

from pipelines.collectors.mobility.secrets import redact, resolve_api_key
from tests.fixtures.mobility.responses import KEY_SENTINEL

SOURCE = {"key_env": "GOOGLE_ROUTES_API_KEY"}


def test_the_key_comes_from_the_environment():
    assert resolve_api_key({"GOOGLE_ROUTES_API_KEY": f"  {KEY_SENTINEL}  "}, SOURCE) == KEY_SENTINEL


def test_dotenv_is_used_only_when_a_root_is_given(tmp_path):
    (tmp_path / ".env").write_text(
        f"# comentário\nOUTRA=1\nexport GOOGLE_ROUTES_API_KEY='{KEY_SENTINEL}'\n", encoding="utf-8")
    assert resolve_api_key({}, SOURCE, root=tmp_path) == KEY_SENTINEL
    with pytest.raises(ValueError, match="GOOGLE_ROUTES_API_KEY"):
        resolve_api_key({}, SOURCE)  # an injected environment never falls back to a real .env


def test_the_environment_wins_over_dotenv(tmp_path):
    (tmp_path / ".env").write_text("GOOGLE_ROUTES_API_KEY=from-dotenv-value\n", encoding="utf-8")
    assert resolve_api_key({"GOOGLE_ROUTES_API_KEY": KEY_SENTINEL}, SOURCE, root=tmp_path) == KEY_SENTINEL


@pytest.mark.parametrize("env", [{}, {"GOOGLE_ROUTES_API_KEY": ""}, {"GOOGLE_ROUTES_API_KEY": "   "},
                                 {"GOOGLE_ROUTES_API_KEY": "short"}, {"GOOGLE_ROUTES_API_KEY": "with space inside"}])
def test_a_missing_or_malformed_key_fails_without_printing_a_value(env):
    with pytest.raises(ValueError, match="GOOGLE_ROUTES_API_KEY") as error:
        resolve_api_key(env, SOURCE)
    for value in env.values():
        assert not value.strip() or value not in str(error.value)


def test_redact_replaces_every_form_of_the_secret_and_leaves_the_rest():
    secret = "key with/odd+chars&1234"
    text = f"a {secret} b {quote(secret, safe='')} c {quote(secret)} d"
    assert redact(text, secret) == "a [REDACTED] b [REDACTED] c [REDACTED] d"
    assert redact("nada a esconder", secret) == "nada a esconder"
    assert redact(ValueError(f"erro {secret}"), secret) == "erro [REDACTED]"
    assert redact("sem segredo", None, "") == "sem segredo"
