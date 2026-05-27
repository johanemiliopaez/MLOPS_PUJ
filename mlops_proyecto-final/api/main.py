from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
import pandas as pd
import time
import os
import uuid
import asyncio
from sqlalchemy import create_engine, text
from datetime import datetime
from typing import Optional

app = FastAPI(title="Real Estate Pricing API")

# --- CONFIGURACIÓN ---
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
DB_URI = os.getenv("DB_URI", "postgresql+psycopg2://mlops_user:mlops_password@postgres:5432/mlops_db")
MODEL_NAME = "RealEstate_Pricing_Model"
ALIAS = "champion"
POLL_INTERVAL_SECONDS = 60  # La API revisará MLflow cada 60 segundos

engine = create_engine(DB_URI)
client = MlflowClient(tracking_uri=MLFLOW_URI)

# Variables globales en memoria
model = None
model_version_id = "Unknown"

# --- MODELO DE DATOS INMOBILIARIO (Tabla 1) ---
class RealEstateData(BaseModel):
    bed: float = 3.0
    bath: float = 2.0
    acre_lot: float = 0.25
    house_size: float = 1500.0
    status: str = "ready for sale"
    city: str = "Bogotá"
    state: str = "Cundinamarca"
    
    # Opcionales para no romper peticiones que no las incluyan
    brokered_by: Optional[int] = None
    street: Optional[str] = None
    zip_code: Optional[str] = None
    prev_sold_date: Optional[str] = None

# --- FUNCIÓN DE CARGA DEL MODELO ---
def load_champion_model():
    global model, model_version_id
    try:
        model_info = client.get_model_version_by_alias(name=MODEL_NAME, alias=ALIAS)
        
        # Solo actualiza si el run_id en MLflow es diferente al que tenemos en RAM
        if model_info.run_id != model_version_id:
            print(f"🔄 ¡Nuevo modelo detectado! Actualizando de {model_version_id} a {model_info.run_id}...")
            mlflow.set_tracking_uri(MLFLOW_URI)
            model_uri = f"models:/{MODEL_NAME}@{ALIAS}"
            model = mlflow.pyfunc.load_model(model_uri)
            model_version_id = model_info.run_id
            print(f"✅ Modelo actualizado en memoria exitosamente.")
            return True
        return False
            
    except Exception as e:
        # Falla silenciosamente en el log si no hay modelo aún, para no saturar la consola
        return False

# --- TAREA EN SEGUNDO PLANO (NUEVO) ---
async def periodic_model_updater():
    """Bucle infinito que revisa MLflow periódicamente sin bloquear la API."""
    while True:
        # Ejecutamos la carga en un hilo separado para no bloquear el Event Loop de FastAPI
        # en caso de que la descarga del modelo tome un par de segundos.
        await asyncio.to_thread(load_champion_model)
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

# --- EVENTOS DE INICIO ---
@app.on_event("startup")
async def startup_event():
    # 1. Carga inicial síncrona para intentar tener el modelo listo antes de recibir tráfico
    load_champion_model()
    # 2. Desplegamos el vigilante en segundo plano
    asyncio.create_task(periodic_model_updater())

# Instrumentación para Prometheus (Grafana)
Instrumentator().instrument(app).expose(app)

# --- ENDPOINTS ---
@app.get("/health")
def health():
    return {
        "status": "ok", 
        "model_loaded": model is not None, 
        "current_version": model_version_id
    }

@app.post("/predict")
def predict(property_data: RealEstateData):
    req_id = str(uuid.uuid4())
    start_time = time.time()
    
    if model is None:
        _log_inference_to_db(req_id, property_data.dict(), None, 0, "failed", "Modelo no cargado en memoria")
        raise HTTPException(status_code=503, detail="Modelo no cargado en memoria. El actualizador está en espera.")
    
    try:
        # 1. Crear DataFrame crudo
        df = pd.DataFrame([property_data.dict()])
        
        # 2. Inferencia (Regresión)
        prediction = float(model.predict(df)[0])
        process_time = (time.time() - start_time) * 1000
        
        # 3. Guardar log exitoso en Base de Datos
        _log_inference_to_db(req_id, property_data.dict(), prediction, process_time, "success", None)

        return {
            "request_id": req_id,
            "estimated_price": prediction,
            "model_used": model_version_id,
            "processing_time_ms": round(process_time, 2)
        }

    except Exception as e:
        error_msg = str(e)
        process_time = (time.time() - start_time) * 1000
        print(f"ERROR EN PREDICCIÓN: {error_msg}")
        
        # Guardar log de fallo en Base de Datos
        _log_inference_to_db(req_id, property_data.dict(), None, process_time, "failed", error_msg)
        
        raise HTTPException(status_code=500, detail="Error interno durante la inferencia")

# --- FUNCIÓN AUXILIAR PARA LOGS ---
def _log_inference_to_db(req_id, input_data, prediction, response_time, status, error_msg):
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO inference_logs 
                (request_id, inference_timestamp, input_data, prediction, model_name, model_version, response_time_ms, status, error_message) 
                VALUES (:id, :ts, :data, :pred, :m_name, :m_ver, :r_time, :status, :error_msg)
            """), {
                "id": req_id, 
                "ts": datetime.now(), 
                "data": pd.io.json.dumps(input_data),
                "pred": prediction if prediction is not None else 0,
                "m_name": MODEL_NAME, 
                "m_ver": model_version_id, 
                "r_time": response_time,
                "status": status,
                "error_msg": error_msg
            })
    except Exception as db_err:
        print(f"Crítico: Error guardando log en DB: {db_err}")