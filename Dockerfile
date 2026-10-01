# The tutor web app (v2/tutor/web.py). Dokku builds this and routes the app's domain to $PORT.
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 PORT=5000
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY v2/build.py v2/vocabulary.json v2/extraction.json v2/
COPY v2/questions v2/questions
COPY v2/word-problems v2/word-problems
COPY v2/trees v2/trees
COPY v2/tutor v2/tutor
WORKDIR /app/v2
EXPOSE 5000
CMD ["sh", "-c", "/app/.venv/bin/uvicorn tutor.web:app --host 0.0.0.0 --port ${PORT:-5000} --proxy-headers --forwarded-allow-ips='*'"]
