"""Script to mass-star popular GitHub repositories.

Requirements:
    pip install requests

Usage:
    python star_repos.py
    Enter your GitHub username and a Personal Access Token with the
    'public_repo' scope when prompted.

Example:
    $ python star_repos.py
    GitHub username: your_username
    Personal access token (with public_repo scope): ****
    ✅ Starred torvalds/linux
    ...
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from getpass import getpass
from typing import Final

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API_BASE: Final[str] = "https://api.github.com"
ACCEPT_HEADER: Final[str] = "application/vnd.github.v3+json"

DEFAULT_REPOS: Final[list[str]] = [
    "torvalds/linux",
    "octocat/Hello-World",
    "github/gitignore",
    "microsoft/vscode",
    "facebook/react",
    "vuejs/vue",
    "angular/angular",
    "tensorflow/tensorflow",
    "twbs/bootstrap",
    "ohmyzsh/ohmyzsh",
    "freeCodeCamp/freeCodeCamp",
    "sindresorhus/awesome",
    "kamranahmedse/developer-roadmap",
    "EbookFoundation/free-programming-books",
    "jwasham/coding-interview-university",
    "donnemartin/system-design-primer",
]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GitHubError(Exception):
    """Raised when a GitHub API request fails."""


class AuthenticationError(GitHubError):
    """Raised when GitHub authentication fails."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class StarResult:
    """Result of a single star operation.

    Attributes:
        repo: Repository slug in ``owner/name`` format.
        success: Whether the operation succeeded.
        status_code: HTTP status code returned by the API.
        message: Human-readable detail message.
    """

    repo: str
    success: bool
    status_code: int
    message: str = ""


@dataclass
class StarSession:
    """Holds credentials and state for a starring session.

    Attributes:
        username: GitHub username.
        token: Personal access token with ``public_repo`` scope.
        results: Accumulated :class:`StarResult` objects.
    """

    username: str
    token: str
    results: list[StarResult] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not self.username.strip():
            raise ValueError("username must not be empty")
        if not self.token.strip():
            raise ValueError("token must not be empty")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": ACCEPT_HEADER,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def star(self, repo: str) -> StarResult:
        """Star a single GitHub repository.

        Args:
            repo: Repository slug in ``owner/name`` format.

        Returns:
            A :class:`StarResult` describing the outcome.

        Raises:
            AuthenticationError: If the token is invalid or expired (HTTP 401).
            GitHubError: For unexpected HTTP errors.
        """
        if "/" not in repo:
            raise ValueError(f"Invalid repository format '{repo}'. Expected 'owner/name'.")

        url = f"{GITHUB_API_BASE}/user/starred/{repo}"
        try:
            response = requests.put(url, headers=self._headers, timeout=10)
        except requests.RequestException as exc:
            raise GitHubError(f"Network error while starring '{repo}': {exc}") from exc

        match response.status_code:
            case 204:
                result = StarResult(repo=repo, success=True, status_code=204)
                logger.info("✅ Starred %s", repo)
            case 401:
                raise AuthenticationError("Authentication failed – check your username and token.")
            case _:
                result = StarResult(
                    repo=repo,
                    success=False,
                    status_code=response.status_code,
                    message=response.text,
                )
                logger.warning(
                    "❌ Failed to star %s: %s – %s", repo, response.status_code, response.text
                )

        self.results.append(result)
        return result

    def star_all(self, repos: list[str]) -> list[StarResult]:
        """Star every repository in *repos*.

        Args:
            repos: List of repository slugs in ``owner/name`` format.

        Returns:
            List of :class:`StarResult` objects, one per repository.
        """
        return [self.star(repo) for repo in repos]

    def summary(self) -> str:
        """Return a human-readable summary of the session results.

        Returns:
            Multi-line summary string with success/failure counts.
        """
        total = len(self.results)
        succeeded = sum(1 for r in self.results if r.success)
        failed = total - succeeded
        lines = [
            f"Session summary for @{self.username}:",
            f"  Total:   {total}",
            f"  Starred: {succeeded}",
            f"  Failed:  {failed}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _prompt_credentials() -> tuple[str, str]:
    """Prompt the user for their GitHub credentials interactively.

    Returns:
        A ``(username, token)`` tuple.
    """
    username = input("GitHub username: ").strip()
    token = getpass("Personal access token (with public_repo scope): ").strip()
    return username, token


def main(repos: list[str] | None = None) -> None:
    """Run the starring workflow.

    Args:
        repos: Optional list of ``owner/name`` slugs to star.  Defaults to
            :data:`DEFAULT_REPOS` when *None*.
    """
    if repos is None:
        repos = DEFAULT_REPOS

    try:
        username, token = _prompt_credentials()
        session = StarSession(username=username, token=token)
    except ValueError as exc:
        logger.error("Invalid credentials: %s", exc)
        sys.exit(1)

    try:
        session.star_all(repos)
    except AuthenticationError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except GitHubError as exc:
        logger.error("GitHub API error: %s", exc)
        sys.exit(1)

    print(session.summary())


if __name__ == "__main__":
    main()
