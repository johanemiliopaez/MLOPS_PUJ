# Taller Locust — Pruebas de carga sobre API de inferencia (MLflow)

Este taller se centra en **medir el comportamiento de la API de inferencia bajo carga** con **[Locust](https://locust.io/)**: usuarios concurrentes, tasa de generación (spawn rate), latencia, errores y comparación entre una sola instancia, límites de recursos y múltiples réplicas detrás de nginx.

El **stack MLflow** (PostgreSQL, MinIO, MLflow, Jupyter, API) es el entorno donde vive el modelo; Locust **no sustituye** ese stack, lo **ejercita** mediante HTTP.

---

## Objetivos del taller (Locust)

- Ejecutar pruebas de carga **headless** contra `POST /predict` y `GET /health`.
- Entender **usuarios simulados** (`-u`) y **spawn rate** (`-r`).
- Probar la API con **límites de CPU y memoria** en contenedor.
- Probar **varias réplicas** y un **balanceador nginx**.
- Opcional: publicar la imagen de inferencia en **Docker Hub** y levantarla con un compose independiente.

---

## Qué hace Locust en este proyecto

| Elemento | Detalle |
|----------|---------|
| **Escenario** | `locust/locustfile.py` — clase `HttpUser` que llama a la API |
| **Peso de tareas** | `POST /predict` peso **10**; `GET /health` peso **1** (la mayor parte del tráfico es inferencia) |
| **Payload** | Mismo JSON Penguins que en producción: 7 features en `features` |
| **Ejecución** | Contenedor `locustio/locust`, modo **headless** (sin UI web del runner) |
| **Valores por defecto** | 10.000 usuarios, 500 usuarios/segundo de arranque, tiempo de ejecución 10 min (todo configurable por variables de entorno) |

Archivo principal: **`locust/locustfile.py`**. Compose: **`docker-compose.locust.yaml`**.

---

## Arquitectura (énfasis en el flujo de carga)

```
                    ┌─────────────┐
                    │   Locust    │  headless: /predict + /health
                    └──────┬──────┘
                           │ HTTP
                           ▼
              ┌────────────────────────┐
              │  API inferencia :8000  │◄── carga modelo desde MLflow
              └───────────┬────────────┘
                          │
     ┌────────────────────┼────────────────────┐
     ▼                    ▼                    ▼
┌─────────┐         ┌──────────┐        ┌────────┐
│ MLflow  │         │  MinIO   │        │ Postgres│
└─────────┘         └──────────┘        └────────┘

Opción réplicas: Locust → nginx:8020 → api-1, api-2, api-3
```

---

## Puesta en marcha rápida (Locust)

### 1. Red predecible y stack MLflow

```bash
cd "Taller 5 - Locust"
docker compose -p taller5locust up -d --build
```

Entrena el modelo en Jupyter si aún no existe en el registry. La API en **:8000** debe responder.

### 2. Red compartida

Por defecto los compose de Locust usan `taller5locust_mlflow_network`. Si no usaste `-p taller5locust`:

```bash
docker network ls | grep mlflow_network
export MLFLOW_STACK_NETWORK=<nombre_completo_de_la_red>
```

### 3. Lanzar Locust contra la API del compose principal

```bash
export MLFLOW_STACK_NETWORK=taller5locust_mlflow_network
export LOCUST_HOST=http://api-inferencia:8000
# Ajustar agresividad (opcional):
export LOCUST_USERS=10000
export LOCUST_SPAWN_RATE=500
export LOCUST_RUN_TIME=10m

docker compose -f docker-compose.locust.yaml up
```

Al terminar el `--run-time`, Locust imprime **RPS**, **latencias** y **fallos** en consola.

### 4. Escenarios avanzados (resumen)

| Escenario | Compose / acción |
|-----------|------------------|
| API desde imagen Docker Hub + límites CPU/RAM | `docker-compose.inferencia.yaml` (puerto host por defecto **8005**) |
| Tres réplicas + nginx | `docker-compose.inferencia-replicas.yaml` (réplicas **8001–8003**, nginx **8020**) |
| Locust contra nginx | `export LOCUST_HOST=http://nginx-replicas:80` y mismo `docker-compose.locust.yaml` |

---

## Archivos relacionados con Locust (sin tocar `docker-compose.yaml`)

| Archivo | Rol |
|---------|-----|
| `locust/locustfile.py` | Definición de usuarios y tareas |
| `docker-compose.locust.yaml` | Imagen oficial Locust, volumen, comando headless |
| `docker-compose.inferencia.yaml` | API desde Hub + `mem_limit` / `cpus` |
| `docker-compose.inferencia-replicas.yaml` | Réplicas + nginx |
| `nginx/nginx-replicas.conf` | Balanceo `least_conn` |
| `api-inferencia/Dockerfile` + `requirements.txt` | Imagen reproducible para build/push |

La API expone **`GET /health`** para comprobar disponibilidad bajo carga.

---

## Imagen Docker Hub y límites de recursos

```bash
docker build -t TU_USUARIO/penguins-inferencia:latest ./api-inferencia
docker login && docker push TU_USUARIO/penguins-inferencia:latest

export DOCKERHUB_IMAGE=TU_USUARIO/penguins-inferencia:latest
export MLFLOW_STACK_NETWORK=taller5locust_mlflow_network
export API_PUBLISHED_PORT=8005
export API_MEM_LIMIT=256m
export API_CPUS=0.5

docker compose -f docker-compose.inferencia.yaml up -d
```

Réplicas + Locust contra el balanceador:

```bash
docker compose -f docker-compose.inferencia-replicas.yaml up -d
export LOCUST_HOST=http://nginx-replicas:80
docker compose -f docker-compose.locust.yaml up
```

---

## Tabla de escenarios (rellenar tras cada prueba Locust)

| Escenario | Réplica | CPU | Memoria | Usuarios | RPS | Latencia | Errores |
|-----------|---------|-----|---------|----------|-----|----------|---------|
| | | | | | | | |
| | | | | | | | |
| | | | | | | | |

---

## Comandos útiles (chuleta)

| Qué | Comando |
|-----|---------|
| Stack MLflow | `docker compose -p taller5locust up -d --build` |
| **Locust** | `docker compose -f docker-compose.locust.yaml up` |
| Build API | `docker build -t USUARIO/penguins-inferencia:latest ./api-inferencia` |
| Push Hub | `docker push USUARIO/penguins-inferencia:latest` |
| API Hub + límites | `docker compose -f docker-compose.inferencia.yaml up -d` |
| Réplicas + nginx | `docker compose -f docker-compose.inferencia-replicas.yaml up -d` |

---

## Stack MLflow (contexto)

- [x] PostgreSQL, MLflow, MinIO, JupyterLab, API inferencia (modelo desde MLflow)
- Dataset **Penguins**; notebooks `entrenamiento_mlflow.ipynb` y `entrenamiento_multimodelo.ipynb`

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| JupyterLab | http://localhost:8888 | token: `jupyter` |
| MLflow | http://localhost:5002 | — |
| MinIO | http://localhost:9001 | admin / admin1234 |
| API Inferencia | http://localhost:8000 | — |

---

## Referencia API (curl)

**Features (orden):** bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, island_encoded, sex_encoded, year.

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'

curl http://localhost:8000/health
curl http://localhost:8000/models
```

`POST /predict/models` con `model_name` (PenguinsLR, PenguinsKNN, etc.): ver ejemplos en documentación previa del curso o en `api-inferencia/main.py`.
