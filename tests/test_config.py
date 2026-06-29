from __future__ import annotations

from pathlib import Path

from glyphhold_mcp.config import load_settings


def test_load_settings_reads_dotenv_from_working_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GLYPHHOLD_URL", raising=False)
    monkeypatch.delenv("GLYPHHOLD_API_KEY", raising=False)
    monkeypatch.delenv("GLYPHHOLD_VERIFY_SSL", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "GLYPHHOLD_URL=https://glyphhold.example.com",
                "GLYPHHOLD_API_KEY=gh_live_test",
                "GLYPHHOLD_VERIFY_SSL=false",
            ]
        )
    )

    settings = load_settings()

    assert settings.glyphhold_url == "https://glyphhold.example.com"
    assert settings.api_key == "gh_live_test"
    assert settings.verify_ssl is False


def test_ca_bundle_takes_precedence_over_verify_flag(tmp_path: Path, monkeypatch) -> None:
    ca_bundle = tmp_path / "ca.pem"
    ca_bundle.write_text("test ca")
    monkeypatch.setenv("GLYPHHOLD_URL", "https://glyphhold.example.com")
    monkeypatch.setenv("GLYPHHOLD_API_KEY", "gh_live_test")
    monkeypatch.setenv("GLYPHHOLD_VERIFY_SSL", "false")
    monkeypatch.setenv("GLYPHHOLD_CA_BUNDLE", str(ca_bundle))

    settings = load_settings()

    assert settings.verify_ssl == str(ca_bundle)
