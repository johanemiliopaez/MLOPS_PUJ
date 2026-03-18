"""
API de Inferencia - Obtiene el modelo desde MLflow Model Registry.
Usa el modelo en etapa Production o el último registrado.
"""
import os
import mlflow
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any

# Configuración MLflow
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MLFLOW_S3_ENDPOINT = os.environ.get("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
MODEL_NAME = os.environ.get("MLFLOW_MODEL_NAME", "PenguinsRF")

mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
os.environ["MLFLOW_S3_ENDPOINT_URL"] = MLFLOW_S3_ENDPOINT

app = FastAPI(title="API Inferencia - MLflow", version="1.0.0")

# Cache del modelo
model_cache = None


def load_model():
    """Carga el modelo desde MLflow (Production o último versión)."""
    global model_cache
    try:
        model_uri = f"models:/{MODEL_NAME}/Production"
        model_cache = mlflow.sklearn.load_model(model_uri)
        return True
    except Exception:
        try:
            model_uri = f"models:/{MODEL_NAME}/latest"
            model_cache = mlflow.sklearn.load_model(model_uri)
            return True
        except Exception as e:
            print(f"Error cargando modelo: {e}")
            return False


@app.on_event("startup")
def startup():
    load_model()


class PredictRequest(BaseModel):
    features: List[Any]


# Orden de features: bill_length_mm, bill_depth_mm, flipper_length_mm, body_mass_g, island_encoded, sex_encoded, year
FEATURE_NAMES = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g", "island_encoded", "sex_encoded", "year"]

@app.get("/")
def root():
    return {
        "message": "API Inferencia - Modelo Penguins desde MLflow",
        "model_loaded": model_cache is not None,
        "model_name": MODEL_NAME,
        "features": FEATURE_NAMES,
    }


@app.post("/predict")
def predict(req: PredictRequest):
    if model_cache is None:
        if not load_model():
            raise HTTPException(status_code=503, detail="Modelo no disponible. Entrena y registra en MLflow.")
    if len(req.features) != len(FEATURE_NAMES):
        raise HTTPException(status_code=400, detail=f"Se esperan {len(FEATURE_NAMES)} features: {FEATURE_NAMES}")
    try:
        import numpy as np
        X = np.array([req.features])
        pred = model_cache.predict(X)
        species_map = {0: "Adelie", 1: "Chinstrap", 2: "Gentoo"}
        return {"species_prediccion": species_map.get(int(pred[0]), int(pred[0]))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reload")
def reload():
    """Fuerza la recarga del modelo desde MLflow."""
    if load_model():
        return {"status": "Modelo recargado"}
    raise HTTPException(status_code=503, detail="No se pudo cargar el modelo")
