# Proyecto 1 - MLOps

Entorno MLOps con Airflow (CeleryExecutor), MinIO, PostgreSQL, MySQL, Redis, Jupyter y APIs FastAPI para datos y modelos.

## Estructura

| Carpeta | Descripción |
|---------|-------------|
| `Docker/` | Docker Compose con todos los servicios (Airflow, MinIO, PostgreSQL, MySQL, Redis, api-data, api-model, Jupyter) |
| `Docker/dags/` | DAGs de Airflow (ingestión y preparación de datos) |
| `Docker/mysql-init/` | Scripts SQL de inicialización para tablas `data_raw` y `data_prepared` |
| `API-Data P2/` | API de datos Forest Cover Type (endpoints `/data`, `/restart_data_generation`) |
| `API-Model/` | API de modelos (FastAPI Hello World) |
| `Jupyter/` | Datos, notebooks y scripts de preparación |

## Servicios (Docker Compose)

| Servicio | Imagen | Puerto | Función |
|----------|--------|--------|---------|
| **postgres** | postgres:13 | — | Metadata de Airflow (DAGs, tareas, logs) |
| **redis** | redis:latest | 6379 (interno) | Broker de Celery |
| **mysql** | mysql:8.0 | 3306 | Datos del proyecto (`data_raw`, `data_prepared`) |
| **minio** | minio/minio:latest | 9000, 9001 | Almacenamiento S3, bucket `models` |
| **minio-init** | minio/mc:latest | — | Crea el bucket `models` al iniciar |
| **airflow-init** | apache/airflow:2.6.0 | — | Inicializa BD y usuario de Airflow |
| **airflow-webserver** | apache/airflow:2.6.0 | 8080 | Interfaz web de Airflow |
| **airflow-scheduler** | apache/airflow:2.6.0 | — | Planificador de DAGs |
| **airflow-worker** | apache/airflow:2.6.0 | — | Ejecutor Celery (tareas en paralelo) |
| **airflow-triggerer** | apache/airflow:2.6.0 | — | Triggers diferidos (DeferrableOperator) |
| **api-data** | data-p2-api:latest (build) | 8988 | API de datos Forest Cover Type |
| **api-model** | api-model:latest (build) | 8989 | API de modelos + MinIO |
| **jupyter** | data-p2-jupyter:latest (build) | 8888 | Jupyter Lab |

## Bases de datos

| Base de datos | Uso |
|---------------|-----|
| **PostgreSQL** | Metadata de Airflow (usuario: `airflow`) |
| **MySQL** | `data_raw` y `data_prepared` (usuario: `airflow_user`, DB: `airflow_data`) |

## Volúmenes

- `postgres-db-volume` — Persistencia de PostgreSQL
- `mysql-db-volume` — Persistencia de MySQL
- `minio-data` — Datos de MinIO
- `airflow-logs` — Logs de Airflow
- `airflow-plugins` — Plugins de Airflow

## Dependencias de arranque

```
postgres, redis, mysql → airflow-init → airflow-webserver, airflow-scheduler, airflow-worker, airflow-triggerer
minio → minio-init → api-model, jupyter
api-data → airflow-webserver, airflow-scheduler
```

## Inicio rápido

```bash
cd "Proyecto 1/Docker"
docker compose -f docker-compose-full.yaml up -d --build
```

## Credenciales

| Servicio | Usuario | Contraseña / Token |
|----------|---------|---------------------|
| PostgreSQL | `airflow` | `airflow` |
| MySQL | `airflow_user` | `airflow_pass` |
| MinIO | `minioadmin` | `minioadmin` |
| Airflow | `airflow` | `airflow` |
| Jupyter | — | Token: `jupyter` |

## URLs

| Servicio | URL |
|----------|-----|
| **Airflow** | http://localhost:8080 |
| **API Data** | http://localhost:8988 |
| **API Model** | http://localhost:8989 |
| **MinIO Console** | http://localhost:9001 |
| **Jupyter** | http://localhost:8888 |

## Acceso a MinIO desde Jupyter

```python
import os
from minio import Minio

client = Minio(
    "minio:9000",
    access_key=os.environ["MINIO_ACCESS_KEY"],
    secret_key=os.environ["MINIO_SECRET_KEY"],
    secure=False
)

for obj in client.list_objects("models"):
    print(obj.object_name)
```

## Dockerfiles (`Docker/`)

| Archivo | Uso |
|---------|-----|
| `dataApi.Dockerfile` | api-data y api-model (FastAPI genérico) |
| `jupyter.Dockerfile` | Jupyter Lab con MinIO y mc |

## Imágenes Docker

| Imagen | Tipo |
|--------|------|
| `postgres:13` | Pull |
| `mysql:8.0` | Pull |
| `redis:latest` | Pull |
| `minio/minio:latest` | Pull |
| `minio/mc:latest` | Pull |
| `apache/airflow:2.6.0` | Pull |
| `data-p2-api:latest` | Build (api-data) |
| `api-model:latest` | Build |
| `data-p2-jupyter:latest` | Build |

## Comandos útiles

```bash
# Levantar todo
docker compose -f docker-compose-full.yaml up -d --build

# Ver logs
docker compose -f docker-compose-full.yaml logs -f

# Detener
docker compose -f docker-compose-full.yaml down
```
