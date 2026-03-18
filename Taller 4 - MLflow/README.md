# Taller 4 - MLflow

Pipeline MLOps con MLflow: PostgreSQL (metadata + datos), MinIO (artifacts), JupyterLab (entrenamiento) y API de inferencia que obtiene el modelo desde MLflow. **Dataset: Penguins.**

## Requisitos cumplidos

- [x] Instancia PostgreSQL (metadata MLflow + datos raw/procesados)
- [x] Instancia MLflow (tracking + model registry)
- [x] Instancia MinIO (artifact store)
- [x] Instancia JupyterLab
- [x] Notebook con 20+ experimentos (variación de hiperparámetros) registrados en MLflow
- [x] Datos raw y procesados en base de datos
- [x] Modelos registrados en MLflow
- [x] API de inferencia en contenedor separado que obtiene el modelo desde MLflow

## Arquitectura

```
PostgreSQL (mlflow_db + data_db) ←→ MLflow (tracking + registry)
         ↑                                    ↓
    JupyterLab  ←──────────────────────  MinIO (artifacts)
         ↓
    API Inferencia (obtiene modelo desde MLflow)
```

## Ejecución

```bash
cd "Taller 4 - MLflow"
docker compose up -d --build
```

## Servicios

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| JupyterLab | http://localhost:8888 | token: jupyter |
| MLflow | http://localhost:5002 | — |
| MinIO | http://localhost:9001 | admin / admin1234 |
| API Inferencia | http://localhost:8000 | — |

## Flujo

1. **JupyterLab**:
   - `entrenamiento_mlflow.ipynb`: 20+ experimentos con RandomForest → modelo PenguinsRF
   - `entrenamiento_multimodelo.ipynb`: 6 técnicas (RF, LR, DT, GB, KNN, SVM) × 20 iteraciones cada una

2. **API Inferencia**: ver ejemplos abajo.

## API de Inferencia – Ejemplos

**Features (7 valores en orden):** bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, island_encoded (0=Torgersen, 1=Biscoe, 2=Dream), sex_encoded (0=female, 1=male), year.

### POST /predict (modelo original PenguinsRF)

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'
```

**Respuesta:**
```json
{"species_prediccion": "Adelie"}
```

### POST /predict/models (elegir modelo)

```bash
# Logistic Regression
curl -X POST http://localhost:8000/predict/models \
  -H "Content-Type: application/json" \
  -d '{"model_name": "PenguinsLR", "features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'

# KNN
curl -X POST http://localhost:8000/predict/models \
  -H "Content-Type: application/json" \
  -d '{"model_name": "PenguinsKNN", "features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'

# SVM
curl -X POST http://localhost:8000/predict/models \
  -H "Content-Type: application/json" \
  -d '{"model_name": "PenguinsSVM", "features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'
```

**Respuesta:**
```json
{"species_prediccion": "Adelie", "model_name": "PenguinsLR"}
```

**Modelos disponibles:** PenguinsRF, PenguinsLR, PenguinsDT, PenguinsGB, PenguinsKNN, PenguinsSVM

### GET /models (listar modelos)

```bash
curl http://localhost:8000/models
```
