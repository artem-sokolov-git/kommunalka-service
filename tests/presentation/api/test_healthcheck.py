from urllib.error import URLError

import pytest

from kommunalka.presentation.api import healthcheck


class Response:
    def close(self) -> None:
        pass


def test_healthy_when_the_server_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(healthcheck, "urlopen", lambda url, timeout: Response())

    assert healthcheck.main() == 0


def test_unhealthy_when_the_server_is_down(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(url: str, timeout: float) -> Response:
        raise URLError("connection refused")

    monkeypatch.setattr(healthcheck, "urlopen", refuse)

    assert healthcheck.main() == 1
    assert "connection refused" in capsys.readouterr().err
