# Proyecto 2 - MLOps en Kubernetes

Base de trabajo para el proyecto de MLOps del curso, diseñada desde el inicio para ejecutarse en Kubernetes.

## Componentes

- `postgres`: almacenamiento para `raw_data`, `clean_data`, `inference_logs`, metadata de MLflow y metadata de Airflow.
- `minio`: artifact store compatible con S3.
- `mlflow`: tracking server y model registry.
- `airflow`: orquesta ingesta incremental, limpieza, entrenamiento y promoción del mejor modelo.
- `api`: FastAPI para inferencia, logging de predicciones y exposición de métricas Prometheus.
- `streamlit`: interfaz para consumir la API.
- `locust`: pruebas de carga sobre la API.
- `prometheus` y `grafana`: observabilidad.

## Estructura

```text
Proyecto 2/
├── api/
├── airflow/
├── k8s/
├── locust/
├── mlflow/
├── sql/
├── streamlit/
└── training/
```

## Flujo funcional

1. Airflow descarga o valida el dataset.
2. Inserta un lote incremental en `raw_data`.
3. Construye la capa `clean_data`.
4. Entrena varios modelos y registra los experimentos en MLflow.
5. Promueve el mejor modelo como `champion` o `Production`.
6. La API consume dinámicamente ese modelo desde MLflow.
7. Cada inferencia queda registrada en `inference_logs`.
8. Prometheus recolecta `/metrics`, Grafana visualiza y Locust genera carga.

## Imágenes a construir

Desde la carpeta `Proyecto 2`:

```bash
docker build -f mlflow/Dockerfile -t innovacion/proyecto2-mlflow:latest .
docker build -f api/Dockerfile -t innovacion/proyecto2-api:latest .
docker build -f streamlit/Dockerfile -t innovacion/proyecto2-streamlit:latest .
docker build -f airflow/Dockerfile -t innovacion/proyecto2-airflow:latest .
docker build -f locust/Dockerfile -t innovacion/proyecto2-locust:latest .
```

Luego publica las imágenes:

```bash
docker push innovacion/proyecto2-mlflow:latest
docker push innovacion/proyecto2-api:latest
docker push innovacion/proyecto2-streamlit:latest
docker push innovacion/proyecto2-airflow:latest
docker push innovacion/proyecto2-locust:latest
```

## Despliegue en Kubernetes

Aplica los recursos:

```bash
kubectl apply -k k8s
```

Revisa el estado:

```bash
kubectl get pods -n mlops-proyecto2
kubectl get svc -n mlops-proyecto2
```

## Acceso local recomendado

```bash
kubectl port-forward svc/airflow-webserver -n mlops-proyecto2 8080:8080
kubectl port-forward svc/mlflow -n mlops-proyecto2 5000:5000
kubectl port-forward svc/streamlit -n mlops-proyecto2 8501:8501
kubectl port-forward svc/grafana -n mlops-proyecto2 3000:3000
kubectl port-forward svc/locust -n mlops-proyecto2 8089:8089
```

## Qué hace cada componente nuevo

### `training/src/pipeline.py`

- Gestiona la ingesta incremental del CSV.
- Guarda registros crudos en `raw_data` con `row_hash`.
- Construye `clean_data` con `features` y `target_value`.
- Entrena `LogisticRegression` y `RandomForest`.
- Registra métricas y modelo en MLflow.
- Promueve automáticamente el mejor modelo según `val_recall`.

### `airflow/dags/mlops_diabetes_pipeline.py`

Define el DAG principal con tareas:

1. `validate_source_file`
2. `ingest_batch`
3. `validate_batch`
4. `transform_and_clean`
5. `train_and_promote`

### `api/app/main.py`

- Endpoints obligatorios:
  - `/health`
  - `/predict`
  - `/model-info`
  - `/metrics`
- Carga el modelo productivo desde MLflow.
- Registra cada inferencia en PostgreSQL.
- Expone métricas para Prometheus.

## Variables importantes

Las principales están en `.env.example`:

- `DATASET_URL`
- `DATASET_PATH`
- `TARGET_COLUMN`
- `BATCH_SIZE`
- `MLFLOW_MODEL_NAME`
- `MLFLOW_MODEL_ALIAS`

## Restricciones ya cubiertas en esta base

- Todo el flujo está pensado para Kubernetes.
- Airflow usa Postgres externo, no SQLite.
- MLflow usa Postgres + MinIO.
- La API no depende de un archivo local de modelo.
- Hay `requests` y `limits` en los despliegues.
- Se incluyen `raw_data`, `clean_data` e `inference_logs`.
- Se deja observabilidad con Prometheus y Grafana.
- Locust queda desplegado como componente del clúster.

## Pendientes naturales para completar la entrega

- Probar el dataset modificado real y refinar `TARGET_COLUMN` o columnas preferidas.
- Exportar un dashboard final de Grafana tras la prueba de carga.
- Afinar recursos y número de réplicas según el clúster local.
