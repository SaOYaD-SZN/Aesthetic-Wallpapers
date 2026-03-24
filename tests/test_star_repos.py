"""Tests for star_repos.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from star_repos import (
    AuthenticationError,
    GitHubError,
    StarResult,
    StarSession,
)

# ---------------------------------------------------------------------------
# StarSession.__post_init__ validation
# ---------------------------------------------------------------------------


def test_star_session_empty_username_raises() -> None:
    with pytest.raises(ValueError, match="username"):
        StarSession(username="", token="tok")


def test_star_session_empty_token_raises() -> None:
    with pytest.raises(ValueError, match="token"):
        StarSession(username="user", token="")


def test_star_session_whitespace_username_raises() -> None:
    with pytest.raises(ValueError, match="username"):
        StarSession(username="   ", token="tok")


# ---------------------------------------------------------------------------
# StarSession._headers
# ---------------------------------------------------------------------------


def test_star_session_headers_contain_bearer() -> None:
    session = StarSession(username="user", token="mytoken")
    assert session._headers["Authorization"] == "Bearer mytoken"
    assert "github" in session._headers["Accept"]


# ---------------------------------------------------------------------------
# StarSession.star – success (HTTP 204)
# ---------------------------------------------------------------------------


def _make_response(status_code: int, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def test_star_success() -> None:
    session = StarSession(username="user", token="tok")
    with patch("star_repos.requests.put", return_value=_make_response(204)) as mock_put:
        result = session.star("owner/repo")

    mock_put.assert_called_once()
    assert result.success is True
    assert result.status_code == 204
    assert result.repo == "owner/repo"


def test_star_failure_non_204() -> None:
    session = StarSession(username="user", token="tok")
    with patch(
        "star_repos.requests.put",
        return_value=_make_response(404, "Not Found"),
    ):
        result = session.star("owner/missing")

    assert result.success is False
    assert result.status_code == 404
    assert "Not Found" in result.message


def test_star_authentication_error() -> None:
    session = StarSession(username="user", token="bad")
    with patch("star_repos.requests.put", return_value=_make_response(401)):
        with pytest.raises(AuthenticationError):
            session.star("owner/repo")


def test_star_invalid_repo_format() -> None:
    session = StarSession(username="user", token="tok")
    with pytest.raises(ValueError, match="Invalid repository format"):
        session.star("nodashslash")


def test_star_network_error() -> None:
    import requests as req

    session = StarSession(username="user", token="tok")
    with patch("star_repos.requests.put", side_effect=req.ConnectionError("timeout")):
        with pytest.raises(GitHubError, match="Network error"):
            session.star("owner/repo")


# ---------------------------------------------------------------------------
# StarSession.star_all
# ---------------------------------------------------------------------------


def test_star_all_returns_all_results() -> None:
    session = StarSession(username="user", token="tok")
    repos = ["a/b", "c/d", "e/f"]
    with patch("star_repos.requests.put", return_value=_make_response(204)):
        results = session.star_all(repos)

    assert len(results) == len(repos)
    assert all(r.success for r in results)
    # results are also accumulated in session.results
    assert len(session.results) == len(repos)


# ---------------------------------------------------------------------------
# StarResult helpers
# ---------------------------------------------------------------------------


def test_star_result_defaults() -> None:
    result = StarResult(repo="x/y", success=True, status_code=204)
    assert result.message == ""


# ---------------------------------------------------------------------------
# StarSession.summary
# ---------------------------------------------------------------------------


def test_summary_contains_username_and_counts() -> None:
    session = StarSession(username="alice", token="tok")
    with patch(
        "star_repos.requests.put",
        side_effect=[
            _make_response(204),
            _make_response(422, "error"),
        ],
    ):
        session.star("a/b")
        session.star("c/d")

    summary = session.summary()
    assert "alice" in summary
    assert "Total:   2" in summary
    assert "Starred: 1" in summary
    assert "Failed:  1" in summary
