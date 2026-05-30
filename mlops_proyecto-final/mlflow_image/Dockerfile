FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalamos MLflow COMPLETO en tiempo de construcción
RUN pip install --no-cache-dir mlflow==2.11.3 psycopg2-binary boto3

EXPOSE 5000

CMD ["mlflow", "server", "--host", "0.0.0.0"]