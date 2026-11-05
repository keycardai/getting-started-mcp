FROM ghcr.io/astral-sh/uv:0.9.5 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE NOTICE ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV HOST=0.0.0.0 PORT=8181
EXPOSE 8181
CMD [".venv/bin/getting-started-mcp"]
