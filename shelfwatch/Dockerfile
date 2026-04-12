FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app

# Install matval_core first (shared dependency)
COPY matval_core/ /app/matval_core/
RUN uv pip install --system --no-cache /app/matval_core/

# Install shelfwatch
COPY shelfwatch/ /app/shelfwatch/
ENV UV_NO_SOURCES=1
RUN uv pip install --system --no-cache /app/shelfwatch/

CMD ["shelfwatch"]
