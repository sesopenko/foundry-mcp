FROM ghcr.io/astral-sh/uv:0.9.16@sha256:ae9ff79d095a61faf534a882ad6378e8159d2ce322691153d68d2afac7422840 AS uv
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS runtime
ARG VERSION=1.4.0
ARG REVISION=unknown
ARG RELEASE_TAG=
LABEL org.opencontainers.image.title="Foundry MCP" \
      org.opencontainers.image.source="https://github.com/sesopenko/foundry-mcp" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION
RUN groupadd --gid 10001 bridge && useradd --uid 10001 --gid bridge --no-create-home bridge
RUN mkdir -p /data/pdf-library /data/pdf-state && chown -R 10001:10001 /data && chmod 700 /data/pdf-library /data/pdf-state
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY foundry_mcp_server/ ./foundry_mcp_server/
COPY LICENSE.txt ./LICENSE.txt
RUN .venv/bin/python -m foundry_mcp_server.build_info --version "$VERSION" --release-tag "$RELEASE_TAG" --revision "$REVISION"
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    FOUNDRY_MCP_HOST=0.0.0.0 FOUNDRY_MCP_PORT=8000 FOUNDRY_MCP_DEV_EXECUTION=false
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
    CMD ["python", "-m", "foundry_mcp_server.healthcheck"]
CMD ["python", "-m", "foundry_mcp_server.main"]
