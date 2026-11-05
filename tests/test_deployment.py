import importlib
import os
import unittest
from unittest.mock import patch

with (
    patch.dict(
        os.environ, {"KEYCARD_ZONE_URL": "https://zone.example.com"}, clear=True
    ),
    patch("dotenv.load_dotenv"),
    patch(
        "keycardai.fastmcp.AuthProvider._discover_jwks_uri",
        return_value="https://zone.example.com/jwks",
    ),
):
    from getting_started_mcp import config, server


class DeploymentTest(unittest.TestCase):
    def test_fly_url(self):
        with patch.dict(os.environ, {"FLY_APP_NAME": "local-tools"}, clear=True):
            self.assertEqual(config._server_url(), "https://local-tools.fly.dev/mcp")

    def test_explicit_url_wins(self):
        with patch.dict(
            os.environ,
            {
                "FLY_APP_NAME": "local-tools",
                "MCP_SERVER_URL": "https://tools.example.com/mcp",
            },
            clear=True,
        ):
            self.assertEqual(config._server_url(), "https://tools.example.com/mcp")

    def test_vercel_url_unchanged(self):
        with patch.dict(
            os.environ,
            {"VERCEL_PROJECT_PRODUCTION_URL": "tools.vercel.app"},
            clear=True,
        ):
            self.assertEqual(config._server_url(), "https://tools.vercel.app/mcp")

    def test_local_credential_unchanged(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(server._application_credential())

    def test_fly_uses_runtime_token_source(self):
        with (
            patch.dict(os.environ, {"FLY_APP_NAME": "local-tools"}, clear=True),
            patch.object(server, "FlyTokenSource") as source,
            patch.object(server, "WorkloadIdentity") as credential,
        ):
            self.assertIs(server._application_credential(), credential.return_value)
            source.assert_called_once_with(audience=config.ZONE_URL)
            credential.assert_called_once_with(source.return_value, client_id=None)

    def test_vercel_uses_invocation_token(self):
        with (
            patch.dict(os.environ, {"VERCEL": "1"}, clear=True),
            patch.object(server, "WorkloadIdentity") as credential,
        ):
            server._application_credential()
            credential.assert_called_once_with(
                server._vercel_oidc_token, client_id=None
            )

    def test_deployed_startup_does_not_require_registration(self):
        for marker in ("FLY_APP_NAME", "VERCEL"):
            with (
                self.subTest(marker=marker),
                patch.dict(
                    os.environ,
                    {
                        "KEYCARD_ZONE_URL": "https://zone.example.com",
                        marker: "1",
                    },
                    clear=True,
                ),
                patch("dotenv.load_dotenv"),
            ):
                importlib.reload(config)
                self.assertFalse(config.STARTUP_IDENTITY_CHECK)


if __name__ == "__main__":
    unittest.main()
