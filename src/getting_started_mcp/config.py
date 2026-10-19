import os

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    """Read a required environment variable, failing loudly when it is unset."""
    if value := os.getenv(name):
        return value

    raise RuntimeError(
        f"{name} is not set. Copy your zone URL from the Keycard dashboard "
        f"and export it, for example: export {name}=https://your-zone-id.keycard.cloud"
    )


def _flag(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _zone_url() -> str:
    """Resolve the zone URL, accepting the deprecated zone-id form."""
    if url := os.getenv("KEYCARD_ZONE_URL"):
        return url.rstrip("/")

    # KEYCARD_ZONE_ID is deprecated upstream. Resolving it here and passing
    # zone_url= to AuthProvider keeps the SDK from warning a second time.
    if zone_id := os.getenv("KEYCARD_ZONE_ID"):
        return f"https://{zone_id}.keycard.cloud"

    return _required("KEYCARD_ZONE_URL")


# The Keycard zone this server authenticates against.
ZONE_URL = _zone_url()

# The zone's OpenID Connect UserInfo endpoint, which is what `whoami` reads.
# `keycard new mcp` adds it as a dependency of the application. The path is
# standard across zones; identity.py checks it against discovery at startup.
USERINFO_RESOURCE = os.getenv(
    "KEYCARD_USERINFO_RESOURCE", f"{ZONE_URL}/openid/connect/userinfo"
)

# GitHub's hosted MCP server. Keycard issues a token for this resource, and
# list_pull_requests spends it by calling search_pull_requests on the same
# server. It must match the identifier of the GitHub MCP dependency in the zone.
GITHUB_MCP = os.getenv(
    "KEYCARD_GITHUB_MCP_RESOURCE", "https://api.githubcopilot.com/mcp/"
)

# Linear's hosted MCP server. Keycard issues a token for this resource, and
# list_tickets spends it by calling list_issues on the same server. It must
# match the identifier of the Linear dependency in the zone.
LINEAR_RESOURCE = os.getenv("KEYCARD_LINEAR_RESOURCE", "https://mcp.linear.app/mcp")

# Port the HTTP transport binds to.
PORT = int(os.getenv("PORT", "8181"))

# Address the HTTP transport binds to.
HOST = os.getenv("HOST", "127.0.0.1")


def _server_url() -> str:
    """Resolve the public URL callers reach this server at.

    Keycard uses it as the resource id, and the server hands it to clients in
    the OAuth `resource_metadata` challenge, so it has to be the address the
    caller can actually reach. Prefer an explicit MCP_SERVER_URL. On Vercel,
    fall back to the project's stable production domain so a deploy works
    without setting anything (VERCEL_PROJECT_PRODUCTION_URL has no scheme, and
    is stable across deploys, unlike the per-deploy VERCEL_URL). Locally, fall
    back to localhost.
    """
    if url := os.getenv("MCP_SERVER_URL"):
        return url
    if host := os.getenv("VERCEL_PROJECT_PRODUCTION_URL"):
        return f"https://{host}/mcp"
    return f"http://localhost:{PORT}/mcp"


# Public URL callers reach this server at; Keycard uses it as the resource id.
SERVER_URL = _server_url()

# Whether the application announces itself at startup. On by default locally,
# off on Vercel, where it would run on every cold start.
STARTUP_IDENTITY_CHECK = _flag(
    "KEYCARD_STARTUP_IDENTITY_CHECK", default=not os.getenv("VERCEL")
)
