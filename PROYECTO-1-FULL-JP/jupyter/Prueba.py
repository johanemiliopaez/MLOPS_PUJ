import pandas as pd
from sqlalchemy import create_engine
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from minio import Minio
import pickle
import io

# 1. Extraer datos limpios y procesados de MySQL
print("Conectando a MySQL...")
engine = create_engine("mysql+pymysql://ml_user:ml_password@mysql:3306/ml_data")
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
minio_client = Minio("minio:9000", access_key="admin", secret_key="password123", secure=False)
if not minio_client.bucket_exists("modelos"):
    minio_client.make_bucket("modelos")

modelo_bytes = pickle.dumps(modelo)
minio_client.put_object("modelos", "modelo_rf.pkl", io.BytesIO(modelo_bytes), len(modelo_bytes))
print("¡Entrenamiento y guardado exitoso!")