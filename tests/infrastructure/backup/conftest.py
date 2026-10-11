import base64
import json
import sqlite3
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from kommunalka.infrastructure.backup.github import GitHubFile, blob_sha


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """A small SQLite database file to back up and restore."""
    path = tmp_path / "kommunalka.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE readings (value TEXT)")
    connection.execute("INSERT INTO readings VALUES ('41768')")
    connection.commit()
    connection.close()
    return path


def values(database: Path) -> list[str]:
    connection = sqlite3.connect(database)
    try:
        return [value for (value,) in connection.execute("SELECT value FROM readings")]
    finally:
        connection.close()


def add_reading(database: Path, value: str) -> None:
    connection = sqlite3.connect(database)
    connection.execute("INSERT INTO readings VALUES (?)", (value,))
    connection.commit()
    connection.close()


class FakeGitHub(ThreadingHTTPServer):
    """The contents and commits endpoints of one GitHub repository, kept in memory."""

    TOKEN = "github_pat_test"

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _FakeGitHubHandler)
        self.commits: list[dict[str, Any]] = []
        """Oldest first: sha, message, date and the files at that commit."""

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"

    def files(self, ref: str) -> dict[str, str] | None:
        if ref == "main":
            return self.commits[-1]["files"] if self.commits else None
        commit = next((c for c in self.commits if c["sha"].startswith(ref)), None)
        return commit["files"] if commit else None


class _FakeGitHubHandler(BaseHTTPRequestHandler):
    server: FakeGitHub

    def do_GET(self) -> None:
        if not self._authorized():
            return
        url = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        if url.path.endswith("/commits"):
            commits = [
                {
                    "sha": c["sha"],
                    "commit": {"message": c["message"], "committer": {"date": c["date"]}},
                }
                for c in reversed(self.server.commits)
                if query["path"] in c["files"]
            ]
            return self._reply(200, json.dumps(commits[: int(query.get("per_page", 30))]))
        path = url.path.split("/contents/", 1)[1]
        text = (self.server.files(query.get("ref", "main")) or {}).get(path)
        if text is None:
            return self._reply(404, json.dumps({"message": "Not Found"}))
        if "raw" in self.headers["Accept"]:
            return self._reply(200, text)
        return self._reply(200, json.dumps({"sha": blob_sha(text)}))

    def do_PUT(self) -> None:
        if not self._authorized():
            return
        path = urlparse(self.path).path.split("/contents/", 1)[1]
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        files = dict(self.server.files("main") or {})
        current = files.get(path)
        if body.get("sha") != (blob_sha(current) if current is not None else None):
            return self._reply(409, json.dumps({"message": "sha does not match"}))
        files[path] = base64.b64decode(body["content"]).decode()
        number = len(self.server.commits) + 1
        self.server.commits.append(
            {
                "sha": f"{number:07x}" + "0" * 33,
                "message": body["message"],
                "date": f"2026-10-{number:02d}T00:00:00Z",
                "files": files,
            }
        )
        self._reply(201, json.dumps({"commit": {"sha": self.server.commits[-1]["sha"]}}))

    def _authorized(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {FakeGitHub.TOKEN}":
            return True
        self._reply(401, json.dumps({"message": "Bad credentials"}))
        return False

    def _reply(self, status: int, body: str) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        pass


@pytest.fixture
def github() -> Iterator[FakeGitHub]:
    server = FakeGitHub()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def backup_file(github: FakeGitHub) -> GitHubFile:
    """The dump in the fake backup repository."""
    return GitHubFile(
        "https://github.com/owner/backups.git",
        "kommunalka.sql",
        token=FakeGitHub.TOKEN,
        api_url=github.url,
    )
