import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
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
REFRESH_INTERVAL_SEC = int(os.environ.get("MODEL_REFRESH_INTERVAL", "60"))

model_cache = {}
etag_cache = {"modelo": None, "mapeo": None}
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

def load_from_minio(bucket: str, filename: str) -> Optional[Any]:
    try:
        response = minio_client.get_object(bucket, filename)
        obj = pickle.loads(response.read())
        response.close()
        response.release_conn()
        return obj
    except Exception as e:
        print(f"Error al cargar '{filename}' desde '{bucket}': {e}")
        return None


def get_object_etag(bucket: str, filename: str) -> Optional[str]:
    """Obtiene el etag del objeto en MinIO (cambia cuando se actualiza)."""
    try:
        stat = minio_client.stat_object(bucket, filename)
        return stat.etag if stat else None
    except Exception:
        return None


def reload_model_and_mapeo() -> bool:
    """Recarga modelo y mapeo desde MinIO. Retorna True si OK."""
    modelo = load_from_minio(MINIO_BUCKET_MODELOS, "modelo_rf.pkl")
    mapeo = load_from_minio(MINIO_BUCKET_ARTEFACTOS, "mapeo_variables.pkl")
    if modelo and mapeo:
        model_cache["modelo"] = modelo
        model_cache["mapeo"] = mapeo
        etag_cache["modelo"] = get_object_etag(MINIO_BUCKET_MODELOS, "modelo_rf.pkl")
        etag_cache["mapeo"] = get_object_etag(MINIO_BUCKET_ARTEFACTOS, "mapeo_variables.pkl")
        return True
    return False


async def refresh_loop():
    """Tarea en background: verifica si modelo o mapeo cambiaron y recarga."""
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SEC)
        try:
            etag_modelo = get_object_etag(MINIO_BUCKET_MODELOS, "modelo_rf.pkl")
            etag_mapeo = get_object_etag(MINIO_BUCKET_ARTEFACTOS, "mapeo_variables.pkl")
            if (etag_modelo and etag_modelo != etag_cache.get("modelo")) or (
                etag_mapeo and etag_mapeo != etag_cache.get("mapeo")
            ):
                if reload_model_and_mapeo():
                    print(f"Modelo y mapeo actualizados desde MinIO (cada {REFRESH_INTERVAL_SEC}s)")
        except Exception as e:
            print(f"Error en auto-refresh: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Iniciando API: Descargando modelo y mapeo de variables...")
    reload_model_and_mapeo()
    task = asyncio.create_task(refresh_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
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
    """Recarga manual de modelo y mapeo desde MinIO."""
    if reload_model_and_mapeo():
        return {"status": "Modelo y Mapeo recargados exitosamente"}
    raise HTTPException(status_code=404, detail="Faltan archivos en MinIO (modelo o mapeo)")