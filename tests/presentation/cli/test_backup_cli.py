from pathlib import Path

import pytest

from kommunalka.infrastructure.config import get_settings
from kommunalka.presentation.cli.backup import main
from tests.infrastructure.backup.conftest import FakeGitHub


def test_cli_takes_everything_from_settings(
    database: Path, github: FakeGitHub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KOMMUNALKA_DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_DIR", str(tmp_path / "copies"))
    monkeypatch.setenv("KOMMUNALKA_DB_BACKUP_REPO_URL", "owner/backups")
    monkeypatch.setenv("KOMMUNALKA_BACKUP_GITHUB_TOKEN", FakeGitHub.TOKEN)
    monkeypatch.setenv("KOMMUNALKA_GITHUB_API_URL", github.url)
    monkeypatch.setattr("sys.argv", ["backup"])
    get_settings.cache_clear()
    try:
        main()
    finally:
        get_settings.cache_clear()

    assert len(list((tmp_path / "copies").glob("kommunalka-*.db"))) == 1
    assert "41768" in github.commits[-1]["files"]["kommunalka.sql"]
