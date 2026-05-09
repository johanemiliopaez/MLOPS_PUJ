import os
import sys
from datetime import datetime

from airflow.decorators import dag, task


PROJECT_SRC = os.getenv("PROJECT_SRC", "/opt/airflow/project/training/src")
if PROJECT_SRC not in sys.path:
    sys.path.insert(0, PROJECT_SRC)

from pipeline import build_clean_layer, ensure_dataset_present, ingest_raw_batch, train_and_register_model  # noqa: E402


@dag(
    dag_id="mlops_diabetes_pipeline",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["proyecto2", "mlops", "kubernetes"],
)
def mlops_diabetes_pipeline():
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
    def train_and_promote(_: dict) -> dict:
        return train_and_register_model()

    train_and_promote(transform_and_clean(validate_batch(ingest_batch(validate_source_file()))))


dag_instance = mlops_diabetes_pipeline()
