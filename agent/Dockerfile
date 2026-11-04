FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.12.17

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 app

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

COPY main.py graph.py schemas.py entrypoint.sh ./
COPY rag/ ./rag/

RUN chmod +x entrypoint.sh && chown -R app:app /app

USER app

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["./entrypoint.sh"]
