# Contenedores - FastAPI + JupyterLab (Penguins)

Entorno de desarrollo para:
- entrenar modelos en `JupyterLab`,
- exponer inferencia en `FastAPI`,
- compartir artefactos y datos por el volumen `commons`.

Las dependencias se gestionan con **UV** usando `Setup/pyproject.toml`.

## Prerrequisitos

- Docker Desktop (o Docker Engine + Docker Compose v2)
- Puerto `8989` libre (FastAPI)
- Puerto `8888` libre (JupyterLab)

## Estructura del proyecto

```text
MLops-taller2/
├── Docker/
│   ├── fastapi.Dockerfile
│   └── jupyterlab.Dockerfile
├── Setup/
│   ├── API/
│   │   └── main.py
│   ├── Model/
│   │   ├── train.py
│   │   └── train_step_by_step.ipynb
│   ├── Dataset/
│   │   └── penguins.csv
│   └── pyproject.toml
├── docker-compose.yml
└── .dockerignore
```

## Servicios

### FastAPI (`fastapi-model`)
- Puerto publicado: `8989`
- App: `Setup/API/main.py`
- Ejecuta con hot-reload (`uvicorn --reload`) para reflejar cambios en `main.py` sin rebuild.
- Nota: en `Docker/fastapi.Dockerfile` se define `EXPOSE 8000`, pero `docker-compose.yml` sobreescribe el comando y ejecuta FastAPI en `8989`.

### JupyterLab (`jupyterlab-ml`)
- Puerto: `8888`
- Arranque sin autenticacion:
  - `--ServerApp.token=`
  - `--ServerApp.password=`

## Volumen compartido `commons`

Los dos contenedores montan `commons` en `/workspace/commons`.

En este proyecto, `Setup/` contiene los directorios que van al volumen:
- `Setup/API`
- `Setup/Model`
- `Setup/Dataset`

Montajes relevantes:
- `./Setup/API` -> `/workspace/commons/API`
- `./Setup/Model` -> `/workspace/commons/Model`
- `./Setup/Dataset` -> `/workspace/commons/Dataset`
- (solo `fastapi`) `./Setup/API` -> `/app` para hot-reload.

## Dependencias con UV

Archivo fuente de dependencias:
- `Setup/pyproject.toml`

Se instala en ambos Dockerfiles con:
- `uv pip install --system -r /tmp/pyproject.toml`

Incluye librerias requeridas por:
- `Setup/API/main.py`
- `Setup/Model/train.py`

## Comandos de ejecucion

### Levantar todo
```bash
docker compose up -d --build
```

### Ver estado
```bash
docker compose ps
```

### Ver logs
```bash
docker compose logs -f
```

### Reiniciar solo FastAPI
```bash
docker compose up -d --build fastapi
```

### Detener servicios
```bash
docker compose down
```

## URLs

- FastAPI: `http://localhost:8989`
- FastAPI docs: `http://localhost:8989/docs`
- JupyterLab: `http://localhost:8888`

## Prueba rapida del API

Ejemplo para `POST /rf`:

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

Respuesta esperada (ejemplo):

```json
{
  "model": "RF",
  "species": "Gentoo"
}
```

## Flujo de trabajo (JupyterLab -> FastAPI)

1. Entrena o actualiza modelos en JupyterLab y guarda `.pkl` en `Setup/Model/`.
2. Si agregas un modelo nuevo (por ejemplo `NN.pkl`), actualiza `Setup/API/main.py` con su ruta y endpoint.
3. FastAPI recarga automaticamente al guardar `main.py` por `--reload`.

Nota: si cambias solo un `.pkl` sin cambiar codigo, la API usara el archivo nuevo segun la logica de carga definida en `main.py`.
