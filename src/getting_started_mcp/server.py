import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from keycardai.fastmcp import AccessContext, AuthProvider
from keycardai.oauth.server import WorkloadIdentity

from getting_started_mcp import config, github, identity, linear

logger = logging.getLogger(__name__)

# Header Vercel sets on every Function request carrying the invocation's
# short-lived OIDC token. This is the token's primary delivery mechanism at
# runtime; the VERCEL_OIDC_TOKEN env var is populated in builds and local dev.
_VERCEL_OIDC_HEADER = "x-vercel-oidc-token"

# Track which token sources we've already logged, so a busy server logs the
# resolved source once rather than on every exchange.
_logged_token_sources: set[str] = set()


def _log_token_source(source: str) -> None:
    if source not in _logged_token_sources:
        _logged_token_sources.add(source)
        logger.info("Resolved Vercel OIDC token from %s", source)


def _vercel_oidc_token() -> str:
    """Fetch Vercel's current workload-identity OIDC token for a token exchange.

    Resolved fresh on every exchange because Vercel rotates the token. Checks,
    in order:
      1. the per-invocation x-vercel-oidc-token request header, which is how
         Vercel delivers the token to Functions at runtime,
      2. VERCEL_OIDC_TOKEN_FILE, if the platform projects a rotating file,
      3. the VERCEL_OIDC_TOKEN environment variable (builds and local dev).
    """
    if token := get_http_headers(include_all=True).get(_VERCEL_OIDC_HEADER):
        _log_token_source("request header")
        return token

    if path := os.getenv("VERCEL_OIDC_TOKEN_FILE"):
        with open(path) as f:
            if token := f.read().strip():
                _log_token_source("VERCEL_OIDC_TOKEN_FILE")
                return token

    if token := os.getenv("VERCEL_OIDC_TOKEN"):
        _log_token_source("VERCEL_OIDC_TOKEN env var")
        return token

    raise RuntimeError(
        "No Vercel OIDC token found; checked the x-vercel-oidc-token header, "
        "VERCEL_OIDC_TOKEN_FILE, and VERCEL_OIDC_TOKEN. Confirm OIDC federation "
        "is enabled for this project."
    )


def _application_credential() -> WorkloadIdentity | None:
    """How the deployed server authenticates its own token exchanges.

    On Vercel, authenticate with the platform's workload identity: Vercel mints
    a short-lived OIDC token per invocation, which we hand to Keycard as a
    jwt-bearer client assertion (see _vercel_oidc_token for how it is sourced).
    No client secret is deployed.

    The decision keys off the VERCEL marker, not the token's presence, so the
    source is resolved per exchange rather than frozen at import. Returns None
    off Vercel, so AuthProvider falls back to discovering
    KEYCARD_CLIENT_ID/KEYCARD_CLIENT_SECRET from the environment for local runs.

    Requires Vercel's OIDC federation to be enabled for the project. The
    KEYCARD_CLIENT_ID is only needed when the zone resolves the application by a
    token-federation rule; it is a client identifier, not a secret, and is
    omitted when unset.
    """
    if not os.getenv("VERCEL"):
        return None

    return WorkloadIdentity(
        _vercel_oidc_token,
        client_id=os.getenv("KEYCARD_CLIENT_ID"),
    )


keycard = AuthProvider(
    zone_url=config.ZONE_URL,
    mcp_server_name="Getting Started MCP",
    mcp_server_url=config.SERVER_URL,
    application_credential=_application_credential(),
)


@asynccontextmanager
async def lifespan(_: FastMCP) -> AsyncIterator[dict]:
    """Announce the application's own identity before serving any traffic."""
    if config.STARTUP_IDENTITY_CHECK:
        await identity.announce_app_identity(keycard)
    yield {}


mcp = FastMCP(
    "Getting Started MCP",
    auth=keycard.get_remote_auth_provider(),
    lifespan=lifespan,
)


@mcp.tool
@keycard.grant(config.USERINFO_RESOURCE)
async def whoami(access: AccessContext) -> dict:
    """Return your Keycard identity, read from the zone as you."""
    if access.has_errors():
        raise ToolError(
            f"Keycard could not issue a token for {config.USERINFO_RESOURCE}: "
            f"{access.get_errors()}. Check that it is a dependency of this "
            "application in the console."
        )

    token = access.access(config.USERINFO_RESOURCE).access_token
    return await identity.fetch_caller_identity(keycard, token)


@mcp.tool
@keycard.grant(config.GITHUB_MCP)
async def list_pull_requests(access: AccessContext) -> dict:
    """List your open pull requests across GitHub."""
    if access.has_errors():
        raise ToolError(
            f"Keycard could not issue a token for {config.GITHUB_MCP}: "
            f"{access.get_errors()}. Check that it is a dependency of this "
            "application in the console."
        )

    token = access.access(config.GITHUB_MCP).access_token
    return {"pull_requests": await github.fetch_pull_requests(token)}


@mcp.tool
@keycard.grant(config.LINEAR_RESOURCE)
async def list_tickets(access: AccessContext) -> dict:
    """List your assigned Linear tickets."""
    if access.has_errors():
        raise ToolError(
            f"Keycard could not issue a token for {config.LINEAR_RESOURCE}: "
            f"{access.get_errors()}. Check that it is a dependency of this "
            "application in the console."
        )

    token = access.access(config.LINEAR_RESOURCE).access_token
    return {"tickets": await linear.fetch_issues(token)}


def main() -> None:
    """Entry point for `uv run getting-started-mcp`."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(name)s: %(message)s",
    )

    mcp.run(transport="http", host=config.HOST, port=config.PORT)


app = mcp.http_app()
