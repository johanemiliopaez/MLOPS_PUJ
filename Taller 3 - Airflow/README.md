# Taller 3 - Airflow

Pipeline MLOps con Airflow para el caso de Penguins, integrando:

- orquestación con Apache Airflow,
- almacenamiento en MySQL (`penguins_raw` y `penguins`),
- volumen compartido `/shared` para dataset y modelos,
- servicio FastAPI para inferencia con modelos entrenados.

## Componentes principales

- `docker-compose.yaml`: stack completo (Airflow + Postgres + Redis + MySQL + FastAPI).
- `dags/penguins_mysql_pipeline_dag.py`: DAG con 4 tareas (clear, load raw, preprocess, train).
- `mysql-init/create_table_penguins.sh`: creación de tablas en MySQL.
- `Dataset/penguins.csv`: dataset fuente.
- `API/main.py`: API de inferencia (`/rf` y `/lr`) con recarga automática de modelos.
- `Docker/fastapi.Dockerfile`: imagen de FastAPI.

## Flujo del DAG

1. Limpia filas de `penguins_raw` y `penguins`.
2. Carga `/shared/dataset/penguins.csv` en `penguins_raw`.
3. Preprocesa datos y guarda resultado en `penguins`.
4. Entrena `RF` y `LR` y guarda `RF.pkl`/`LR.pkl` en `/shared/modelos`.

## Ejecución rápida

Desde `Taller 3 - Airflow/`:

```bash
docker compose up -d
```

Airflow:
- URL: `http://localhost:8080`
- Usuario/clave por defecto: `airflow` / `airflow`

FastAPI:
- URL: `http://localhost:8989`
- Docs: `http://localhost:8989/docs`

## Documentación detallada

Para guía completa de servicios, comandos y validaciones, revisa:

- `Docker/README.md`
