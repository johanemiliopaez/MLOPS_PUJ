from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import requests
import json
import joblib
import os
import boto3
from sqlalchemy import create_engine, text
import mlflow
from mlflow.tracking import MlflowClient
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from mlflow.models.signature import infer_signature
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset

# --- CONFIGURACIÓN DE ENTORNO (SECRETS/CONFIGMAPS) ---
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "minio_admin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minio_password")
MINIO_ENDPOINT = os.getenv("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "mlflow-artifacts")

os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
os.environ["MLFLOW_S3_ENDPOINT_URL"] = MINIO_ENDPOINT
os.environ["AWS_DEFAULT_REGION"] = AWS_DEFAULT_REGION

# --- CONFIGURACIÓN GLOBAL ---
DB_URI = os.getenv("DB_URI", "postgresql+psycopg2://mlops_user:mlops_password@postgres:5432/mlops_db")
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
DATA_API_URL = os.getenv("DATA_API_URL", "http://data-api:80/data")
MODEL_NAME = os.getenv("MODEL_NAME", "RealEstate_Pricing_Model")

MINIO_ACCESS_KEY = AWS_ACCESS_KEY_ID
MINIO_SECRET_KEY = AWS_SECRET_ACCESS_KEY

GROUP_NUMBER = int(os.getenv("GROUP_NUMBER", "1"))

default_args = {
    'owner': 'mlops_team',
    'depends_on_past': False,
    'start_date': datetime(2026, 5, 20),
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

def _get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name='us-east-1'
    )

def _fetch_batch_from_api(**kwargs):
    try:
        response = requests.get(DATA_API_URL, params={'group_number': GROUP_NUMBER}, timeout=10)
        response.raise_for_status()
        batch_data = response.json()
        if not batch_data:
            raise ValueError("API retornó un lote vacío.")
        kwargs['ti'].xcom_push(key='fetched_data', value=batch_data)
    except Exception as e:
        print(f"Error crítico al consumir la API: {e}")
        raise

def _store_raw_batch(**kwargs):
    batch_id = kwargs['run_id']
    batch_data = kwargs['ti'].xcom_pull(key='fetched_data', task_ids='fetch_batch_from_api')
    
    if isinstance(batch_data, dict):
        for key, value in batch_data.items():
            if isinstance(value, list):
                batch_data = value
                break
                
    engine = create_engine(DB_URI)
    df_batch = pd.DataFrame(batch_data).replace({np.nan: None})
    records = []
    for _, row in df_batch.iterrows():
        records.append({
            'batch_id': batch_id,
            'status': 'loaded',
            'record_data': json.dumps(row.to_dict())
        })
    
    df_insert = pd.DataFrame(records)
    df_insert.to_sql('raw_data', con=engine, if_exists='append', index=False)
    print(f"Lote {batch_id} guardado con éxito en la tabla raw_data.")

def _validate_schema(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    query = f"SELECT record_data FROM raw_data WHERE batch_id = '{batch_id}'"
    raw_df = pd.read_sql(query, con=engine)
    
    parsed_records = [json.loads(x) if isinstance(x, str) else x for x in raw_df['record_data']]
    df = pd.json_normalize(parsed_records)
    
    required_cols = ['bed', 'bath', 'acre_lot', 'house_size', 'price', 'status', 'city', 'state']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        raise ValueError(f"Fallo de Esquema: Columnas faltantes obligatorias: {missing_cols}")
    print("Validación de esquema completada exitosamente.")

def _validate_data_quality(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    query = f"SELECT record_data FROM raw_data WHERE batch_id = '{batch_id}'"
    raw_df = pd.read_sql(query, con=engine)
    
    parsed_records = [json.loads(x) if isinstance(x, str) else x for x in raw_df['record_data']]
    df = pd.json_normalize(parsed_records)
    
    null_prices = df['price'].isnull().sum()
    if null_prices > (len(df) * 0.2):
        raise ValueError(f"Fallo de Calidad: Demasiados valores nulos en el target 'price' ({null_prices})")
    print("Validación de calidad de datos aprobada.")

def _detect_new_categories(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    
    curr_query = f"SELECT record_data FROM raw_data WHERE batch_id = '{batch_id}'"
    curr_raw = pd.read_sql(curr_query, con=engine)
    curr_parsed = [json.loads(x) if isinstance(x, str) else x for x in curr_raw['record_data']]
    curr_df = pd.json_normalize(curr_parsed)
    
    hist_query = f"SELECT features FROM clean_data WHERE raw_id NOT IN (SELECT id FROM raw_data WHERE batch_id = '{batch_id}')"
    hist_res = pd.read_sql(hist_query, con=engine)
    
    if not hist_res.empty:
        hist_parsed = [json.loads(x) if isinstance(x, str) else x for x in hist_res['features']]
        hist_df = pd.json_normalize(hist_parsed)
        for col in ['city', 'state']:
            if col in hist_df.columns and col in curr_df.columns:
                nuevas = set(curr_df[col].unique()) - set(hist_df[col].unique())
                if nuevas:
                    print(f"⚠️ Alerta: Nuevas categorías detectadas en '{col}': {nuevas}.")

def _detect_data_drift(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    
    ref_res = pd.read_sql(f"SELECT features FROM clean_data WHERE raw_id NOT IN (SELECT id FROM raw_data WHERE batch_id = '{batch_id}')", con=engine)
    curr_res = pd.read_sql(f"SELECT record_data FROM raw_data WHERE batch_id = '{batch_id}'", con=engine)
    
    if ref_res.empty or len(ref_res) < 100:
        kwargs['ti'].xcom_push(key='data_drift_detected', value=True)
        print("Historial insuficiente para calcular Data Drift. Forzando bandera True por arranque en frío.")
        return

    ref_parsed = [json.loads(x) if isinstance(x, str) else x for x in ref_res['features']]
    ref_df = pd.json_normalize(ref_parsed)
    
    curr_parsed = [json.loads(x) if isinstance(x, str) else x for x in curr_res['record_data']]
    curr_df = pd.json_normalize(curr_parsed)[['bed', 'bath', 'acre_lot', 'house_size', 'status', 'city', 'state']]
    
    drift_report = Report(metrics=[DataDriftPreset()])
    drift_report.run(reference_data=ref_df, current_data=curr_df)
    dataset_drift = drift_report.as_dict()["metrics"][0]["result"]["dataset_drift"]
    
    kwargs['ti'].xcom_push(key='data_drift_detected', value=dataset_drift)
    print(f"Análisis de Data Drift completado. ¿Existe drift?: {dataset_drift}")

def _preprocess_data(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    
    raw_df = pd.read_sql(f"SELECT id as raw_id, record_data FROM raw_data WHERE batch_id = '{batch_id}'", con=engine)
    parsed_records = [json.loads(x) if isinstance(x, str) else x for x in raw_df['record_data']]
    features_df = pd.json_normalize(parsed_records)
    features_df['raw_id'] = raw_df['raw_id']
    features_df.replace(['', 'None', 'null'], np.nan, inplace=True)
    features_df = features_df.dropna(subset=['price'])
    
    clean_records = []
    for _, row in features_df.iterrows():
        clean_records.append({
            'raw_id': row['raw_id'],
            'features': json.dumps({
                'bed': float(row.get('bed', 0) or 0),
                'bath': float(row.get('bath', 0) or 0),
                'acre_lot': float(row.get('acre_lot', 0) or 0),
                'house_size': float(row.get('house_size', 0) or 0),
                'status': str(row.get('status', 'unknown')),
                'city': str(row.get('city', 'unknown')),
                'state': str(row.get('state', 'unknown'))
            }),
            'price': float(row['price'])
        })
    pd.DataFrame(clean_records).to_sql('clean_data', con=engine, if_exists='append', index=False)
    print("Capa CLEAN DATA actualizada de forma segura.")

def _decide_training(**kwargs):
    drift_detected = kwargs['ti'].xcom_pull(key='data_drift_detected', task_ids='detect_data_drift')
    if drift_detected:
        kwargs['ti'].xcom_push(key='training_reason', value="Alta variabilidad detectada por distribución de datos.")
        return 'train_candidate_model'
    else:
        kwargs['ti'].xcom_push(key='training_reason', value="Distribución estable. No se requiere reentrenamiento.")
        return 'skip_training'

def _skip_training(**kwargs):
    reason = kwargs['ti'].xcom_pull(key='training_reason', task_ids='decide_training')
    kwargs['ti'].xcom_push(key='pipeline_outcome', value="SKIPPED")
    print(f"Entrenamiento omitido: {reason}")

def _train_candidate_model(**kwargs):
    engine = create_engine(DB_URI)
    clean_df = pd.read_sql("SELECT features, price FROM clean_data", con=engine)
    
    parsed_features = [json.loads(x) if isinstance(x, str) else x for x in clean_df['features']]
    X = pd.json_normalize(parsed_features)
    y = clean_df['price']
    
    preprocessor = ColumnTransformer(transformers=[
        ('num', SimpleImputer(strategy='median'), ['bed', 'bath', 'acre_lot', 'house_size']),
        ('cat', OneHotEncoder(handle_unknown='ignore'), ['status', 'city', 'state'])
    ])
    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('regressor', RandomForestRegressor(n_estimators=100, max_depth=15, random_state=42))
    ])
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    pipeline.fit(X_train, y_train)
    
    temp_model_path = f"/tmp/candidate_model_{kwargs['run_id']}.pkl"
    joblib.dump(pipeline, temp_model_path)
    
    s3_client = _get_s3_client()
    s3_key = f"temp_models/candidate_{kwargs['run_id']}.pkl"
    s3_client.upload_file(temp_model_path, MINIO_BUCKET, s3_key)
    print(f"Modelo candidato entrenado y subido a MinIO: s3://{MINIO_BUCKET}/{s3_key}")
    
    os.remove(temp_model_path)
    
    kwargs['ti'].xcom_push(key='s3_model_key', value=s3_key)
    kwargs['ti'].xcom_push(key='test_data', value={'X': X_test.to_dict(), 'y': y_test.to_list()})

def _evaluate_candidate_model(**kwargs):
    test_data = kwargs['ti'].xcom_pull(key='test_data', task_ids='train_candidate_model')
    s3_key = kwargs['ti'].xcom_pull(key='s3_model_key', task_ids='train_candidate_model')
    
    X_test = pd.DataFrame.from_dict(test_data['X'])
    y_test = pd.Series(test_data['y'])
    
    s3_client = _get_s3_client()
    temp_model_path = f"/tmp/eval_model_{kwargs['run_id']}.pkl"
    s3_client.download_file(MINIO_BUCKET, s3_key, temp_model_path)
    
    pipeline = joblib.load(temp_model_path)
    y_pred = pipeline.predict(X_test)
    
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))
    
    os.remove(temp_model_path)
    
    kwargs['ti'].xcom_push(key='candidate_metrics', value={'mae': mae, 'rmse': rmse, 'r2': r2})
    kwargs['ti'].xcom_push(key='candidate_mae', value=mae)
    print(f"Evaluación finalizada. MAE: {mae}")

def _register_candidate_in_mlflow(**kwargs):
    metrics = kwargs['ti'].xcom_pull(key='candidate_metrics', task_ids='evaluate_candidate_model')
    test_data = kwargs['ti'].xcom_pull(key='test_data', task_ids='train_candidate_model')
    s3_key = kwargs['ti'].xcom_pull(key='s3_model_key', task_ids='train_candidate_model')
    
    X_test = pd.DataFrame.from_dict(test_data['X'])
    
    s3_client = _get_s3_client()
    temp_model_path = f"/tmp/register_model_{kwargs['run_id']}.pkl"
    s3_client.download_file(MINIO_BUCKET, s3_key, temp_model_path)
    
    pipeline = joblib.load(temp_model_path)
    
    mlflow.set_tracking_uri(MLFLOW_URI)
    mlflow.set_experiment("RealEstate_Pricing")
    
    with mlflow.start_run(run_name=f"Run_{kwargs['run_id']}") as run:
        mlflow.log_metrics(metrics)
        
        signature = infer_signature(X_test, pipeline.predict(X_test))
        
        # EL TRUCO ESTÁ AQUÍ: Evitamos que intente usar pip freeze pasando las librerías a mano.
        mlflow.sklearn.log_model(
            pipeline, 
            "model", 
            signature=signature,
            pip_requirements=["scikit-learn==1.4.0", "pandas==2.1.4"] 
        )
        
        kwargs['ti'].xcom_push(key='active_run_id', value=run.info.run_id)
        print(f"Modelo registrado oficialmente en MLflow (ID: {run.info.run_id})")
        
    os.remove(temp_model_path)
    try:
        s3_client.delete_object(Bucket=MINIO_BUCKET, Key=s3_key)
        print(f"Objeto temporal {s3_key} eliminado de MinIO.")
    except Exception as e:
        print(f"Advertencia: No se pudo eliminar el objeto temporal en MinIO: {e}")

def _compare_with_production(**kwargs):
    candidate_mae = kwargs['ti'].xcom_pull(key='candidate_mae', task_ids='evaluate_candidate_model')
    mlflow.set_tracking_uri(MLFLOW_URI)
    client = MlflowClient()
    
    try:
        champion = client.get_model_version_by_alias(name=MODEL_NAME, alias="champion")
        champ_run = client.get_run(champion.run_id)
        champion_mae = champ_run.data.metrics.get("mae", float('inf'))
        kwargs['ti'].xcom_push(key='champion_mae', value=champion_mae)
        
        if candidate_mae < (champion_mae * 0.98):
            kwargs['ti'].xcom_push(key='promotion_decision', value='promote_model')
        else:
            kwargs['ti'].xcom_push(key='promotion_decision', value='reject_model')
    except mlflow.exceptions.RestException:
        print("Cold Start: No existe champion en producción. Aprobación directa.")
        kwargs['ti'].xcom_push(key='champion_mae', value=float('inf'))
        kwargs['ti'].xcom_push(key='promotion_decision', value='promote_model')

def _decide_promotion(**kwargs):
    return kwargs['ti'].xcom_pull(key='promotion_decision', task_ids='compare_with_production')

def _promote_model(**kwargs):
    run_id = kwargs['ti'].xcom_pull(key='active_run_id', task_ids='register_candidate_in_mlflow')
    mlflow.set_tracking_uri(MLFLOW_URI)
    client = MlflowClient()
    
    model_version = mlflow.register_model(f"runs:/{run_id}/model", MODEL_NAME)
    client.set_registered_model_alias(MODEL_NAME, "champion", model_version.version)
    kwargs['ti'].xcom_push(key='pipeline_outcome', value="PROMOTED")

def _reject_model(**kwargs):
    kwargs['ti'].xcom_push(key='pipeline_outcome', value="REJECTED")

def _notify_or_log_result(**kwargs):
    batch_id = kwargs['run_id']
    engine = create_engine(DB_URI)
    ti = kwargs['ti']
    
    outcome = ti.xcom_pull(key='pipeline_outcome', task_ids=['promote_model', 'reject_model', 'skip_training'])
    outcome = next(item for item in outcome if item is not None)
    reason = ti.xcom_pull(key='training_reason', task_ids='decide_training')
    c_mae = ti.xcom_pull(key='candidate_mae', task_ids='evaluate_candidate_model') or 0.0
    ch_mae = ti.xcom_pull(key='champion_mae', task_ids='compare_with_production') or 0.0
    if ch_mae == float('inf'): ch_mae = 0.0

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pipeline_history (
                id SERIAL PRIMARY KEY,
                batch_id VARCHAR(100),
                execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(50),
                reason TEXT,
                candidate_mae FLOAT,
                champion_mae FLOAT
            );
            INSERT INTO pipeline_history (batch_id, status, reason, candidate_mae, champion_mae)
            VALUES (:b_id, :status, :reason, :c_mae, :ch_mae);
        """), {"b_id": batch_id, "status": outcome, "reason": reason, "c_mae": c_mae, "ch_mae": ch_mae})


# --- DEFINICIÓN EXPLICITA DEL GRAFO DE AIRFLOW ---

with DAG('real_estate_mlops_pipeline',
         default_args=default_args,
         description='Pipeline declarativo de MLOps de 19 pasos',
         schedule_interval=timedelta(hours=1),
         catchup=False) as dag:

    start = EmptyOperator(task_id='start')
    
    fetch_batch = PythonOperator(task_id='fetch_batch_from_api', python_callable=_fetch_batch_from_api, provide_context=True)
    store_raw   = PythonOperator(task_id='store_raw_batch', python_callable=_store_raw_batch, provide_context=True)
    val_schema  = PythonOperator(task_id='validate_schema', python_callable=_validate_schema, provide_context=True)
    val_quality = PythonOperator(task_id='validate_data_quality', python_callable=_validate_data_quality, provide_context=True)
    det_cat     = PythonOperator(task_id='detect_new_categories', python_callable=_detect_new_categories, provide_context=True)
    det_drift   = PythonOperator(task_id='detect_data_drift', python_callable=_detect_data_drift, provide_context=True)
    preprocess  = PythonOperator(task_id='preprocess_data', python_callable=_preprocess_data, provide_context=True)
    
    decide_train = BranchPythonOperator(task_id='decide_training', python_callable=_decide_training, provide_context=True)
    skip_train   = PythonOperator(task_id='skip_training', python_callable=_skip_training, provide_context=True)
    train_model  = PythonOperator(task_id='train_candidate_model', python_callable=_train_candidate_model, provide_context=True)
    
    eval_model   = PythonOperator(task_id='evaluate_candidate_model', python_callable=_evaluate_candidate_model, provide_context=True)
    reg_mlflow   = PythonOperator(task_id='register_candidate_in_mlflow', python_callable=_register_candidate_in_mlflow, provide_context=True)
    comp_prod    = PythonOperator(task_id='compare_with_production', python_callable=_compare_with_production, provide_context=True)
    
    decide_prom  = BranchPythonOperator(task_id='decide_promotion', python_callable=_decide_promotion, provide_context=True)
    promo_model  = PythonOperator(task_id='promote_model', python_callable=_promote_model, provide_context=True)
    reje_model   = PythonOperator(task_id='reject_model', python_callable=_reject_model, provide_context=True)
    
    log_result   = PythonOperator(task_id='notify_or_log_result', python_callable=_notify_or_log_result, provide_context=True, trigger_rule='one_success')
    end          = EmptyOperator(task_id='end')

    # --- DEFINICIÓN DE DEPENDENCIAS ---
    start >> fetch_batch >> store_raw >> val_schema >> val_quality >> det_cat >> det_drift >> preprocess >> decide_train
    
    decide_train >> skip_train >> log_result
    decide_train >> train_model
    
    train_model >> eval_model >> reg_mlflow >> comp_prod >> decide_prom
    
    decide_prom >> promo_model >> log_result
    decide_prom >> reje_model >> log_result
    
    log_result >> end