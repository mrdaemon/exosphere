# Dockerfile for Exosphere
#
# Builds a minimal container image for running the exosphere
# cli application with Python 3.13 on Debian Bookworm
#
# This is used to provide official images for exosphere
# but can also be used locally for any purpose.
#

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
LABEL org.opencontainers.image.authors="Alexandre Gauthier <alex@lab.underwares.org>"

# Application install root
WORKDIR /opt/exosphere

# UV parameters
# We use 'copy' mode to not rely on cache at runtime
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Override configuration options for container environment
ENV EXOSPHERE_CONFIG_PATH="/data"
ENV EXOSPHERE_OPTIONS_LOG_FILE="/data/exosphere.log"
ENV EXOSPHERE_OPTIONS_CACHE_FILE="/data/exosphere.db"

# Install project dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# Copy source tree
COPY . /opt/exosphere

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Default ports and expected volumes
EXPOSE 8000
VOLUME ["/data"]

# Add venv to PATH
ENV PATH="/opt/exosphere/.venv/bin:$PATH"

# Entrypoint is the 'exosphere' command, implicitly
ENTRYPOINT ["exosphere"]