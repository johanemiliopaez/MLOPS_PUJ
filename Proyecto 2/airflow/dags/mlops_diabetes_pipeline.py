import os
import sys
from datetime import datetime

from airflow.decorators import dag, task


PROJECT_SRC = os.getenv("PROJECT_SRC", "/opt/airflow/project/training/src")
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from pipeline import (  # noqa: E402
    build_clean_layer,
    ensure_dataset_present,
    ingest_raw_batch,
    split_train_val_test,
    train_and_register_model,
)


@dag(
    dag_id="mlops_diabetes_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["proyecto2", "mlops", "kubernetes"],
)
def mlops_diabetes_pipeline():
    """Pipeline diario de MLOps para predicción de readmisión por diabetes.

    Cada ejecución carga un nuevo lote (máx. 15.000 registros), valida
    calidad, construye la capa limpia, separa train/val/test, entrena
    LogisticRegression y RandomForest, registra todo en MLflow y promueve
    el mejor modelo si supera al campeón actual.
    """

    @task
    def validate_source_file() -> str:
        return ensure_dataset_present()

    @task
    def ingest_batch(_: str) -> dict:
        return ingest_raw_batch()

    @task
    def validate_batch(result: dict) -> dict:
        if result["rows_inserted"] == 0:
            raise ValueError("No hay nuevos registros para procesar")
        return result

    @task
    def transform_and_clean(_: dict) -> dict:
        return build_clean_layer()

    @task
    def split_dataset(_: dict) -> dict:
        return split_train_val_test()

    @task
    def train_and_promote(_: dict) -> dict:
        return train_and_register_model()

    source = validate_source_file()
    raw = ingest_batch(source)
    validated = validate_batch(raw)
    cleaned = transform_and_clean(validated)
    split = split_dataset(cleaned)
    train_and_promote(split)


dag_instance = mlops_diabetes_pipeline()
