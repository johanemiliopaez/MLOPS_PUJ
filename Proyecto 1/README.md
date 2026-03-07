# Proyecto 1 - MLOps

Entorno MLOps con Airflow (CeleryExecutor), MinIO, PostgreSQL, MySQL, Redis, Jupyter y APIs FastAPI para datos y modelos Forest Cover Type.

## Flujo del pipeline

```
API Data → Airflow DAG → MySQL (data_raw → data_prepared) → Jupyter (entrenamiento) → MinIO (PKL) → API Model (predicciones)
```

## Estructura

| Carpeta | Descripción |
|---------|-------------|
| `Docker/` | Docker Compose con todos los servicios |
| `Docker/dags/` | DAGs de Airflow (ingestión, preparación, split) |
| `Docker/mysql-init/` | Scripts SQL para `data_raw` y `data_prepared` |
| `API-Data P2/` | API de datos Forest Cover Type (`/data`, `/restart_data_generation`) |
| `API-Model/` | API de predicciones Covertype (PKL desde MinIO) + `Test.py` |
| `Jupyter/` | Notebooks de entrenamiento (`covertype.ipynb`) |

## Servicios (Docker Compose)

| Servicio | Imagen | Puerto | Función |
|----------|--------|--------|---------|
| **postgres** | postgres:13 | — | Metadata de Airflow |
| **redis** | redis:latest | 6379 (interno) | Broker de Celery |
| **mysql** | mysql:8.0 | 3306 | `data_raw`, `data_prepared` |
| **minio** | minio/minio:latest | 9000, 9001 | Bucket `models` (PKL) |
| **minio-init** | minio/mc:latest | — | Crea bucket `models` |
| **airflow-init** | apache/airflow:2.6.0 | — | Inicializa Airflow |
| **airflow-webserver** | apache/airflow:2.6.0 | 8080 | UI de Airflow |
| **airflow-scheduler** | apache/airflow:2.6.0 | — | Planificador |
| **airflow-worker** | apache/airflow:2.6.0 | — | Celery worker |
| **airflow-triggerer** | apache/airflow:2.6.0 | — | Triggerer |
| **api-data** | data-p2-api:latest | 8988 | API datos Forest Cover |
| **api-model** | api-model:latest | 8989 | API predicciones (PKL MinIO, auto-refresh) |
| **jupyter** | data-p2-jupyter:latest | 8888 | Jupyter Lab |

## Bases de datos

| Base de datos | Uso |
|---------------|-----|
| **PostgreSQL** | Metadata de Airflow (usuario: `airflow`) |
| **MySQL** | `data_raw`, `data_prepared` (usuario: `airflow_user`, DB: `airflow_data`) |

## Inicio rápido

```bash
cd "Proyecto 1/Docker"
docker compose -f docker-compose-full.yaml up -d --build
```

## DAG: data_ingestion_preparation

Automatiza ingestión, preparación y split de datos Forest Cover Type.

| Parámetro | Valor |
|-----------|-------|
| **Schedule** | Cada 5 minutos |
| **Archivo** | `Docker/dags/data_ingestion_dag.py` |

### Flujo

```
extract_data_from_api → load_data → clean_data → transform_data → validate_data → feature_engineering → split → store_prepared_data
```

### Tareas

| # | Task | Descripción |
|---|------|-------------|
| 1 | extract_data_from_api | Consulta API con `group_number=1` |
| 2 | load_data | Inserta en `data_raw` |
| 3 | clean_data | Limpieza de datos |
| 4 | transform_data | Estandarización z-score |
| 5 | validate_data | Validación |
| 6 | feature_engineering | Passthrough |
| 7 | split | 80% train / 20% test (`data_type`) |
| 8 | store_prepared_data | Inserta en `data_prepared` |

### Ejecutar el DAG

1. http://localhost:8080 (usuario: `airflow`, contraseña: `airflow`)
2. Activar DAG **data_ingestion_preparation**
3. Trigger manual: clic en DAG → **Trigger DAG** (▶️)

## Jupyter: covertype.ipynb

Entrena RandomForestClassifier y sube el modelo a MinIO.

1. Carga datos desde MySQL (`data_prepared` por `data_type`)
2. Entrena RandomForestClassifier
3. Guarda PKL con modelo + encoders (`covertype_rf.pkl`) en MinIO bucket `models`

**Ubicación:** `Jupyter/covertype.ipynb`

**Nota:** Jupyter y API-Model usan scikit-learn 1.3.x para compatibilidad del PKL.

## API Model: predicciones

API que carga el PKL desde MinIO y sirve predicciones. Se actualiza automáticamente cuando el PKL cambia en MinIO.

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Estado del modelo |
| GET | `/health` | Health check |
| POST | `/predict` | Predicciones |
| POST | `/refresh` | Recarga modelo desde MinIO |

### Consumir `/predict`

```bash
curl -X POST http://localhost:8989/predict \
  -H "Content-Type: application/json" \
  -d '{
    "instances": [{
      "elevation": 2596,
      "aspect": 51,
      "slope": 3,
      "horizontal_distance_to_hydrology": 258,
      "vertical_distance_to_hydrology": 0,
      "horizontal_distance_to_roadways": 510,
      "hillshade_9am": 221,
      "hillshade_noon": 232,
      "hillshade_3pm": 148,
      "horizontal_distance_to_fire_points": 6279,
      "wilderness_area": "Rawah",
      "soil_type": "C7744"
    }]
  }'
```

**Respuesta:** `{"predictions": [0]}` (Cover Type 0-6)

**Clases Cover Type:** 0=Spruce/Fir, 1=Lodgepole Pine, 2=Ponderosa Pine, 3=Cottonwood/Willow, 4=Aspen, 5=Douglas-fir, 6=Krummholz

**Documentación:** http://localhost:8989/docs

### Test: 100 requests

```bash
cd "Proyecto 1/API-Model"
python Test.py
```

Ejecuta 100 requests aleatorios al endpoint `/predict` y muestra un resumen con: total exitosos/errores, distribución de predicciones por nombre, y latencias (min/max/avg).

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
| **API Model Docs** | http://localhost:8989/docs |
| **MinIO Console** | http://localhost:9001 |
| **Jupyter** | http://localhost:8888 |

## Comandos útiles

```bash
# Levantar todo
docker compose -f docker-compose-full.yaml up -d --build

# Actualizar solo api-model
docker compose -f docker-compose-full.yaml up -d --build api-model

# Ver logs
docker compose -f docker-compose-full.yaml logs -f
docker compose -f docker-compose-full.yaml logs -f api-model

# Detener
docker compose -f docker-compose-full.yaml down
```

## Orden de uso recomendado

1. Levantar el stack
2. Ejecutar el DAG en Airflow (para llenar `data_prepared`)
3. Ejecutar `covertype.ipynb` en Jupyter (entrenar y subir PKL a MinIO)
4. Consumir la API en http://localhost:8989/predict
5. Probar con `python API-Model/Test.py` (100 requests)
