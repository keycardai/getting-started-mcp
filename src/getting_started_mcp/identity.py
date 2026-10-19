import logging

import anyio
from keycardai.oauth.utils.jwt import extract_scopes, get_claims

from getting_started_mcp import config

logger = logging.getLogger(__name__)


async def fetch_caller_identity(keycard, token: str) -> dict:
    """Return the identity claims of the caller the token was issued for."""
    info = await keycard.client.userinfo(token)
    return {"sub": info.sub, "claims": info.claims}


async def announce_app_identity(keycard, *, timeout: float = 5.0) -> dict | None:
    """Show the application's own identity, so Activity records the boot.

    The application authenticates as itself (a client-credentials grant) and
    reads the claims of the token Keycard issues it: its subject, the issuing
    zone, the audience, and when it expires. That issuance is the thing you
    watch in Activity, attributed to the application.

    UserInfo is deliberately not called here: it is a user endpoint and does
    not accept an application as its subject, so the honest "as myself" answer
    is the token the app was just handed, not a UserInfo response.
    """
    if keycard.application_credential is None:
        logger.warning(
            "No application credential found, so this server is starting without "
            "an identity of its own. Run `keycard new mcp` to create one."
        )
        return None

    try:
        with anyio.fail_after(timeout):
            # `resource` is only the audience the app's token is scoped to; the
            # UserInfo URL is a convenient, always-present one. We never call it.
            token = await keycard.client.client_credentials_grant(
                resource=config.USERINFO_RESOURCE, scope="openid"
            )
    except Exception as error:
        logger.warning(
            "Could not obtain the application's own token: %s. The server is "
            "still serving; tool calls are unaffected.",
            error,
        )
        return None

    try:
        claims = get_claims(token.access_token)
    except ValueError:
        # An opaque (non-JWT) token has no readable claims; the issuance still
        # happened and is on record under Activity.
        claims = {}

    identity = {
        "sub": claims.get("sub"),
        "issuer": claims.get("iss"),
        "audience": claims.get("aud"),
        "expires_at": claims.get("exp"),
        "scopes": extract_scopes(claims),
    }
    logger.info(
        "Keycard issued %s a token as itself. The issuance is on record under "
        "Activity in the Keycard console.",
        identity["sub"] or "this application",
    )
    return identity
