FROM python:3.12.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.11.13 && uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY contracts ./contracts
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --uid 10001 --create-home runtime
USER 10001:10001
CMD ["uvicorn", "rah.gateway:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM python:3.12.12-slim-bookworm AS sandbox
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY src/rah/__init__.py src/rah/worker.py /opt/rah/
ENV PYTHONPATH=/opt
USER 10001:10001
WORKDIR /work
CMD ["python", "-c", "import time; time.sleep(86400)"]
