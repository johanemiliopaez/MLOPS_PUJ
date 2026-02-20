# Dockerfile para FastAPI - Despliegue de modelos
FROM python:3.12-slim-bookworm

# Instalar UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Instalar dependencias requeridas por Setup/API/main.py y Setup/Model/train.py usando UV
COPY Setup/pyproject.toml /tmp/pyproject.toml
RUN uv pip install --system -r /tmp/pyproject.toml

# Copiar código de la API real
COPY Setup/API/ /app/

# Puerto FastAPI
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
