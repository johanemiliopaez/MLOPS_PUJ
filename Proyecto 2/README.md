# Proyecto 2 — MLOps en Kubernetes (Diabetes 130-US Hospitals)

Plataforma MLOps completa desplegada en Kubernetes que cubre el ciclo de vida de un modelo de Machine Learning sobre el dataset clínico **Diabetes 130-US hospitals (1999-2008)**: ingesta incremental por lotes, almacenamiento crudo, limpieza, entrenamiento periódico, registro de experimentos, selección automática del mejor modelo, inferencia productiva, interfaz gráfica, pruebas de carga y observabilidad.

Toda la solución está pensada desde el inicio para correr en un clúster de Kubernetes (probada en `minikube`). No depende de `docker-compose` para la entrega final.

---

## Tabla de contenido

1. [Arquitectura](#arquitectura)
2. [Componentes](#componentes)
3. [Estructura del repositorio](#estructura-del-repositorio)
4. [Modelo de datos](#modelo-de-datos)
5. [Pipeline de Airflow](#pipeline-de-airflow)
6. [API de inferencia](#api-de-inferencia)
7. [Interfaz gráfica (Streamlit)](#interfaz-gráfica-streamlit)
8. [Pruebas de carga (Locust)](#pruebas-de-carga-locust)
9. [Observabilidad (Prometheus + Grafana)](#observabilidad-prometheus--grafana)
10. [Imágenes Docker](#imágenes-docker)
11. [Despliegue en Kubernetes](#despliegue-en-kubernetes)
12. [Acceso local a las UIs](#acceso-local-a-las-uis)
13. [Variables y secretos](#variables-y-secretos)
14. [Cumplimiento del enunciado](#cumplimiento-del-enunciado)
15. [Troubleshooting](#troubleshooting)
16. [Pendientes naturales](#pendientes-naturales)

---

## Arquitectura

```text
                         ┌────────────────────────┐
                         │      Airflow DAG       │
                         │ mlops_diabetes_pipeline│
                         └──────────┬─────────────┘
                                    │
        ┌───────────────────────────┼────────────────────────────┐
        ▼                           ▼                            ▼
   raw_data            clean_data + train/val/test        MLflow Tracking
  (PostgreSQL)            (PostgreSQL)                  + Model Registry
                                                                │
                                                                ▼
                                                       MinIO (artifacts S3)
                                                                │
                                                                ▼
                                                       FastAPI /predict
                                                                │
            ┌───────────────────────────────────────────────────┼─────────────┐
            ▼                                                   ▼             ▼
       Streamlit UI                                       inference_logs   Prometheus
                                                          (PostgreSQL)         │
                                                                               ▼
                                                                            Grafana
            ▲
            │
        Locust (carga sintética sobre /predict)
```

Todo corre dentro del namespace `mlops-proyecto2` y se comunica por nombres de servicio internos (`postgres`, `mlflow`, `minio`, `api`, etc.).

---

## Componentes

| Componente | Imagen / base | Rol |
|---|---|---|
| `postgres` | `postgres:16` | Backend único para `raw_data`, `clean_data`, `inference_logs`, metadata de MLflow y metadata de Airflow (en bases independientes). |
| `minio` | `minio/minio:RELEASE.2024-10-02T17-50-41Z` | Object store compatible con S3 para artefactos de MLflow. |
| `mlflow` | `innovacion/proyecto2-mlflow:latest` | Tracking server + Model Registry, con backend en PostgreSQL y artifact store en MinIO. |
| `airflow` | `innovacion/proyecto2-airflow:latest` | `webserver` + `scheduler` + `Job` de inicialización; orquesta el pipeline. |
| `api` | `innovacion/proyecto2-api:v2` | FastAPI: `/health`, `/predict`, `/model-info`, `/metrics`. Carga el modelo productivo desde MLflow. |
| `streamlit` | `innovacion/proyecto2-streamlit:latest` | UI para enviar payloads a `/predict` y consultar el modelo. |
| `locust` | `innovacion/proyecto2-locust:latest` | Generador de carga contra `/predict` y `/health`. |
| `prometheus` | `prom/prometheus:v2.54.1` | Scrapea `/metrics` de la API. |
| `grafana` | `grafana/grafana:11.2.2` | Dashboard pre-provisionado para la API. |

Cada uno se despliega con `Deployment` (o `StatefulSet` para `postgres`), `Service` propio, `requests` y `limits` definidos, y `readinessProbe`/`livenessProbe` cuando aplica.

---

## Estructura del repositorio

```text
Proyecto 2/
├── README.md
├── .env.example
├── MLOPS_Proyecto2_2026.pdf            # Enunciado oficial
│
├── airflow/
│   ├── Dockerfile                      # Airflow + dependencias del pipeline
│   ├── requirements.txt
│   └── dags/
│       └── mlops_diabetes_pipeline.py  # DAG principal
│
├── training/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       └── pipeline.py                 # Lógica de ingesta, limpieza y training
│
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       └── main.py                     # FastAPI + Prometheus + logging
│
├── streamlit/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                          # UI de inferencia
│
├── locust/
│   ├── Dockerfile
│   └── locustfile.py                   # Escenario de carga
│
├── mlflow/
│   └── Dockerfile                      # mlflow + psycopg2 + boto3
│
├── sql/
│   └── init/
│       └── 01_init_databases.sql       # DDL de raw/clean/inference_logs
│
└── k8s/
    ├── kustomization.yaml
    ├── 00-namespace.yaml
    ├── 01-config-and-secrets.yaml      # ConfigMap + Secret comunes
    ├── 02-postgres.yaml                # StatefulSet + initdb
    ├── 03-minio.yaml                   # Deployment + PVC + Job creador de bucket
    ├── 04-mlflow.yaml
    ├── 05-api.yaml
    ├── 06-streamlit.yaml
    ├── 07-airflow.yaml                 # init Job + webserver + scheduler
    ├── 08-prometheus.yaml
    ├── 09-grafana.yaml                 # con dashboard provisionado
    └── 10-locust.yaml
```

---

## Modelo de datos

Tres capas físicamente separadas dentro de la base `mlops_data` de PostgreSQL.

### `raw_data`

Lote tal como llega del archivo fuente. No se sobreescribe.

| Columna | Tipo | Descripción |
|---|---|---|
| `raw_id` | `BIGSERIAL PK` | Identificador interno. |
| `batch_id` | `INTEGER` | Lote secuencial (1, 2, 3, …). |
| `source_file` | `TEXT` | Ruta del CSV de origen. |
| `load_timestamp` | `TIMESTAMPTZ` | Cuándo se cargó el lote. |
| `status` | `TEXT` | `loaded` o estado de control. |
| `row_hash` | `TEXT UNIQUE` | Hash determinista para evitar duplicados. |
| `payload` | `JSONB` | Registro completo sin transformaciones destructivas. |

### `clean_data`

Resultado del preprocesamiento, listo para entrenamiento.

| Columna | Tipo | Descripción |
|---|---|---|
| `clean_id` | `BIGSERIAL PK` | |
| `source_batch_id` | `INTEGER` | Lote de origen (opcional). |
| `processed_at` | `TIMESTAMPTZ` | Momento del clean. |
| `row_hash` | `TEXT UNIQUE` | |
| `features` | `JSONB` | Diccionario de features ya limpios. |
| `target_value` | `TEXT` | Target binarizado (`0`/`1`). |

### `inference_logs`

Cada predicción que sale por la API queda registrada acá. Esto cumple el requisito de que las inferencias puedan reutilizarse para reentrenamiento, auditoría o monitoreo.

| Columna | Tipo | Descripción |
|---|---|---|
| `inference_id` | `BIGSERIAL PK` | |
| `request_id` | `TEXT UNIQUE` | Identificador único por solicitud. |
| `inference_timestamp` | `TIMESTAMPTZ` | |
| `model_name` | `TEXT` | Nombre registrado en MLflow. |
| `model_version` | `TEXT` | Versión usada. |
| `model_alias` | `TEXT` | `champion` / `Production`. |
| `input_payload` | `JSONB` | Features recibidos. |
| `prediction` | `JSONB` | Salida del modelo. |
| `score` | `DOUBLE PRECISION` | Probabilidad si el modelo lo soporta. |
| `response_time_ms` | `DOUBLE PRECISION` | Latencia del request. |

---

## Pipeline de Airflow

DAG: **`mlops_diabetes_pipeline`** (`@daily`, no catchup).

Flujo:

1. **`validate_source_file`**: descarga el CSV si no está presente (`DATASET_URL` → `DATASET_PATH`).
2. **`ingest_batch`**: carga el siguiente lote de máximo `BATCH_SIZE` registros (default `15000`) en `raw_data`. El `batch_id` se autoincrementa según el último insertado.
3. **`validate_batch`**: falla si `rows_inserted == 0`, evitando entrenar sobre datos vacíos.
4. **`transform_and_clean`**: lee `raw_data`, normaliza nulos (`?` → `NA`), descarta duplicados, selecciona features candidatos clínicos, transforma el target `readmitted` a binario (`<30` vs resto cuando aplica) y persiste en `clean_data`.
5. **`train_and_promote`**:
   - Carga `clean_data`.
   - Entrena `LogisticRegression` y `RandomForestClassifier` con `ColumnTransformer` (imputación + scaling para numéricas, imputación + one-hot para categóricas).
   - Particiona `train/val/test` (70/15/15) con estratificación.
   - Registra en MLflow params, métricas (`recall`, `precision`, `F1`, `ROC-AUC`), `feature_columns.json` y modelo serializado con signature.
   - Selecciona el mejor por **`val_recall`** (justificable clínicamente: minimizar falsos negativos en readmisión).
   - Lo registra como modelo en `MLFLOW_MODEL_NAME` y le asigna alias `champion` (o stage `Production` como fallback en MLflow ≤ 2.x).

La métrica principal es configurable y está documentada por código.

---

## API de inferencia

FastAPI multi-réplica (2 pods por defecto) con cache de modelo.

### Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/health` | Reporta `ok` o `degraded` y si el modelo está cargado. |
| GET | `/model-info` | Devuelve `model_name`, `model_version`, `model_alias`, `model_uri`. |
| POST | `/predict` | Recibe `{"features": {...}}`, ejecuta la inferencia, persiste el log y devuelve la predicción. |
| GET | `/metrics` | Métricas en formato Prometheus. |

### Carga dinámica del modelo

- La API **no tiene rutas locales quemadas**.
- En `startup` (y bajo demanda) consulta MLflow:
  1. intenta `models:/<MODEL_NAME>@<ALIAS>` (ej. `champion`),
  2. si falla, busca la última versión registrada o la que esté en stage `Production`.
- Hay un **TTL de cache** configurable (`MODEL_CACHE_TTL_SECONDS`, default 300 s) que fuerza la recarga periódica.
- Si Postgres o MLflow aún no están listos, la API arranca igual en modo `degraded` y se recupera sola.

### Request/response

Request:

```json
{
  "features": {
    "race": "Caucasian",
    "gender": "Female",
    "age": "[60-70)",
    "admission_type_id": 1,
    "discharge_disposition_id": 1,
    "admission_source_id": 7,
    "time_in_hospital": 4,
    "num_lab_procedures": 44,
    "num_procedures": 1,
    "num_medications": 11,
    "number_outpatient": 0,
    "number_emergency": 0,
    "number_inpatient": 0,
    "diag_1": "250.83",
    "diag_2": "276",
    "diag_3": "414",
    "A1Cresult": ">7",
    "insulin": "Up",
    "change": "Ch",
    "diabetesMed": "Yes"
  }
}
```

Response (ejemplo):

```json
{
  "request_id": "1715271234567-123456",
  "prediction": 0,
  "score": 0.31,
  "model_name": "DiabetesReadmissionModel",
  "model_version": "3",
  "model_alias": "champion",
  "processing_time_ms": 28.7
}
```

### Métricas expuestas

- `api_requests_total{endpoint, status}` — Counter.
- `api_request_latency_seconds_bucket{endpoint, le=...}` — Histogram (p50/p95/p99 derivables con `histogram_quantile`).

---

## Interfaz gráfica (Streamlit)

`streamlit/app.py` ofrece:

- Editor JSON con un payload de ejemplo precargado.
- Botón **Cargar ejemplo** para resetear el formulario.
- Botón **Consultar modelo** → consume `/model-info` (versión actual, alias, URI).
- Botón **Enviar predicción** → llama a `/predict` y muestra la respuesta.
- Manejo de errores de validación JSON y de errores HTTP de la API.

La UI **solo habla con la API**, nunca directamente con MLflow ni con la base.

---

## Pruebas de carga (Locust)

`locust/locustfile.py` define `InferenceUser` con dos tareas (peso 1 cada una):

- `POST /predict` con un payload de ejemplo.
- `GET /health`.

Sugerencia para sustentación:

- Subir gradualmente usuarios concurrentes.
- Observar en Grafana cómo evolucionan **RPS**, **errores** y **latencia p95** de `/predict`.
- Reportar el punto donde la API empieza a degradarse según los `requests/limits` configurados.

---

## Observabilidad (Prometheus + Grafana)

- **Prometheus** scrapea `api:8000/metrics` cada 15 s (configurado vía `ConfigMap`).
- **Grafana** ya viene con:
  - Datasource `Prometheus` (`http://prometheus:9090`) provisionado.
  - Dashboard **Proyecto 2 API Dashboard** con tres paneles:
    - Predicciones exitosas (`sum(api_requests_total{...status="success"})`).
    - Requests por segundo (`rate(...)[1m]`).
    - Latencia p95 de `/predict` (`histogram_quantile(0.95, ...)`).

Esto satisface el requisito de mostrar el efecto de Locust sobre los dashboards durante la sustentación.

---

## Imágenes Docker

Construir desde la carpeta `Proyecto 2/`:

```bash
docker build -f mlflow/Dockerfile     -t innovacion/proyecto2-mlflow:latest    .
docker build -f api/Dockerfile        -t innovacion/proyecto2-api:latest       .
docker build -f streamlit/Dockerfile  -t innovacion/proyecto2-streamlit:latest .
docker build -f airflow/Dockerfile    -t innovacion/proyecto2-airflow:latest   .
docker build -f locust/Dockerfile     -t innovacion/proyecto2-locust:latest    .
```

> Si Docker Desktop reporta `input/output error` o falta de espacio en `BuildKit`, usar el builder clásico:
>
> ```bash
> DOCKER_BUILDKIT=0 docker build ...
> ```

Publicar en Docker Hub:

```bash
docker push innovacion/proyecto2-mlflow:latest
docker push innovacion/proyecto2-api:latest
docker push innovacion/proyecto2-streamlit:latest
docker push innovacion/proyecto2-airflow:latest
docker push innovacion/proyecto2-locust:latest
```

> El deployment de la API actualmente apunta a `innovacion/proyecto2-api:v2` con `imagePullPolicy: Always`. Cuando publiques una versión nueva, retaggea (`docker tag .. :v3 && docker push`) y actualiza `k8s/05-api.yaml` para forzar el rollout. Esto evita el problema clásico de seguir corriendo una imagen vieja con la misma etiqueta `:latest` en cache.

---

## Despliegue en Kubernetes

### 1. Levantar el clúster

```bash
minikube start
kubectl get nodes
```

### 2. Aplicar todos los manifiestos

```bash
kubectl apply -k "Proyecto 2/k8s"
```

Esto crea:

- Namespace `mlops-proyecto2`.
- `ConfigMap proyecto2-config` y `Secret proyecto2-secrets`.
- StatefulSet de Postgres (con `initdb` que crea las 3 bases).
- Deployment + PVC de MinIO + Job `create-mlflow-bucket`.
- Deployments de MLflow, API (×2 réplicas), Streamlit, Prometheus, Grafana, Locust.
- Job `airflow-init` (db migrate + creación de admin) + Deployments del webserver y scheduler.

### 3. Verificar el estado

```bash
kubectl get pods -n mlops-proyecto2
kubectl get svc  -n mlops-proyecto2
kubectl get jobs -n mlops-proyecto2
kubectl get pvc  -n mlops-proyecto2
```

Estado esperado: todos los pods en `Running 1/1` (o `2/2` para `api`), y los Jobs (`airflow-init`, `create-mlflow-bucket`) en `Completed`.

---

## Acceso local a las UIs

Puerto-forward por servicio:

```bash
kubectl port-forward svc/airflow-webserver -n mlops-proyecto2 8080:8080
kubectl port-forward svc/mlflow            -n mlops-proyecto2 5000:5000
kubectl port-forward svc/streamlit         -n mlops-proyecto2 8501:8501
kubectl port-forward svc/grafana           -n mlops-proyecto2 3000:3000
kubectl port-forward svc/locust            -n mlops-proyecto2 8089:8089
kubectl port-forward svc/api               -n mlops-proyecto2 8000:8000
kubectl port-forward svc/minio             -n mlops-proyecto2 9001:9001
```

URLs y credenciales por defecto:

| Servicio | URL | Credenciales |
|---|---|---|
| Airflow UI | <http://127.0.0.1:8080> | `admin` / `admin123` |
| MLflow UI | <http://127.0.0.1:5000> | — |
| Streamlit | <http://127.0.0.1:8501> | — |
| Grafana | <http://127.0.0.1:3000> | `admin` / `admin123` |
| Locust UI | <http://127.0.0.1:8089> | — |
| API Swagger | <http://127.0.0.1:8000/docs> | — |
| MinIO Console | <http://127.0.0.1:9001> | `minioadmin` / `minioadmin123` |

> Las credenciales viven en `k8s/01-config-and-secrets.yaml`. **Cámbialas antes de ir a producción.**

### Bootstrap del primer modelo

Hasta que el DAG no haya corrido al menos una vez, la API responde `status=degraded` con `model_loaded=false`. El flujo de “estreno” es:

1. Entrar a Airflow.
2. Activar (un-pause) el DAG `mlops_diabetes_pipeline`.
3. Disparar (`Trigger DAG`) la primera ejecución.
4. Esperar a que las 5 tareas terminen en verde.
5. Verificar en MLflow que existe el modelo `DiabetesReadmissionModel` con alias `champion`.
6. Llamar `GET /health` → `status=ok` y `model_loaded=true`.

---

## Variables y secretos

Se inyectan a los contenedores vía `envFrom` (`ConfigMap` + `Secret`).

### `proyecto2-config` (ConfigMap)

| Variable | Default | Uso |
|---|---|---|
| `POSTGRES_HOST` / `POSTGRES_PORT` | `postgres` / `5432` | Conexión común. |
| `DATA_DB` / `MLFLOW_DB` / `AIRFLOW_DB` | `mlops_data` / `mlflow_meta` / `airflow_meta` | Bases separadas por dominio. |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | Tracking + Registry. |
| `MLFLOW_MODEL_NAME` | `DiabetesReadmissionModel` | Nombre registrado. |
| `MLFLOW_MODEL_ALIAS` | `champion` | Alias de productivo. |
| `MLFLOW_S3_ENDPOINT_URL` | `http://minio:9000` | Artifacts. |
| `MINIO_BUCKET` | `mlflow-artifacts` | Bucket de artefactos. |
| `DATASET_URL` | Google Drive del dataset modificado | Fuente del CSV. |
| `DATASET_PATH` | `/opt/project/data/Diabetes.csv` | Ruta dentro del pod. |
| `TARGET_COLUMN` | `readmitted` | Variable a predecir. |
| `BATCH_SIZE` | `15000` | Máximo registros por ejecución. |
| `API_URL` | `http://api:8000` | Usado por Streamlit y Locust. |
| `AIRFLOW__CORE__EXECUTOR` | `LocalExecutor` | No SQLite. |

### `proyecto2-secrets` (Secret)

`POSTGRES_USER`, `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AIRFLOW__CORE__FERNET_KEY`, `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`, `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`.

> El archivo `.env.example` lista las variables equivalentes para correr scripts en local fuera de Kubernetes.

---

## Cumplimiento del enunciado

| Requisito del enunciado | Cómo se cumple |
|---|---|
| Despliegue 100% en Kubernetes | `kubectl apply -k k8s` levanta todo el namespace `mlops-proyecto2`. |
| Imágenes propias en registro público | Todas las imágenes propias se publican en `docker.io/innovacion/proyecto2-*`. |
| `Deployment`/`StatefulSet`, `Service`, `ConfigMap`, `Secret`, `PVC`, probes | Presentes en `k8s/`. |
| `requests` y `limits` en cada contenedor | Definidos para todos los workloads. |
| DAG de Airflow con varias tareas independientes | 5 tareas: validate → ingest → validate batch → clean → train. |
| Carga incremental por lotes ≤ 15.000 | `ingest_raw_batch` lee `BATCH_SIZE` registros por ejecución y avanza con `batch_id`. |
| Capas RAW / CLEAN / INFERENCE separadas | Tablas `raw_data`, `clean_data`, `inference_logs` en `mlops_data`. |
| Trazabilidad en `raw_data` (batch, timestamp, source, status, hash) | Todas presentes. |
| MLflow con backend store y artifact store externos (no SQLite) | Backend en PostgreSQL (`mlflow_meta`), artifacts en MinIO (`mlflow-artifacts`). |
| Selección automática del mejor modelo y alias productivo | `register_best_model` asigna alias `champion` (o stage `Production`). |
| API que consume modelo dinámicamente desde MLflow | `resolve_model_uri` resuelve `models:/<name>@<alias>` o última versión. |
| Endpoints obligatorios `/health`, `/predict`, `/model-info`, `/metrics` | Implementados. |
| Cada inferencia registrada en BD con campos exigidos | `log_inference` persiste en `inference_logs`. |
| Interfaz Streamlit que solo habla con la API | `streamlit/app.py` solo llama HTTP a `API_URL`. |
| Locust como componente del clúster | Deployment + Service propios en `k8s/10-locust.yaml`. |
| Observabilidad con Prometheus + Grafana | Scrape config + dashboard JSON pre-provisionado. |

---

## Troubleshooting

Casos reales encontrados durante el despliegue y cómo se resolvieron.

- **`input/output error` al hacer `docker build`**
  Daño en cache/almacenamiento de Docker Desktop. Soluciones (en orden):
  1. `DOCKER_BUILDKIT=0 docker build ...`
  2. Reiniciar Docker Desktop.
  3. Liberar espacio (`docker system prune -a`).

- **Pods atrapados en `ContainerCreating` por PVC**
  El provisioner `k8s.io/minikube-hostpath` necesita unos segundos. Si demora, validar:
  `kubectl describe pvc minio-data -n mlops-proyecto2`.

- **`api` en `CrashLoopBackOff` con `connection to server at "postgres" ... failed`**
  Postgres aún no está listo cuando arranca la API. La API ya tolera ese caso y arranca en modo `degraded`; la sintomatología desaparece sola tras unos segundos. Si persiste:
  - `kubectl rollout restart deployment/api -n mlops-proyecto2`.

- **`api` con `RuntimeError: No registered versions found for model 'DiabetesReadmissionModel'`**
  Aún no se ha entrenado nada. Disparar el DAG en Airflow.

- **`airflow-webserver` se reinicia con `Connection refused (postgres)`**
  El comando del contenedor espera con `until bash -c '</dev/tcp/postgres/5432'; do sleep 5; done` antes de arrancar. Si el reinicio se mantiene, revisar:
  `kubectl logs deploy/airflow-webserver -n mlops-proyecto2`.

- **Cambios en el código de la API no se ven**
  Las imágenes se publican como `:latest` y `imagePullPolicy: Always` no es suficiente si el nodo cachea por digest. La estrategia segura es **publicar una etiqueta nueva** (`:v3`) y actualizar `k8s/05-api.yaml`.

- **`The Job ... is invalid: spec.template ... field is immutable`**
  Los `Job` no permiten cambiar `spec.template`. Para regenerar `airflow-init`:
  ```bash
  kubectl delete job airflow-init -n mlops-proyecto2
  kubectl apply -f k8s/07-airflow.yaml
  ```

- **Probes muy estrictas tumbando `postgres-0`**
  Las probes ya están relajadas (`timeoutSeconds: 5`, `failureThreshold: 6`, `liveness initialDelaySeconds: 60`).

---

## Pendientes naturales

Cosas que quedan abiertas a criterio del equipo según el ambiente final:

- Refinar `TARGET_COLUMN` y la lista de features según análisis exploratorio sobre el dataset modificado.
- Exportar el dashboard final de Grafana con corridas reales de Locust (`Share → Export → Save to file`).
- Ajustar `replicas`, `requests` y `limits` según el clúster donde se sustente.
- Sustituir credenciales por defecto por valores seguros (especialmente `MINIO_ROOT_PASSWORD`, `POSTGRES_PASSWORD`, `AIRFLOW_ADMIN_PASSWORD`).
- Considerar empaquetar el despliegue como Helm chart si se quiere parametrizar por ambiente.
