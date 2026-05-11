from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
import mlflow
from mlflow.tracking import MlflowClient
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.impute import SimpleImputer
import json

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from mlflow.models.signature import infer_signature

# --- CONFIGURACIÓN GLOBAL ---
DB_URI = "postgresql+psycopg2://mlops_user:mlops_password@postgres:5432/mlops_db"
MLFLOW_URI = "http://mlflow:5000"
FILE_PATH = "/opt/airflow/data/diabetic_data.csv"
BATCH_SIZE = 15000
MODEL_NAME = "Diabetes_Readmission_Model"

default_args = {
    'owner': 'mlops_team',
    'depends_on_past': False,
    'start_date': datetime(2026, 5, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# --- FUNCIONES DE LAS TAREAS ---

def _load_incremental_raw(**kwargs):
    batch_id = kwargs['run_id'] 
    engine = create_engine(DB_URI)
    
    with engine.begin() as conn:
        # Aseguramos que la tabla exista con la estructura correcta, incluyendo el 'id' autoincremental
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_data (
                id SERIAL PRIMARY KEY,
                batch_id VARCHAR(255),
                source_file VARCHAR(255),
                status VARCHAR(50),
                record_data JSON
            );
        """))
        
        try:
            conn.execute(text("DELETE FROM raw_data WHERE batch_id = :b_id"), {"b_id": batch_id})
        except Exception:
            pass
        
        try:
            current_index = conn.execute(text("SELECT COUNT(*) FROM raw_data")).scalar() or 0
        except Exception:
            current_index = 0

    df_batch = pd.read_csv(FILE_PATH, skiprows=range(1, current_index + 1), nrows=BATCH_SIZE)
    
    if df_batch.empty:
        print("No hay más datos para cargar.")
        return None

    df_batch = df_batch.replace({np.nan: None})
    
    records = []
    for _, row in df_batch.iterrows():
        records.append({
            'batch_id': batch_id,
            'source_file': 'diabetic_data.csv',
            'status': 'loaded',
            'record_data': json.dumps(row.to_dict()) 
        })
    
    df_insert = pd.DataFrame(records)
    # index=False evita que Pandas intente insertar su propio índice numérico, 
    # dejando que PostgreSQL use el SERIAL para llenar la columna 'id'
    df_insert.to_sql('raw_data', con=engine, if_exists='append', index=False)
    print(f"Lote {batch_id} insertado con {len(df_batch)} registros. Índice anterior: {current_index}")

def _quality_check(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM raw_data WHERE batch_id = :b_id"), {"b_id": batch_id}).scalar()
    
    if count == 0:
        raise ValueError(f"Fallo de calidad: El lote {batch_id} está vacío.")
    print(f"Quality check superado. Lote {batch_id} tiene {count} registros.")

def _process_and_clean(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    
    with engine.begin() as conn:
        # Aseguramos que la tabla destino también exista
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS clean_data (
                id SERIAL PRIMARY KEY,
                raw_id INTEGER,
                features JSON,
                readmitted_binary INTEGER
            );
        """))
        
        try:
            conn.execute(text("""
                DELETE FROM clean_data 
                WHERE raw_id IN (SELECT id FROM raw_data WHERE batch_id = :b_id)
            """), {"b_id": batch_id})
        except Exception:
            pass
            
    # Ahora la consulta "SELECT id as raw_id..." funcionará perfectamente
    query = f"SELECT id as raw_id, record_data FROM raw_data WHERE batch_id = '{batch_id}'"
    raw_df = pd.read_sql(query, con=engine)
    
    if raw_df.empty:
        print("No hay datos crudos para procesar en este batch.")
        return

    features_df = pd.json_normalize(raw_df['record_data'])
    features_df['raw_id'] = raw_df['raw_id']
    
    features_df.replace('?', np.nan, inplace=True)
    cols_to_drop = ['weight', 'max_glu_serum', 'A1Cresult', 'payer_code', 'medical_specialty']
    features_df.drop(columns=[c for c in cols_to_drop if c in features_df.columns], inplace=True)
    
    features_df['readmitted_binary'] = features_df['readmitted'].apply(lambda x: 0 if x == 'NO' else 1)
    features_df = features_df.replace({np.nan: None})
    
    clean_records = []
    for _, row in features_df.iterrows():
        target = row['readmitted_binary']
        raw_id = row['raw_id']
        feat_dict = row.drop(labels=['readmitted', 'readmitted_binary', 'raw_id', 'encounter_id', 'patient_nbr']).to_dict()
        
        clean_records.append({
            'raw_id': raw_id,
            'features': json.dumps(feat_dict),
            'readmitted_binary': target
        })
        
    df_clean_insert = pd.DataFrame(clean_records)
    df_clean_insert.to_sql('clean_data', con=engine, if_exists='append', index=False)
    print("Datos procesados e insertados en clean_data de forma segura.")
    
def _train_and_log_model():
    engine = create_engine(DB_URI)
    clean_df = pd.read_sql("SELECT features, readmitted_binary FROM clean_data", con=engine)
    
    if len(clean_df) < 100:
        print("Insuficientes datos para entrenar.")
        return

    X_full = pd.json_normalize(clean_df['features'])
    y = clean_df['readmitted_binary']
    
    ui_features = [
        'age', 'time_in_hospital', 'num_lab_procedures', 'num_procedures', 
        'num_medications', 'number_outpatient', 'number_emergency', 
        'number_inpatient', 'number_diagnoses', 'change', 'diabetesMed'
    ]
    
    X = X_full[ui_features]
    
    categorical_cols = ['age', 'change', 'diabetesMed']
    numeric_cols = [col for col in ui_features if col not in categorical_cols]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', SimpleImputer(strategy='median'), numeric_cols),
            ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_cols)
        ])
    
    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42))
    ])
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("Diabetes_Readmission")
    
    with mlflow.start_run() as run:
        pipeline.fit(X_train, y_train)
        y_pred = pipeline.predict(X_test)
        f1 = f1_score(y_test, y_pred)
        
        mlflow.log_param("n_estimators", 100)
        mlflow.log_metric("f1_score", f1)
        
        signature = infer_signature(X_train, pipeline.predict(X_train))
        mlflow.sklearn.log_model(pipeline, "model", signature=signature)
        print(f"Modelo entrenado con Pipeline. F1-Score: {f1}")
        
def _promote_champion_model():
    mlflow.set_tracking_uri(MLFLOW_URI)
    client = MlflowClient()
    
    experiment = client.get_experiment_by_name("Diabetes_Readmission")
    if not experiment:
        return
        
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["metrics.f1_score DESC"],
        max_results=1
    )
    
    if not runs:
        return
        
    best_run = runs[0]
    best_run_id = best_run.info.run_id
    best_f1 = best_run.data.metrics.get("f1_score", 0)
    
    try:
        model_version = mlflow.register_model(f"runs:/{best_run_id}/model", MODEL_NAME)
        client.set_registered_model_alias(MODEL_NAME, "champion", model_version.version)
        print(f"Modelo versión {model_version.version} promovido a champion (F1: {best_f1})")
    except Exception as e:
        print(f"Error al registrar/promover el modelo: {e}")

# --- DEFINICIÓN DEL DAG ---

with DAG('diabetes_mlops_pipeline',
         default_args=default_args,
         description='Pipeline de MLOps para predecir readmisiones de diabetes',
         schedule_interval=timedelta(days=1),
         catchup=False) as dag:

    load_raw = PythonOperator(
        task_id='load_incremental_raw',
        python_callable=_load_incremental_raw,
        provide_context=True
    )

    check_quality = PythonOperator(
        task_id='quality_check',
        python_callable=_quality_check,
        provide_context=True
    )

    process_clean = PythonOperator(
        task_id='process_and_clean',
        python_callable=_process_and_clean,
        provide_context=True
    )

    train_log = PythonOperator(
        task_id='train_and_log_model',
        python_callable=_train_and_log_model
    )

    promote_model = PythonOperator(
        task_id='promote_champion_model',
        python_callable=_promote_champion_model
    )

    load_raw >> check_quality >> process_clean >> train_log >> promote_model