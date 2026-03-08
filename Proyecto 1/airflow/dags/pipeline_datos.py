import os
from airflow.decorators import dag, task
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
import requests
from minio import Minio
import pickle
import io
from sklearn.model_selection import train_test_split

# Configuración desde variables de entorno
MYSQL_HOST = os.environ.get("MYSQL_HOST", "mysql")
MYSQL_PORT = os.environ.get("MYSQL_PORT", "3306")
MYSQL_USER = os.environ.get("MYSQL_USER", "ml_user")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "ml_password")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "ml_data")
MINIO_HOST = os.environ.get("MINIO_HOST", "minio")
MINIO_PORT = os.environ.get("MINIO_PORT", "9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "admin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "password123")
BUCKET_ARTEFACTOS = os.environ.get("MINIO_BUCKET_ARTEFACTOS", "artefactos")
API_DATOS_URL = os.environ.get("API_DATOS_URL", "http://api_datos:80")

MYSQL_CONN = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
MINIO_CLIENT = Minio(
    f"{MINIO_HOST}:{MINIO_PORT}",
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
ARCHIVO_MAPEO = "mapeo_variables.pkl"

COLUMNAS_API = [
    "Elevation", "Aspect", "Slope", "Horizontal_Distance_To_Hydrology",
    "Vertical_Distance_To_Hydrology", "Horizontal_Distance_To_Roadways",
    "Hillshade_9am", "Hillshade_Noon", "Hillshade_3pm", 
    "Horizontal_Distance_To_Fire_Points", "Wilderness_Area", "Soil_Type", "Cover_Type"
]

@dag(start_date=datetime(2023, 1, 1), schedule_interval="*/5 * * * *", catchup=False)
def etl_ml_pipeline():

    @task
    def extraer_api_a_raw():
        engine = create_engine(MYSQL_CONN)
        # Petición a la API en la red aislada (usando el nombre del contenedor 'api_datos' en el puerto 80)
        url = f"{API_DATOS_URL.rstrip('/')}/data?group_number=1" 
        try:
            response = requests.get(url)
            if response.status_code == 200:
                json_data = response.json()
                df_nuevo = pd.DataFrame(json_data["data"], columns=COLUMNAS_API)
                df_nuevo.to_sql('tabla_raw', con=engine, if_exists='append', index=False)
                return f"Batch extraído."
            return f"Error o límite alcanzado."
        except Exception as e:
            return f"Error: {e}"

    @task
    def limpiar_datos(dependencia):
        engine = create_engine(MYSQL_CONN)
        try:
            df = pd.read_sql("SELECT * FROM tabla_raw", con=engine)
            # Convertir a numérico lo que sea posible (ignora textos puros)
            df = df.apply(pd.to_numeric, errors='ignore')
            df = df.drop_duplicates()
            df = df.fillna(df.mean(numeric_only=True))
            df = df.fillna("Desconocido")
            df.to_sql('tabla_clean', con=engine, if_exists='replace', index=False)
            return "Limpieza completada"
        except:
            return "Esperando datos..."

    @task
    def procesar_y_codificar(dependencia):
        if "Esperando" in dependencia: return "Omitido"
        engine = create_engine(MYSQL_CONN)
        df = pd.read_sql("SELECT * FROM tabla_clean", con=engine)
        
        if not MINIO_CLIENT.bucket_exists(BUCKET_ARTEFACTOS):
            MINIO_CLIENT.make_bucket(BUCKET_ARTEFACTOS)

        diccionario_mapeo = {}
        try:
            respuesta = MINIO_CLIENT.get_object(BUCKET_ARTEFACTOS, ARCHIVO_MAPEO)
            diccionario_mapeo = pickle.loads(respuesta.read())
        except: pass

        columnas_texto = df.select_dtypes(include=['object']).columns
        for col in columnas_texto:
            if col not in diccionario_mapeo: diccionario_mapeo[col] = {}
            def codificar_valor(valor):
                if valor not in diccionario_mapeo[col]:
                    diccionario_mapeo[col][valor] = len(diccionario_mapeo[col])
                return diccionario_mapeo[col][valor]
            df[col] = df[col].apply(codificar_valor)

        MINIO_CLIENT.put_object(BUCKET_ARTEFACTOS, ARCHIVO_MAPEO, io.BytesIO(pickle.dumps(diccionario_mapeo)), len(pickle.dumps(diccionario_mapeo)))
        df.to_sql('tabla_procesada', con=engine, if_exists='replace', index=False)
        return "Codificación lista"

    @task
    def separar_train_test(dependencia):
        if "Omitido" in dependencia: return "Omitido"
        engine = create_engine(MYSQL_CONN)
        df = pd.read_sql("SELECT * FROM tabla_procesada", con=engine)
        
        if len(df) > 10:
            df_train, df_test = train_test_split(df, test_size=0.20, random_state=42)
            df_train.to_sql('tabla_train', con=engine, if_exists='replace', index=False)
            df_test.to_sql('tabla_test', con=engine, if_exists='replace', index=False)
        return "Tablas listas"

    separar_train_test(procesar_y_codificar(limpiar_datos(extraer_api_a_raw())))

dag_instancia = etl_ml_pipeline()