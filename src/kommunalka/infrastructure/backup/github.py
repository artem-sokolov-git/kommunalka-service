"""A file in a GitHub repository, read and written through the REST Contents API.

Every write is a commit, so the history of the file is the history of backups. No clone and
no git binary are needed.
"""

import base64
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class GitHubError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Revision:
    sha: str
    date: str
    message: str


class GitHubFile:
    def __init__(
        self,
        repo: str,
        path: str,
        *,
        token: str | None = None,
        branch: str = "main",
        api_url: str = "https://api.github.com",
    ) -> None:
        """`repo` is `owner/name` or a URL of the repository."""
        self.repo = repo_name(repo)
        self.path = path
        self.branch = branch
        self._token = token
        self._api_url = api_url.rstrip("/")

    def read(self, revision: str | None = None) -> str | None:
        """The file at `revision` (default: the branch), None if it doesn't exist there."""
        query = {"ref": revision or self.branch}
        body = self._request("GET", self._contents_url(query), raw=True, missing_ok=True)
        return None if body is None else body.decode()

    def write(self, text: str, message: str) -> bool:
        """Commit `text` as the file; return False without a commit if it is the same already."""
        current = self._request("GET", self._contents_url({"ref": self.branch}), missing_ok=True)
        sha = json.loads(current)["sha"] if current is not None else None
        if sha == blob_sha(text):
            return False
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(text.encode()).decode(),
            "branch": self.branch,
        }
        if sha is not None:
            payload["sha"] = sha
        self._request("PUT", self._contents_url(), data=payload)
        return True

    def history(self, limit: int = 20) -> list[Revision]:
        """Commits that changed the file, newest first."""
        query = {"path": self.path, "sha": self.branch, "per_page": str(limit)}
        url = f"{self._api_url}/repos/{self.repo}/commits?{urllib.parse.urlencode(query)}"
        body = self._request("GET", url, missing_ok=True)
        commits = json.loads(body) if body is not None else []
        return [
            Revision(
                sha=commit["sha"],
                date=commit["commit"]["committer"]["date"],
                message=commit["commit"]["message"],
            )
            for commit in commits
        ]

    def _contents_url(self, query: dict[str, str] | None = None) -> str:
        url = f"{self._api_url}/repos/{self.repo}/contents/{urllib.parse.quote(self.path)}"
        return f"{url}?{urllib.parse.urlencode(query)}" if query else url

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        raw: bool = False,
        missing_ok: bool = False,
    ) -> bytes | None:
        headers = {
            "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        body = json.dumps(data).encode() if data is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404 and missing_ok:
                return None
            detail = error.read().decode(errors="replace")
            message = (
                json.loads(detail).get("message", detail) if detail.startswith("{") else detail
            )
            raise GitHubError(f"GitHub {method} {self.repo}: {error.code} {message}") from None
        except urllib.error.URLError as error:
            raise GitHubError(f"GitHub {method} {self.repo}: {error.reason}") from None


def repo_name(repo: str) -> str:
    """`owner/name` from `owner/name` or a repository URL like https://github.com/owner/name.git."""
    match = re.fullmatch(r"(?:https?://[^/]+/)?([\w.-]+/[\w.-]+?)(?:\.git)?/?", repo.strip())
    if match is None:
        raise GitHubError(f"Not a GitHub repository: {repo!r}")
    return match[1]


def blob_sha(text: str) -> str:
    """The git blob id of `text`, as GitHub reports it for a file with that content."""
    data = text.encode()
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()
