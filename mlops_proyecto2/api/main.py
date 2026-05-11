from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
import mlflow.pyfunc
from mlflow.tracking import MlflowClient
import pandas as pd
import time
import os
import uuid
from sqlalchemy import create_engine, text
from datetime import datetime

app = FastAPI(title="Diabetes Readmission API")

# --- CONFIGURACIÓN ---
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
DB_URI = os.getenv("DB_URI", "postgresql+psycopg2://mlops_user:mlops_password@postgres:5432/mlops_db")
MODEL_NAME = "Diabetes_Readmission_Model"
ALIAS = "champion"

engine = create_engine(DB_URI)
client = MlflowClient(tracking_uri=MLFLOW_URI) # Cliente para consultar metadatos rápido

# Variables globales en memoria
model = None
model_version_id = "Unknown"

# --- MODELO DE DATOS ---
class PatientData(BaseModel):
    age: str = "[50-60)"
    time_in_hospital: int = 5
    num_lab_procedures: int = 45
    num_procedures: int = 1
    num_medications: int = 15
    number_outpatient: int = 0
    number_emergency: int = 0
    number_inpatient: int = 0
    number_diagnoses: int = 6
    change: str = "No"
    diabetesMed: str = "Yes"

# --- FUNCIÓN DE CARGA / ACTUALIZACIÓN ---
def check_and_update_model():
    global model, model_version_id
    try:
        # Consulta súper rápida a los metadatos de MLflow (sin descargar el archivo)
        model_info = client.get_model_version_by_alias(name=MODEL_NAME, alias=ALIAS)
        latest_run_id = model_info.run_id
        
        # Si el modelo en MLflow es diferente al que tenemos en RAM, lo actualizamos
        if latest_run_id != model_version_id:
            print(f"🔄 ¡Nuevo modelo detectado! Actualizando de {model_version_id} a {latest_run_id}...")
            mlflow.set_tracking_uri(MLFLOW_URI)
            model_uri = f"models:/{MODEL_NAME}@{ALIAS}"
            model = mlflow.pyfunc.load_model(model_uri)
            model_version_id = latest_run_id
            print(f"✅ Modelo actualizado en memoria exitosamente.")
            
    except Exception as e:
        # Falla silenciosamente si no hay conexión o no existe el alias aún
        pass

# --- EVENTO DE INICIO ---
@app.on_event("startup")
def load_model_on_startup():
    check_and_update_model()

Instrumentator().instrument(app).expose(app)

@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": model is not None, "current_version": model_version_id}

@app.post("/predict")
def predict(patient: PatientData):
    # 1. Verificar si hay un nuevo modelo antes de predecir (toma milisegundos)
    check_and_update_model()
    
    if model is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado en memoria. Verifique MLflow.")
    
    try:
        start_time = time.time()
        
        # 2. Crear DataFrame crudo
        df = pd.DataFrame([patient.dict()])
        
        # 3. Inferencia
        prediction = int(model.predict(df)[0])
        process_time = (time.time() - start_time) * 1000
        req_id = str(uuid.uuid4())
        
        # 4. Guardar log en Base de Datos
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO inference_logs 
                    (request_id, inference_timestamp, input_data, prediction, model_name, model_version, response_time_ms) 
                    VALUES (:id, :ts, :data, :pred, :m_name, :m_ver, :r_time)
                """), {
                    "id": req_id, "ts": datetime.now(), "data": df.to_json(orient='records'),
                    "pred": prediction, "m_name": MODEL_NAME, "m_ver": model_version_id, "r_time": process_time
                })
        except Exception as db_err:
            print(f"Error guardando log en DB: {db_err}")

        return {
            "request_id": req_id,
            "prediction": prediction,
            "model_used": model_version_id,
            "processing_time_ms": round(process_time, 2)
        }

    except Exception as e:
        print(f"ERROR EN PREDICCIÓN: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))