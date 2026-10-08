# emendrix-mcp: two-stage build, non-root runtime, the MCP server and its dependencies only.
#
# Built from the repository root, because the lockfile the image is built against is the
# workspace's:
#
#   docker build -f packages/emendrix-mcp/Dockerfile -t ghcr.io/emendrix/emendrix-mcp:main .
#   docker run --rm -e EMENDRIX_MCP_CHANGELOGS=/srv/changelogs \
#     -e EMENDRIX_MCP_ALLOWED_HOSTS=mcp.example.org -v <a changelogs clone>:/srv/changelogs:ro \
#     -p 8000:8000 ghcr.io/emendrix/emendrix-mcp:main
#
# Configured only through `EMENDRIX_MCP_*` variables (or the flags of the same name); `--help`
# lists them. The image holds no host, no address and no data: it reads a changelogs repository
# and a site's catalogue from directories mounted into it, read-only.
#
# It carries no `emendrix`. Only the member and its own dependencies are installed, so the
# server cannot import the pipeline's model stage, and the published workflow's smoke step
# checks that `import emendrix` fails inside it.
#
# Base images are pinned by manifest-list digest for the reason `deploy/Dockerfile` gives: a tag
# moves, a platform digest pulls only on the platform it was resolved on, and this image is built
# on arm64 workstations and an amd64 runner alike. They are that file's bases, so the two images
# move together; re-resolve both files when either is bumped. Unlike that image this one needs no
# `git`: it reads committed files and never commits.

FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS build

COPY --from=ghcr.io/astral-sh/uv:0.8.13@sha256:4de5495181a281bc744845b9579acf7b221d6791f99bcc211b9ec13f417c2853 /uv /uvx /bin/

# Built at its final path: a venv moved between stages keeps absolute paths into the stage it
# was built in, which shows only at run time.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src

# The workspace root's pyproject and lockfile name the member and pin its dependencies; the
# pipeline's sources are not copied, so nothing of it can be installed by mistake. `--frozen`
# fails rather than resolving, so the image ships the dependency set CI tested.
COPY pyproject.toml uv.lock ./
COPY packages/emendrix-mcp ./packages/emendrix-mcp
RUN uv sync --frozen --package emendrix-mcp --no-dev --no-editable


FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime

RUN useradd --create-home --uid 10001 emendrix

COPY --from=build --chown=root:root /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/emendrix

USER emendrix
WORKDIR /home/emendrix

# Set by the caller, as for the main image: an unlabelled build says `dev` rather than a number.
ARG VERSION=dev

LABEL org.opencontainers.image.title="emendrix-mcp" \
      org.opencontainers.image.description="A read-only MCP server over a published emendrix changelogs repository." \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="MIT"

EXPOSE 8000

ENTRYPOINT ["python", "-m", "emendrix_mcp"]
