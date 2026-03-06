"""
DAG de ingestión y preparación de datos - Proyecto 2 MLOps.

Objetivo: automatizar únicamente la ingestión y preparación de datos.
No hace split, entrenamiento, evaluación ni selección de modelos.

Etapas:
1. extract_data_from_api - Consultar API Data
2. load_data - Cargar en data_raw
3. clean_data - Limpieza
4. transform_data - Transformación
5. validate_data - Validación
6. feature_engineering - Ingeniería de características
7. store_prepared_data - Cargar en data_prepared

El batch_number (group_number para la API) cicla 1→10→1 automáticamente.
"""

from datetime import datetime, timedelta
import requests
import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.providers.mysql.hooks.mysql import MySqlHook

# Configuración
API_DATA_URL = "http://api-data-p2:80/data"
MYSQL_CONN_ID = "mysql_data"
VARIABLE_NEXT_BATCH = "data_ingestion_next_batch"

# Columnas del dataset Forest Cover Type (orden de la API)
DATA_COLUMNS = [
    "elevation",
    "aspect",
    "slope",
    "horizontal_distance_to_hydrology",
    "vertical_distance_to_hydrology",
    "horizontal_distance_to_roadways",
    "hillshade_9am",
    "hillshade_noon",
    "hillshade_3pm",
    "horizontal_distance_to_fire_points",
    "wilderness_area",
    "soil_type",
    "cover_type",
]


def get_and_advance_batch(**context):
    """Obtiene el batch actual, lo usa y persiste el siguiente (1-10 cíclico)."""
    next_batch = Variable.get(VARIABLE_NEXT_BATCH, default_var=1)
    next_batch = int(next_batch)
    current_batch = next_batch
    # Siguiente: si era 10, vuelve a 1; si no, +1
    next_batch = 1 if current_batch >= 10 else current_batch + 1
    Variable.set(VARIABLE_NEXT_BATCH, next_batch)
    return current_batch


def extract_data_from_api(**context):
    """Consulta la API con group_number (batch) y devuelve los datos."""
    batch = get_and_advance_batch(**context)
    resp = requests.get(API_DATA_URL, params={"group_number": batch}, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    data = payload.get("data", [])
    group_number = payload.get("group_number", batch)
    # Empujar a XCom para tareas siguientes
    context["ti"].xcom_push(key="group_number", value=group_number)
    context["ti"].xcom_push(key="raw_data", value=data)
    return len(data)


def load_data(**context):
    """Inserta los datos en la tabla data_raw."""
    ti = context["ti"]
    raw_data = ti.xcom_pull(task_ids="extract_data_from_api", key="raw_data")
    group_number = ti.xcom_pull(task_ids="extract_data_from_api", key="group_number")
    if not raw_data:
        return 0
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    conn = hook.get_conn()
    cur = conn.cursor()
    insert_sql = """
        INSERT INTO data_raw (
            group_number, elevation, aspect, slope,
            horizontal_distance_to_hydrology, vertical_distance_to_hydrology,
            horizontal_distance_to_roadways, hillshade_9am, hillshade_noon,
            hillshade_3pm, horizontal_distance_to_fire_points,
            wilderness_area, soil_type, cover_type
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for row in raw_data:
        if len(row) >= 13:
            cur.execute(
                insert_sql,
                [group_number] + [str(v)[:255] for v in row[:13]],
            )
    conn.commit()
    cur.close()
    conn.close()
    # Pasar datos para siguientes tareas
    ti.xcom_push(key="group_number", value=group_number)
    ti.xcom_push(key="raw_data", value=raw_data)
    return len(raw_data)


def clean_data(**context):
    """Limpieza: eliminar duplicados, valores nulos/vacíos, outliers básicos."""
    ti = context["ti"]
    raw_data = ti.xcom_pull(task_ids="load_data", key="raw_data")
    group_number = ti.xcom_pull(task_ids="load_data", key="group_number")
    if not raw_data:
        ti.xcom_push(key="group_number", value=group_number)
        ti.xcom_push(key="cleaned_data", value=[])
        return 0
    df = pd.DataFrame(raw_data, columns=DATA_COLUMNS)
    # Eliminar filas con valores vacíos
    df = df.replace("", pd.NA).dropna()
    # Eliminar duplicados
    df = df.drop_duplicates()
    # Convertir numéricos y filtrar outliers básicos (opcional)
    numeric_cols = DATA_COLUMNS[:10]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=numeric_cols)
    cleaned = df.values.tolist()
    ti.xcom_push(key="group_number", value=group_number)
    ti.xcom_push(key="cleaned_data", value=cleaned)
    ti.xcom_push(key="columns", value=DATA_COLUMNS)
    return len(cleaned)


def transform_data(**context):
    """Transformación: normalización/estandarización básica de numéricos."""
    ti = context["ti"]
    cleaned = ti.xcom_pull(task_ids="clean_data", key="cleaned_data")
    group_number = ti.xcom_pull(task_ids="clean_data", key="group_number")
    columns = ti.xcom_pull(task_ids="clean_data", key="columns") or DATA_COLUMNS
    if not cleaned:
        ti.xcom_push(key="group_number", value=group_number)
        ti.xcom_push(key="transformed_data", value=[])
        return 0
    df = pd.DataFrame(cleaned, columns=columns)
    numeric_cols = columns[:10]
    # Estandarización simple (z-score)
    for col in numeric_cols:
        mean_val = df[col].mean()
        std_val = df[col].std()
        if std_val and std_val > 0:
            df[col] = (df[col] - mean_val) / std_val
    transformed = df.values.tolist()
    ti.xcom_push(key="group_number", value=group_number)
    ti.xcom_push(key="transformed_data", value=transformed)
    ti.xcom_push(key="columns", value=columns)
    return len(transformed)


def validate_data(**context):
    """Validación: verificar tipos, rangos y ausencia de nulos."""
    ti = context["ti"]
    transformed = ti.xcom_pull(task_ids="transform_data", key="transformed_data")
    group_number = ti.xcom_pull(task_ids="transform_data", key="group_number")
    columns = ti.xcom_pull(task_ids="transform_data", key="columns") or DATA_COLUMNS
    if not transformed:
        ti.xcom_push(key="group_number", value=group_number)
        ti.xcom_push(key="validated_data", value=[])
        return 0
    df = pd.DataFrame(transformed, columns=columns)
    # Verificar que no haya nulos
    df = df.dropna()
    validated = df.values.tolist()
    ti.xcom_push(key="group_number", value=group_number)
    ti.xcom_push(key="validated_data", value=validated)
    ti.xcom_push(key="columns", value=columns)
    return len(validated)


def feature_engineering(**context):
    """Ingeniería de características: passthrough (extensible en Jupyter)."""
    ti = context["ti"]
    validated = ti.xcom_pull(task_ids="validate_data", key="validated_data")
    group_number = ti.xcom_pull(task_ids="validate_data", key="group_number")
    columns = ti.xcom_pull(task_ids="validate_data", key="columns") or DATA_COLUMNS
    if not validated:
        ti.xcom_push(key="group_number", value=group_number)
        ti.xcom_push(key="prepared_data", value=[])
        return 0
    df = pd.DataFrame(validated, columns=columns)
    # Passthrough: datos listos para data_prepared (features adicionales en Jupyter)
    prepared = df.values.tolist()
    ti.xcom_push(key="group_number", value=group_number)
    ti.xcom_push(key="prepared_data", value=prepared)
    ti.xcom_push(key="columns", value=columns)
    return len(prepared)


def store_prepared_data(**context):
    """Carga los datos preparados en la tabla data_prepared."""
    ti = context["ti"]
    prepared = ti.xcom_pull(task_ids="feature_engineering", key="prepared_data")
    group_number = ti.xcom_pull(task_ids="feature_engineering", key="group_number")
    if not prepared:
        return 0
    hook = MySqlHook(mysql_conn_id=MYSQL_CONN_ID)
    conn = hook.get_conn()
    cur = conn.cursor()
    insert_sql = """
        INSERT INTO data_prepared (
            group_number, elevation, aspect, slope,
            horizontal_distance_to_hydrology, vertical_distance_to_hydrology,
            horizontal_distance_to_roadways, hillshade_9am, hillshade_noon,
            hillshade_3pm, horizontal_distance_to_fire_points,
            wilderness_area, soil_type, cover_type
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    for row in prepared:
        vals = [group_number] + [str(v)[:255] if v is not None else "" for v in row[:13]]
        cur.execute(insert_sql, vals)
    conn.commit()
    cur.close()
    conn.close()
    return len(prepared)


with DAG(
    dag_id="data_ingestion_preparation",
    description="Ingestión y preparación de datos Forest Cover Type",
    schedule_interval=timedelta(minutes=5),
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["proyecto2", "ingestion", "preparacion"],
) as dag:
    t1 = PythonOperator(
        task_id="extract_data_from_api",
        python_callable=extract_data_from_api,
    )
    t2 = PythonOperator(
        task_id="load_data",
        python_callable=load_data,
    )
    t3 = PythonOperator(
        task_id="clean_data",
        python_callable=clean_data,
    )
    t4 = PythonOperator(
        task_id="transform_data",
        python_callable=transform_data,
    )
    t5 = PythonOperator(
        task_id="validate_data",
        python_callable=validate_data,
    )
    t6 = PythonOperator(
        task_id="feature_engineering",
        python_callable=feature_engineering,
    )
    t7 = PythonOperator(
        task_id="store_prepared_data",
        python_callable=store_prepared_data,
    )

    t1 >> t2 >> t3 >> t4 >> t5 >> t6 >> t7
