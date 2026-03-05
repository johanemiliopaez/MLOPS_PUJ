# Data P2 - API de datos para Proyecto 2

Carpeta con los datos y la API local para el **Proyecto 2** del curso MLOps. Permite obtener porciones del dataset Forest Cover Type por grupo y batch, simulando el comportamiento de la API externa del profesor.

## Contenido

| Archivo / carpeta | Descripción |
|-------------------|-------------|
| `main.py` | API FastAPI que expone los endpoints `/data` y `/restart_data_generation` |
| `data/covertype.csv` | Dataset Forest Cover Type (UCI) con ~581k filas y 55 columnas |
| `data/timestamps.json` | Estado de timestamps y batch por grupo (se genera/actualiza automáticamente) |

## Estructura del dataset

El CSV `covertype.csv` contiene:

- **10 variables numéricas:** Elevation, Aspect, Slope, Horizontal_Distance_To_Hydrology, Vertical_Distance_To_Hydrology, Horizontal_Distance_To_Roadways, Hillshade_9am, Hillshade_Noon, Hillshade_3pm, Horizontal_Distance_To_Fire_Points
- **4 variables one-hot:** Wilderness_Area1–4
- **40 variables one-hot:** Soil_Type1–40
- **Target:** Cover_Type (1–7, tipo de cubierta forestal)

El dataset se divide en **10 batches**. Cada petición a `/data` devuelve una porción aleatoria del batch vigente para el grupo indicado.

## API

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Estado del servicio |
| GET | `/data?group_number=N` | Obtiene una porción aleatoria del batch actual para el grupo N (1–10) |
| GET | `/restart_data_generation?group_number=N` | Reinicia el temporizador y el conteo de batch para el grupo N |

### Comportamiento

- El batch cambia cada **5 segundos** (`MIN_UPDATE_TIME` en `main.py`).
- Para tener una muestra mínima útil, se recomienda extraer al menos una porción de cada uno de los 10 batches.
- Tras recolectar la información mínima, la API responde con error 400.

## Ejecución local

### Requisitos

- Python 3.9+
- `fastapi`, `uvicorn` (ver `requirements.txt` si existe, o instalar con `pip`)

### Arrancar la API

Desde la carpeta `Data P2`:

```bash
cd "Proyecto 1/Data P2"
uvicorn main:app --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Documentación: `http://localhost:8000/docs`

### Pruebas rápidas

```bash
curl "http://localhost:8000/data?group_number=1"
curl "http://localhost:8000/restart_data_generation?group_number=1"
```

## Uso en el proyecto

Esta API local sirve para **pruebas y desarrollo**. La entrega del Proyecto 2 debe usar la API desplegada por el profesor en `http://10.43.101.149:80`.

Flujo sugerido:

1. Orquestar la recolección de datos con **Airflow**.
2. Entrenar y registrar modelos con **MLflow**.
3. Almacenar artefactos en **MinIO** (según diagrama del proyecto).
