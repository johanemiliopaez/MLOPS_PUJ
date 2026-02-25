# Dockerfile para FastAPI - Taller 3 Airflow
FROM python:3.9-slim-bookworm

# Instalar UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependencias minimas para API de inferencia
RUN uv pip install --system \
    fastapi \
    uvicorn[standard] \
    pandas==1.5.3 \
    numpy==1.23.5 \
    scikit-learn==1.0.2 \
    joblib \
    dill \
    pymysql \
    sqlalchemy

# Copiar codigo de la API
COPY API/ /app/

# Puerto FastAPI
EXPOSE 8989

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8989"]
