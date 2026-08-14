# emendrix: two-stage build, non-root runtime, no build tooling in the shipped image.
#
# Two entrypoints, both of them the shipped CLI (there is no second program):
#
#   docker run --rm ghcr.io/emendrix/emendrix:0.1.0 run --once  # the poller: cron, systemd, K8s
#   docker run --rm ghcr.io/emendrix/emendrix:0.1.0 site build --out …   # the static site
#
# That is the name `deploy/compose.yaml` runs, so a build tagged with it serves both.
#
# Base images are pinned by digest, not merely by tag. A tag moves under you, so two builds of
# the same commit can ship different bases and only one of them is the one that was tested. Each
# `@sha256:` below is the *manifest list* digest (an OCI image index), resolved on 2026-08-09
# with `docker buildx imagetools inspect`. That matters: a platform-specific digest would pull
# on the machine it was resolved on and fail everywhere else, and this image is built on both
# arm64 workstations and an amd64 CI runner. The tag is kept in front of the digest for a human
# reader; docker honours the digest and ignores the tag. Re-resolve all three when a base is
# deliberately bumped, and say so in the commit.
#
# `git` is installed in the runtime stage on purpose: the changelog writer shells out to it to
# commit into the output repository, and it is the only executable outside the interpreter this
# tool needs.

FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS build

# uv itself, from the image its authors publish, pinned to the version this repo develops on.
COPY --from=ghcr.io/astral-sh/uv:0.8.13@sha256:4de5495181a281bc744845b9579acf7b221d6791f99bcc211b9ec13f417c2853 /uv /uvx /bin/

# The environment is built at its *final* path, not moved into place afterwards: a console
# script's shebang is an absolute path, so a venv relocated between stages produces
# `exec /app/.venv/bin/emendrix: no such file or directory` at run time and nowhere earlier.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /src

# The lockfile is the build input: `--frozen` fails rather than resolving, so an image cannot
# quietly ship a different dependency set from the one CI tested.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable


FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 emendrix

COPY --from=build --chown=root:root /app/.venv /app/.venv

# The committed evaluation reports travel with the image so `site build` can publish measured
# numbers without a checkout mounted. They are read-only artifacts, owned by root, and the
# runtime user cannot rewrite them: a published figure may not be editable by the process that
# publishes it.
COPY --chown=root:root reports /app/reports
COPY --chown=root:root watchlist.example.toml /app/watchlist.example.toml

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/emendrix

# Every path a volume will be mounted at is created here, owned by the runtime user. Docker
# seeds a named volume from whatever is *already* at that path in the image, and when nothing
# is, it fabricates an empty directory owned by `root:root` whatever `USER` says. A non-root
# image with volumes and no such directories therefore fails on its very first run, on all four
# of them at once: the output git repository, the response cache, the watch cursor and the
# generated site. The paths are `deploy/compose.yaml`'s; the two must stay in step.
RUN mkdir -p /work/changelogs /work/site /home/emendrix/.cache /home/emendrix/.local/share \
    && chown -R emendrix:emendrix /work /home/emendrix

USER emendrix
WORKDIR /work

# What the version label says is decided by the caller, because only the caller knows. A
# hardcoded version is the first thing to rot: it keeps reading `0.1.0` through every release
# after it, and this label is precisely what someone reads to answer "what is this image". The
# default is `dev` rather than a version number so that an unlabelled build is honest about
# being unlabelled. Builds that mean something pass one:
#
#   docker build -f deploy/Dockerfile --build-arg VERSION=$(git describe --tags --always) .
#
# ARG must be re-declared inside the stage that consumes it; one before the first FROM would be
# out of scope here.
ARG VERSION=dev

LABEL org.opencontainers.image.title="emendrix" \
      org.opencontainers.image.description="A regulatory change engine: watch EU legislation, diff it provision by provision, explain what changed." \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="MIT"

ENTRYPOINT ["emendrix"]
CMD ["--help"]
