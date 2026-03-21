# Taller 4 - MLflow

Pipeline MLOps con MLflow. Incluye infraestructura orquestada para: PostgreSQL (bases de datos independientes para metadata y negocio), MinIO (artifacts), JupyterLab (entrenamiento) y una API de inferencia construida con FastAPI que consume el modelo directamente desde MLflow Model Registry. **Dataset: Penguins.**

## Requisitos cumplidos

- [x] Instancia de base de datos dedicada para metadata de MLflow (`mlflow_db`)
- [x] Instancia de base de datos adicional para los datos crudos y procesados (`data_db`)
- [x] Instancia MLflow (tracking + model registry)
- [x] Instancia MinIO dedicada para MLflow (artifact store)
- [x] Instancia JupyterLab
- [x] Notebook con experimentación exhaustiva (múltiples técnicas y +20 ejecuciones con variación de hiperparámetros) registrado en MLflow
- [x] Datos raw y procesados almacenados en la base de datos de negocio (`data_db`)
- [x] Modelos registrados correctamente en MLflow
- [x] API de inferencia en contenedor separado que obtiene el modelo directamente desde MLflow

## Arquitectura

```text
PostgreSQL 
 ├─ mlflow_db ←──────────────────→ MLflow (tracking + registry)
 └─ data_db   ←─ JupyterLab ─→          ↓
                     ↓             MinIO (artifacts)
                     ↓                  ↓
              API Inferencia ←──────────┘
      (obtiene modelo desde MLflow)
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
| MLflow Tracking UI | http://localhost:5002 | — |
| MinIO Console | http://localhost:9001 | admin / admin1234 |
| API Inferencia | http://localhost:8000 | — |

## Flujo de Trabajo

1. **Base de Datos (Init)**: Al iniciar, el script `init-db.sh` crea automáticamente dos bases de datos aisladas (`mlflow_db` y `data_db`) y las tablas necesarias.
2. **JupyterLab (Procesamiento y Entrenamiento)**:
   - `entrenamiento_mlflow.ipynb`: Lectura de `data_db`, procesamiento y 20+ experimentos con RandomForest → modelo `PenguinsRF`.
   - `entrenamiento_multimodelo.ipynb`: Experimentación avanzada con 6 técnicas (RF, LR, DT, GB, KNN, SVM) × 20 iteraciones cada una.
3. **API Inferencia**: Despliegue de los modelos en estado *Production* listos para ser consumidos (ver ejemplos abajo).

## API de Inferencia – Ejemplos de Uso

**Features requeridas (7 valores numéricos en el siguiente orden):** bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, island_encoded (0=Torgersen, 1=Biscoe, 2=Dream), sex_encoded (0=female, 1=male), year.

### POST /predict (Usa el modelo por defecto: PenguinsRF)

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'
```

**Respuesta esperada:**
```json
{"species_prediccion": "Adelie"}
```

### POST /predict/models (Elegir un modelo específico)

Puedes solicitar inferencia de cualquiera de los modelos entrenados pasando su nombre en el payload.

```bash
# Ejemplo usando Logistic Regression (PenguinsLR)
curl -X POST http://localhost:8000/predict/models \
  -H "Content-Type: application/json" \
  -d '{"model_name": "PenguinsLR", "features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'

# Ejemplo usando Support Vector Machine (PenguinsSVM)
curl -X POST http://localhost:8000/predict/models \
  -H "Content-Type: application/json" \
  -d '{"model_name": "PenguinsSVM", "features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'
```

**Respuesta esperada:**
```json
{"species_prediccion": "Adelie", "model_name": "PenguinsLR"}
```

**Modelos disponibles:** PenguinsRF, PenguinsLR, PenguinsDT, PenguinsGB, PenguinsKNN, PenguinsSVM

### GET /models (Listar modelos disponibles)

```bash
curl http://localhost:8000/models
```