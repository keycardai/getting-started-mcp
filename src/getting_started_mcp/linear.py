import json
from typing import TypeGuard

from fastmcp import Client
from fastmcp.client.client import CallToolResult

from getting_started_mcp import config


async def fetch_issues(token: str, *, limit: int = 50) -> list[dict]:
    """Return the caller's assigned Linear issues, newest activity first.

    The token is spent on Linear's MCP server. `list_issues` treats the
    assignee `"me"` as the person that token was issued for.
    """
    async with Client(config.LINEAR_RESOURCE, auth=token) as client:
        result = await client.call_tool(
            "list_issues",
            {
                "assignee": "me",
                "orderBy": "updatedAt",
                "limit": limit,
                "fields": ["id", "title", "url", "status"],
            },
        )

    return [_ticket(issue) for issue in _issues(result)]


def _issues(result: CallToolResult) -> list:
    """Pull the issue rows out of whichever shape Linear sent back.

    The hosted server returns the JSON as a text content block. Structured
    output, when present, is the same object.
    """
    for candidate in (result.data, result.structured_content, *_text_payloads(result)):
        found = _issue_rows(candidate)
        if found is not None:
            return found

    raise RuntimeError("Linear list_issues returned no issues list")


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


def _issue_rows(value: object) -> list | None:
    mapping = _mapping(value)
    if mapping is not None:
        rows = mapping.get("issues")
        if _is_issue_list(rows):
            return rows
        nested = mapping.get("result")
        if nested is not None:
            return _issue_rows(nested)
        return None
    if _is_issue_list(value):
        return value
    return None


def _is_issue_list(value: object) -> TypeGuard[list]:
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


def _ticket(issue: dict) -> dict:
    return {
        "identifier": issue.get("identifier") or issue.get("id"),
        "title": issue.get("title"),
        "state": _state(issue),
        "url": issue.get("url"),
    }


def _state(issue: dict) -> str | None:
    status = issue.get("status", issue.get("state"))
    if isinstance(status, dict):
        name = status.get("name")
        return name if isinstance(name, str) else None
    return status if isinstance(status, str) else None
