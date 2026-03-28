"""
Script para cargar penguins.csv en PostgreSQL (tabla data_raw).
Ejecutar una vez antes del entrenamiento (opcional; el notebook también carga desde CSV si la tabla está vacía).
"""
import os
import pandas as pd
from sqlalchemy import create_engine

PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_USER = os.environ.get("POSTGRES_USER", "admin")  # O el usuario que hayas dejado
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "admin")
PG_DB = os.environ.get("POSTGRES_DB", "data_db") # Leemos la variable de entorno que pusimos en el compose
CONN_RAW = f"postgresql://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"

if __name__ == "__main__":
    csv_path = "/home/jovyan/data/penguins.csv"
    if not os.path.exists(csv_path):
        csv_path = "Dataset/penguins.csv"
    if not os.path.exists(csv_path):
        print("No se encontró penguins.csv")
        exit(1)

    df = pd.read_csv(csv_path)
    engine = create_engine(CONN)
    df.to_sql("data_raw", engine, if_exists="replace", index=False)
    print(f"Cargados {len(df)} registros en data_raw")
