# Getting Started MCP

MCP server that reads GitHub on your behalf using short-lived tokens from Keycard for each call.

Run it locally, connect Claude Code, and reads will appear in the Keycard console under your name.

## What the MCP tools show you

`whoami` answers as you, reading claims from your Keycard zone. At startup the server authenticates as _itself_ with the credential in `.env` and reads the claims of the token Keycard issues it. That issuance appears in the Keycard console with the application as the subject, rather than you.

`list_pull_requests` returns your open pull requests. The server asks Keycard for a token scoped to you, spends it on GitHub's hosted MCP server, and discards it. This call appears in the Keycard console with you as the subject, rather than the application.

## Prerequisites

You need Python 3.12 or later, [uv](https://docs.astral.sh/uv/), and a Keycard account.

## Quickstart

1. Clone the project and move into it.

   ```bash
   git clone https://github.com/keycardai/getting-started-mcp local-tools
   cd local-tools
   ```

2. Install the Keycard CLI and enroll the project.

   ```bash
   brew install keycardai/tap/keycard
   keycard new mcp
   ```

   `keycard new mcp` creates the `local-tools` application in your zone, mints a credential for local development, and writes `.env`.

3. Install dependencies and start the server.

   ```bash
   make install
   make dev
   ```

   The server listens on `http://localhost:8181/mcp`. Open Activity in the Keycard console and you'll see the startup `whoami` call attributed to `local-tools`.

4. Add GitHub as a dependency of the application.

   In the console: go to Dependencies, choose Add Dependency, then Add Resource, and pick GitHub MCP. Keycard walks you through connecting GitHub and then holds tokens for you.

5. Connect Claude Code.

   ```bash
   claude mcp add --transport http --scope local local-tools http://localhost:8181/mcp
   claude
   ```

6. Ask Claude Code to list open pull requests. You sign in, consent to using GitHub, and the read comes back. Activity records the grant and the read with you as the subject.

## How the authorization works

Two exchanges, and neither one puts a GitHub credential in this repository.

At startup the server authenticates to your Keycard zone with its own client ID and secret from `.env`, a plain OAuth client credentials grant, and reads the claims of the token it is issued. UserInfo is a user endpoint and does not accept an application as its subject, so the server shows its own token rather than calling UserInfo as itself.

To list pull requests the server hands the caller's token to Keycard using RFC 8693 token exchange to get back a token scoped to the request. Keycard decides whether to issue the token by ensuring the resource is a dependency of the application and that you consented to the use. The token comes back scoped to one resource and the server throws it away after the call.

So `.env` holds exactly one secret: the application's own. GitHub's credential lives in Keycard, and nothing in this project can read it.

## Configuration

Every value comes from `.env`, which is written by `keycard new mcp` and loaded at startup.

| Variable                         | What it does                                               | Default                     |
| -------------------------------- | ---------------------------------------------------------- | --------------------------- |
| `KEYCARD_ZONE_URL`               | Your Keycard zone. Required.                               | none                        |
| `KEYCARD_CLIENT_ID`              | The application's client ID, written by `keycard new mcp`. | none                        |
| `KEYCARD_CLIENT_SECRET`          | Its secret, written by `keycard new mcp`.                  | none                        |
| `MCP_SERVER_URL`                 | The URL Keycard knows this server by.                      | `http://localhost:8181/mcp` |
| `PORT`                           | Port the HTTP transport binds to.                          | `8181`                      |
| `HOST`                           | Address it binds to.                                       | `127.0.0.1`                 |
| `KEYCARD_USERINFO_RESOURCE`      | Override the UserInfo endpoint.                            | derived from the zone URL   |
| `KEYCARD_STARTUP_IDENTITY_CHECK` | Whether to announce the application at startup.            | on locally, off on Vercel   |

The server runs without `KEYCARD_CLIENT_ID` and `KEYCARD_CLIENT_SECRET`, so you can start it before you enroll. It logs a warning and skips the startup call.

On Vercel the server does not announce itself, which is why `KEYCARD_STARTUP_IDENTITY_CHECK` stays off there. The platform's OIDC token arrives per request (`x-vercel-oidc-token`) rather than with the process, so a startup hook has nothing to present. The deployed server uses that token to authenticate each tool call's token exchange, and the deployment shows up in Activity through the first real call.

## Commands

Run `make` to see the list.

| Command          | What it does                                     |
| ---------------- | ------------------------------------------------ |
| `make install`   | Install dependencies.                            |
| `make dev`       | Run the server with debug logging.               |
| `make run`       | Run the server.                                  |
| `make typecheck` | Type-check the source.                           |
| `make env-push`  | Push selected `.env` keys to the Vercel project. |
| `make env-pull`  | Pull the Vercel environment into `.env.local`.   |
| `make env-list`  | List the environment set on the Vercel project.  |

`make env-push` sends `KEYCARD_ZONE_URL` from `.env` to the linked Vercel project. It does not send `KEYCARD_CLIENT_ID` or `KEYCARD_CLIENT_SECRET`. The deployed server authenticates with Vercel's workload identity. Redeploy after it runs.

## Project layout

| Path                                  | Holds                                                                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `src/getting_started_mcp/server.py`   | Tool definitions, the startup hook, and the entry point.                                                           |
| `src/getting_started_mcp/github.py`   | GitHub MCP calls. Takes a token, knows nothing about Keycard.                                                      |
| `src/getting_started_mcp/identity.py` | Identity reads: your UserInfo answer (the `whoami` tool) and the application's own issued-token claims at startup. |
| `src/getting_started_mcp/config.py`   | Environment-derived settings.                                                                                      |
| `scripts/env-push.sh`                 | The `make env-push` implementation.                                                                                |

## Deploying

We're still building the Vercel path, and the production credential handling remains unfinished. Run `vercel deploy`, then give the console your Vercel team slug, project name, and the deployed URL. Keycard creates a provider for your team, registers the deployed endpoint, and issues a workload identity credential keyed to it.

The deployed server holds no secret at all. Vercel mints a short-lived OIDC token for every function invocation, Keycard trusts your team's issuer, and the exchange happens against that. The client ID and secret in `.env` stay local.

The deployed server does not announce an identity of its own. Each tool call authenticates its token exchange with the workload identity, so the deployment shows up on the Activity feed through the first real call rather than through a separate self-issued announcement.

## Troubleshooting

If startup fails with `KEYCARD_ZONE_URL is not set`, you haven't run `keycard new mcp` yet.

If the log says no application credential was found, you haven't run `keycard new mcp` yet. The server still serves; only the startup identity call is skipped.

If a GitHub tool returns a token exchange error, GitHub isn't a dependency of the application yet, or you haven't consented to this agent using it. Both are fixed in the console under Dependencies.

If your agent can't connect, check that `MCP_SERVER_URL` matches the URL you gave it, including the `/mcp` path. Keycard pins the token audience to that value, so a mismatch shows up as a rejected token.

## License

Apache-2.0 — see [LICENSE](./LICENSE) and, for the copyright notice,
[NOTICE](./NOTICE). The Keycard name and logo are trademarks;
[TRADEMARKS.md](./TRADEMARKS.md) states how they may be used.
