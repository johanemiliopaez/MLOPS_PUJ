"""
API Model - Covertype RandomForestClassifier desde MinIO.

Carga el modelo PKL desde MinIO y sirve predicciones.
Se actualiza automáticamente cuando el PKL cambia en MinIO.
"""

import os
import io
import asyncio
import traceback
import joblib
import numpy as np
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from minio import Minio

# Configuración MinIO
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "models")
MODEL_OBJECT = os.environ.get("MODEL_OBJECT", "covertype_rf.pkl")
REFRESH_INTERVAL_SEC = int(os.environ.get("MODEL_REFRESH_INTERVAL", "60"))

# Estado global del modelo
model_state = {"model": None, "encoders": None, "etag": None, "ready": False}

FEATURE_COLS = [
    "elevation", "aspect", "slope",
    "horizontal_distance_to_hydrology", "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways", "hillshade_9am", "hillshade_noon",
    "hillshade_3pm", "horizontal_distance_to_fire_points",
    "wilderness_area", "soil_type",
]


def get_minio_client() -> Minio:
    host = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
    return Minio(host, access_key=MINIO_ACCESS, secret_key=MINIO_SECRET, secure=False)


def load_model_from_minio() -> bool:
    """Descarga el PKL de MinIO y carga el modelo. Retorna True si OK."""
    try:
        client = get_minio_client()
        response = client.get_object(MINIO_BUCKET, MODEL_OBJECT)
        data = response.read()
        response.close()
        response.release_conn()

        bundle = joblib.load(io.BytesIO(data))

        if isinstance(bundle, dict):
            model_state["model"] = bundle.get("model")
            model_state["encoders"] = {
                "le_wilderness": bundle.get("le_wilderness"),
                "le_soil": bundle.get("le_soil"),
            }
        else:
            model_state["model"] = bundle
            model_state["encoders"] = None

        model_state["ready"] = model_state["model"] is not None
        return model_state["ready"]
    except Exception as e:
        print(f"Error cargando modelo: {e}")
        model_state["ready"] = False
        return False


def get_object_etag() -> Optional[str]:
    """Obtiene el etag del objeto en MinIO (cambia cuando se actualiza)."""
    try:
        client = get_minio_client()
        stat = client.stat_object(MINIO_BUCKET, MODEL_OBJECT)
        return stat.etag if stat else None
    except Exception:
        return None


async def refresh_loop():
    """Loop en background que verifica si el PKL cambió y recarga."""
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SEC)
        try:
            etag = get_object_etag()
            if etag and etag != model_state.get("etag"):
                if load_model_from_minio():
                    model_state["etag"] = etag
                    print(f"Modelo actualizado desde MinIO ({MODEL_OBJECT})")
        except Exception as e:
            print(f"Error en refresh: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicio: carga modelo. Background: refresh periódico."""
    load_model_from_minio()
    etag = get_object_etag()
    if etag:
        model_state["etag"] = etag
    task = asyncio.create_task(refresh_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="API Model - Covertype",
    version="1.0.0",
    description="Predicciones con RandomForestClassifier cargado desde MinIO. Se actualiza automáticamente.",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Devuelve el detalle del error para depuración (excepto HTTPException)."""
    if isinstance(exc, HTTPException):
        raise exc
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "type": type(exc).__name__},
    )


class FeatureInput(BaseModel):
    elevation: float
    aspect: float
    slope: float
    horizontal_distance_to_hydrology: float
    vertical_distance_to_hydrology: float
    horizontal_distance_to_roadways: float
    hillshade_9am: float
    hillshade_noon: float
    hillshade_3pm: float
    horizontal_distance_to_fire_points: float
    wilderness_area: str = Field(..., description="Ej: Rawah, Neota, Commanche, Cache")
    soil_type: str = Field(..., description="Ej: C2702, C2703, ...")


class PredictRequest(BaseModel):
    instances: List[FeatureInput]


class PredictResponse(BaseModel):
    predictions: List[int]


def encode_features(instances: List[FeatureInput]) -> List[List[float]]:
    """Convierte las instancias a la matriz de features para el modelo."""
    encoders = model_state.get("encoders") or {}
    le_w = encoders.get("le_wilderness")
    le_s = encoders.get("le_soil")

    rows = []
    for inst in instances:
        row = [
            inst.elevation, inst.aspect, inst.slope,
            inst.horizontal_distance_to_hydrology, inst.vertical_distance_to_hydrology,
            inst.horizontal_distance_to_roadways, inst.hillshade_9am, inst.hillshade_noon,
            inst.hillshade_3pm, inst.horizontal_distance_to_fire_points,
        ]
        if le_w is not None and le_s is not None:
            try:
                w_val = str(inst.wilderness_area)
                s_val = str(inst.soil_type)
                w_enc = le_w.transform([w_val])[0] if w_val in le_w.classes_ else 0
                s_enc = le_s.transform([s_val])[0] if s_val in le_s.classes_ else 0
            except Exception:
                w_enc = 0
                s_enc = 0
            row.extend([w_enc, s_enc])
        else:
            row.extend([0, 0])
        rows.append(row)
    return rows


@app.get("/")
async def root():
    return {
        "message": "API Model - Covertype RandomForestClassifier",
        "model_ready": model_state["ready"],
        "model_object": MODEL_OBJECT,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "model_ready": model_state["ready"]}


@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    if not model_state["ready"]:
        raise HTTPException(status_code=503, detail="Modelo no cargado. Verifica que el PKL exista en MinIO.")
    if not req.instances:
        return PredictResponse(predictions=[])

    try:
        X = encode_features(req.instances)
        X_arr = np.array(X, dtype=np.float64)
        model = model_state["model"]
        preds = model.predict(X_arr)
        return PredictResponse(predictions=[int(p) for p in preds.tolist()])
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/refresh")
async def refresh_model():
    """Fuerza la recarga del modelo desde MinIO."""
    if load_model_from_minio():
        model_state["etag"] = get_object_etag()
        return {"status": "ok", "message": "Modelo recargado"}
    raise HTTPException(status_code=500, detail="No se pudo cargar el modelo")
