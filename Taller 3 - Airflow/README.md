# Taller 3 - Airflow

Pipeline MLOps con Apache Airflow para el caso de Penguins, integrando:

- `CeleryExecutor`
- `PostgreSQL` como metadatabase
- `Redis` como broker de colas
- `MySQL` para datos del pipeline (`penguins_raw` y `penguins`)
- `FastAPI` para inferencia con modelos entrenados por Airflow
- volumen compartido `/shared` entre contenedores

Esta configuración está orientada a **desarrollo y pruebas locales**.

## Prerrequisitos

- Docker Desktop (o Docker Engine + Docker Compose v2)
- Recomendado: al menos 4 GB de RAM disponibles para Docker
- Puerto `8080` libre (Airflow Webserver)
- Puerto `3306` libre (MySQL)
- Puerto `8989` libre (FastAPI)

## Estructura esperada

Desde `Taller 3 - Airflow/` se usan estos directorios:

- `./dags` -> `/opt/airflow/dags`
- `./logs` -> `/opt/airflow/logs`
- `./plugins` -> `/opt/airflow/plugins`
- `./mysql-init` -> scripts de inicialización de MySQL
- `./Dataset/penguins.csv` -> origen para copiar a volumen compartido

Adicionalmente, el volumen `shared-data` se monta en `/shared` y contiene:

- `/shared/dataset/penguins.csv`
- `/shared/modelos/RF.pkl` y `/shared/modelos/LR.pkl` (salida del DAG)

Si no existen, créalos antes de levantar los servicios:

```bash
mkdir -p dags logs plugins mysql-init
```

## Levantar el entorno

```bash
docker compose up -d
```

En el primer arranque:

- `airflow-init` inicializa Airflow y crea el usuario administrador.
- `dataset-init` crea `/shared/dataset` y copia `penguins.csv`.
- MySQL ejecuta scripts de `./mysql-init`.

## Verificar estado

```bash
docker compose ps
docker compose logs -f airflow-webserver
```
<p align="center">
<img width="332" height="512" alt="image" src="https://github.com/user-attachments/assets/e37eac4c-f37e-40f0-bede-e324b9bc448a" />
<img width="888" height="584" alt="image" src="https://github.com/user-attachments/assets/2a158f5b-d0cf-46c8-92ea-d5952ab680d6" />
</p>



## Acceso a la interfaz

- URL: `http://localhost:8080`
- Usuario por defecto: `airflow`
- Contraseña por defecto: `airflow`
<p align="center">
<img width="1723" height="498" alt="image" src="https://github.com/user-attachments/assets/fd57b52d-2994-42e1-afb5-b179e6b15039" />
</p>

## MySQL del taller

- Host desde contenedores: `mysql`
- Host desde tu máquina: `localhost`
- Puerto: `3306`
- Base por defecto: `airflow_lab`
- Usuario por defecto: `airflow_user`
- Password por defecto: `airflow_pass`

Tablas inicializadas:

- `penguins_raw`
- `penguins`

Script de inicialización:

- `mysql-init/create_table_penguins.sh`
<p align="center">
<img width="1318" height="595" alt="image" src="https://github.com/user-attachments/assets/730222cf-5a87-4d32-bb98-cb1cb0ed23ec" />
</p>

## FastAPI del taller

- Servicio: `fastapi`
- URL base: `http://localhost:8989`
- Swagger: `http://localhost:8989/docs`
- Código API: `API/main.py`

Endpoints:

- `POST /rf`
- `POST /lr`

Recarga de modelos:

- El API lee modelos desde `/shared/modelos`.
- Si `RF.pkl` o `LR.pkl` cambian (por una nueva ejecución del DAG), la API recarga automáticamente el modelo actualizado sin reiniciar contenedor.

<p align="center">
<img width="391" height="400" alt="image" src="https://github.com/user-attachments/assets/e0375067-cba2-4893-83ac-e5131aa37554" />
</p>


## DAG de pipeline Penguins

DAG creado:

- `dags/penguins_mysql_pipeline_dag.py`

Flujo del DAG:

1. **step_1_clear_tables**: limpia filas de `penguins_raw` y `penguins`.
2. **step_2_load_raw**: carga `/shared/dataset/penguins.csv` en `penguins_raw`.
3. **step_3_preprocess**: aplica limpieza/transformación/validación y guarda en `penguins`.
4. **step_4_train**: entrena RF/LR y guarda modelos en `/shared/modelos`.

## Ejecutar el DAG

1. Abre Airflow en `http://localhost:8080`.
2. Activa `penguins_mysql_pipeline`.
3. Ejecuta un run manual desde la UI.

Verificación rápida de modelos:

```bash
docker compose exec airflow-webserver ls -lah /shared/modelos
```

## Ejecutar FastAPI

Construir y levantar solo el servicio:

```bash
docker compose up -d --build fastapi
```

Prueba rápida:

```bash
curl -X POST "http://localhost:8989/rf" \
  -H "Content-Type: application/json" \
  -d '{
    "island": "Biscoe",
    "bill_length_mm": 48.7,
    "bill_depth_mm": 14.1,
    "flipper_length_mm": 210,
    "body_mass_g": 4450,
    "sex": "male",
    "year": 2008
  }'
```

## Comandos útiles

Detener servicios:

```bash
docker compose down
```

Detener y eliminar volúmenes (reinicio limpio):

```bash
docker compose down -v
```

Ver logs de todos los servicios:

```bash
docker compose logs -f
```

## Ejecutar Flower (opcional)

Para monitorizar workers Celery:

```bash
docker compose --profile flower up -d
```

- URL Flower: `http://localhost:5555`

## Notas

- El archivo `docker-compose.yaml` usa una plantilla oficial de Airflow para entorno local.
- Si cambias scripts en `mysql-init` y ya existe el volumen MySQL, esos scripts no se re-ejecutan automáticamente.
- Para reinicializar DB de MySQL desde cero: `docker compose down -v && docker compose up -d`.
- No se recomienda este stack tal cual para producción.
