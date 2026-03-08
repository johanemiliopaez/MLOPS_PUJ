import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any
from minio import Minio
import pandas as pd
import pickle

# Configuración desde variables de entorno
MINIO_HOST = os.environ.get("MINIO_HOST", "minio")
MINIO_PORT = os.environ.get("MINIO_PORT", "9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "password123")
MINIO_BUCKET_MODELOS = os.environ.get("MINIO_BUCKET_MODELOS", "modelos")
MINIO_BUCKET_ARTEFACTOS = os.environ.get("MINIO_BUCKET_ARTEFACTOS", "artefactos")

model_cache = {}
minio_client = Minio(
    f"{MINIO_HOST}:{MINIO_PORT}",
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)

COLUMNAS_MODELO = [
    "Elevation", "Aspect", "Slope", "Horizontal_Distance_To_Hydrology",
    "Vertical_Distance_To_Hydrology", "Horizontal_Distance_To_Roadways",
    "Hillshade_9am", "Hillshade_Noon", "Hillshade_3pm", 
    "Horizontal_Distance_To_Fire_Points", "Wilderness_Area", "Soil_Type"
]

def load_from_minio(bucket, filename):
    try:
        response = minio_client.get_object(bucket, filename)
        obj = pickle.loads(response.read())
        response.close()
        response.release_conn()
        return obj
    except Exception as e:
        print(f"Error al cargar '{filename}' desde '{bucket}': {e}")
        return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Iniciando API: Descargando modelo y mapeo de variables...")
    model_cache["modelo"] = load_from_minio(MINIO_BUCKET_MODELOS, "modelo_rf.pkl")
    model_cache["mapeo"] = load_from_minio(MINIO_BUCKET_ARTEFACTOS, "mapeo_variables.pkl")
    yield
    model_cache.clear()

app = FastAPI(lifespan=lifespan)

class ModelInput(BaseModel):
    features: list[Any]

@app.post("/predict")
def predict(data: ModelInput):
    modelo = model_cache.get("modelo")
    mapeo = model_cache.get("mapeo")
    
    if not modelo:
        raise HTTPException(status_code=503, detail="Modelo no cargado. Usa /reload")
    
    if len(data.features) != len(COLUMNAS_MODELO):
         raise HTTPException(
             status_code=400, 
             detail=f"Se esperan {len(COLUMNAS_MODELO)} características, se recibieron {len(data.features)}."
         )

    advertencias_generadas = []

    try:
        df_input = pd.DataFrame([data.features], columns=COLUMNAS_MODELO)
        
        if mapeo:
            for col, diccionario_columna in mapeo.items():
                if col in df_input.columns:
                    valor_recibido = df_input.at[0, col]
                    
                    if isinstance(valor_recibido, str):
                        if valor_recibido in diccionario_columna:
                            df_input.at[0, col] = diccionario_columna[valor_recibido]
                        else:
                            # --- NUEVA LÓGICA DE RESILIENCIA ---
                            # 1. Registramos la advertencia para el usuario y para los logs del servidor
                            mensaje = f"Valor '{valor_recibido}' no reconocido en la columna '{col}'. Se asignó el valor genérico (-1)."
                            print(f"ADVERTENCIA: {mensaje}")
                            advertencias_generadas.append(mensaje)
                            
                            # 2. Asignamos el valor genérico (-1) para que el modelo pueda procesarlo
                            df_input.at[0, col] = -1

        df_input = df_input.apply(pd.to_numeric)
        prediccion = modelo.predict(df_input)
        
        # Preparamos la respuesta base
        respuesta = {"cover_type_prediccion": int(prediccion[0])}
        
        # Si hubo advertencias, las adjuntamos al JSON final
        if advertencias_generadas:
            respuesta["advertencias"] = advertencias_generadas
            
        return respuesta
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno al procesar/predecir: {str(e)}")

@app.post("/reload")
def reload():
    model_cache["modelo"] = load_from_minio(MINIO_BUCKET_MODELOS, "modelo_rf.pkl")
    model_cache["mapeo"] = load_from_minio(MINIO_BUCKET_ARTEFACTOS, "mapeo_variables.pkl")
    
    if model_cache["modelo"] and model_cache["mapeo"]: 
        return {"status": "Modelo y Mapeo recargados exitosamente"}
    raise HTTPException(status_code=404, detail="Faltan archivos en MinIO (modelo o mapeo)")