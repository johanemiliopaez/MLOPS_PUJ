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
| MinIO | http://localhost:9001 | minioadmin / minioadmin |
| API Inferencia | http://localhost:8000 | — |

## Flujo

1. **JupyterLab**: Abrir `entrenamiento_mlflow.ipynb` y ejecutar todas las celdas.
   - Carga datos desde PostgreSQL (o CSV si está vacío)
   - Procesa y guarda en `data_procesada`
   - Ejecuta 20+ experimentos con RandomForest (n_estimators, max_depth, min_samples_split)
   - Registra en MLflow y promueve el mejor a Production

2. **API Inferencia**: `POST /predict` con 7 features en orden:
```json
{"features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}
```
(bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, island_encoded, sex_encoded, year)

## Formato de predicción

El modelo espera 7 features: bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, island_encoded (0=Torgersen, 1=Biscoe, 2=Dream), sex_encoded (0=female, 1=male), year. Respuesta: `species_prediccion` (Adelie, Chinstrap o Gentoo).
