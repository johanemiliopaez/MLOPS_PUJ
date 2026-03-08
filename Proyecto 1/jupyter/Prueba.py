import os
import pandas as pd
from sqlalchemy import create_engine
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from minio import Minio
import pickle
import io

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
MINIO_BUCKET_MODELOS = os.environ.get("MINIO_BUCKET_MODELOS", "modelos")

# 1. Extraer datos limpios y procesados de MySQL
print("Conectando a MySQL...")
MYSQL_CONN = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
engine = create_engine(MYSQL_CONN)
df_train = pd.read_sql("SELECT * FROM tabla_train", con=engine)
df_test = pd.read_sql("SELECT * FROM tabla_test", con=engine)

# 2. Preparar X e y (Cover_Type es nuestra etiqueta a predecir)
X_train = df_train.drop('Cover_Type', axis=1)
y_train = df_train['Cover_Type']
X_test = df_test.drop('Cover_Type', axis=1)
y_test = df_test['Cover_Type']

# 3. Entrenar Modelo
print("Entrenando RandomForest...")
modelo = RandomForestClassifier(n_estimators=100, random_state=42)
modelo.fit(X_train, y_train)

# 4. Evaluar
predicciones = modelo.predict(X_test)
precision = accuracy_score(y_test, predicciones)
print(f"Precisión en Test: {precision * 100:.2f}%")

# 5. Guardar modelo en MinIO
print("Guardando modelo en MinIO...")
minio_client = Minio(
    f"{MINIO_HOST}:{MINIO_PORT}",
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False,
)
if not minio_client.bucket_exists(MINIO_BUCKET_MODELOS):
    minio_client.make_bucket(MINIO_BUCKET_MODELOS)

modelo_bytes = pickle.dumps(modelo)
minio_client.put_object(MINIO_BUCKET_MODELOS, "modelo_rf.pkl", io.BytesIO(modelo_bytes), len(modelo_bytes))
print("¡Entrenamiento y guardado exitoso!")