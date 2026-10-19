import json
from typing import TypeGuard

from fastmcp import Client
from fastmcp.client.client import CallToolResult

from getting_started_mcp import config

# GitHub reports each result's repository as an API URL; strip this to "owner/repo".
_REPO_URL_PREFIX = "https://api.github.com/repos/"


async def fetch_pull_requests(token: str, *, limit: int = 50) -> list[dict]:
    """Return the caller's open pull requests, newest activity first.

    The token is spent on GitHub's hosted MCP server. `search_pull_requests`
    with `author:@me` scopes the search to the person the token was issued for.
    """
    async with Client(config.GITHUB_MCP, auth=token) as client:
        result = await client.call_tool(
            "search_pull_requests",
            {
                "query": "is:open author:@me",
                "sort": "updated",
                "order": "desc",
                "perPage": limit,
            },
        )

    return [_pull_request(pr) for pr in _rows(result)]


def _rows(result: CallToolResult) -> list:
    """Pull the pull-request rows out of whichever shape GitHub sent back.

    The hosted server returns the JSON as a text content block. Structured
    output, when present, is the same object.
    """
    for candidate in (result.data, result.structured_content, *_text_payloads(result)):
        found = _pr_rows(candidate)
        if found is not None:
            return found

    raise RuntimeError("GitHub search_pull_requests returned no pull requests list")


def _text_payloads(result: CallToolResult) -> list:
    payloads = []
    for block in result.content:
        text = getattr(block, "text", None)
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            payloads.append(json.loads(text))
        except json.JSONDecodeError:
            continue
    return payloads


def _pr_rows(value: object) -> list | None:
    mapping = _mapping(value)
    if mapping is not None:
        for key in ("items", "pull_requests", "pullRequests", "results"):
            rows = mapping.get(key)
            if _is_row_list(rows):
                return rows
        nested = mapping.get("result")
        if nested is not None:
            return _pr_rows(nested)
        return None
    if _is_row_list(value):
        return value
    return None


def _is_row_list(value: object) -> TypeGuard[list]:
    return isinstance(value, list) and all(isinstance(row, dict) for row in value)


def _mapping(value: object) -> dict | None:
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        dumped = dump()
        if isinstance(dumped, dict):
            return dumped
    return None


def _pull_request(pr: dict) -> dict:
    return {
        "repository": _repository(pr),
        "number": pr.get("number"),
        "title": pr.get("title"),
        "url": pr.get("html_url") or pr.get("url"),
    }


def _repository(pr: dict) -> str | None:
    repo_url = pr.get("repository_url")
    if isinstance(repo_url, str):
        return repo_url.removeprefix(_REPO_URL_PREFIX)
    repository = pr.get("repository")
    if isinstance(repository, dict):
        name = repository.get("full_name") or repository.get("name")
        return name if isinstance(name, str) else None
    repo = pr.get("repo")
    return repo if isinstance(repo, str) else None
