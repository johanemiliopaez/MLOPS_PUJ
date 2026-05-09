import json
import os
import re
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import mlflow
import pandas as pd
import requests
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert


DEFAULT_FEATURE_COLUMNS = [
    "race",
    "gender",
    "age",
    "admission_type_id",
    "discharge_disposition_id",
    "admission_source_id",
    "time_in_hospital",
    "num_lab_procedures",
    "num_procedures",
    "num_medications",
    "number_outpatient",
    "number_emergency",
    "number_inpatient",
    "diag_1",
    "diag_2",
    "diag_3",
    "A1Cresult",
    "insulin",
    "change",
    "diabetesMed",
]

ID_COLUMNS = {"encounter_id", "patient_nbr"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_database_uri(db_name: str | None = None) -> str:
    user = get_env("POSTGRES_USER", "mlops")
    password = get_env("POSTGRES_PASSWORD", "mlops123")
    host = get_env("POSTGRES_HOST", "postgres")
    port = get_env("POSTGRES_PORT", "5432")
    database = db_name or get_env("DATA_DB", "mlops_data")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def get_engine(db_name: str | None = None):
    return create_engine(get_database_uri(db_name), future=True)


def _extract_gdrive_id(url: str) -> str | None:
    """Extrae el id de un archivo de Google Drive a partir de varias formas de URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "id" in qs and qs["id"]:
        return qs["id"][0]
    match = re.search(r"/d/([A-Za-z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None


def _download_from_gdrive(url: str, destination: Path) -> None:
    """Descarga un archivo grande de Google Drive resolviendo el confirm token.

    Implementa el flujo descrito en el enunciado (`confirm={{VALUE}}`) y, como
    primera opción, usa `gdown` que ya conoce todas las variantes del proceso.
    """
    file_id = _extract_gdrive_id(url)
    try:
        import gdown  # type: ignore[import-not-found]

        if file_id:
            gdown.download(id=file_id, output=str(destination), quiet=True, fuzzy=True)
        else:
            gdown.download(url=url, output=str(destination), quiet=True, fuzzy=True)
        return
    except Exception:
        pass

    session = requests.Session()
    response = session.get(url, params={"confirm": "t"}, stream=True, timeout=180)
    response.raise_for_status()

    token = None
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            token = value
            break
    if token is None and "text/html" in response.headers.get("Content-Type", ""):
        match = re.search(r"confirm=([0-9A-Za-z_-]+)", response.text)
        if match:
            token = match.group(1)

    if token:
        params = {"confirm": token}
        if file_id:
            params["id"] = file_id
        response = session.get(url, params=params, stream=True, timeout=300)
        response.raise_for_status()

    with destination.open("wb") as fh:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                fh.write(chunk)


def _validate_csv(path: Path) -> None:
    """Valida que el archivo descargado sea un CSV legible y no una página HTML.

    Google Drive devuelve HTML cuando el archivo es grande y no se aceptó el
    aviso de virus scan. Si eso pasó, abortamos en vez de continuar con un
    DataFrame inservible.
    """
    if path.stat().st_size < 1024:
        raise RuntimeError(f"Dataset descargado demasiado pequeño ({path.stat().st_size} bytes); revisa DATASET_URL")

    with path.open("rb") as fh:
        head = fh.read(2048).lower()
    if b"<html" in head or b"<!doctype html" in head:
        raise RuntimeError(
            "El dataset descargado parece ser una página HTML de Google Drive (confirm token). "
            "Verifica permisos del enlace o reintenta."
        )

    pd.read_csv(path, nrows=5)


def ensure_dataset_present() -> str:
    """Descarga el dataset si no existe localmente.

    Cumple el flujo descrito en la sección 3.1 del enunciado:
    crea el directorio destino, evita re-descargar si el archivo ya existe,
    y resuelve el `confirm={{VALUE}}` propio de Google Drive para archivos
    grandes.
    """
    dataset_path = Path(get_env("DATASET_PATH", "/opt/project/data/Diabetes.csv"))
    dataset_url = get_env("DATASET_URL", "")
    dataset_path.parent.mkdir(parents=True, exist_ok=True)

    if dataset_path.exists() and dataset_path.stat().st_size > 1024:
        return str(dataset_path)

    if not dataset_url:
        raise FileNotFoundError(f"Dataset not found at {dataset_path} and DATASET_URL is empty")

    _download_from_gdrive(dataset_url, dataset_path)
    _validate_csv(dataset_path)
    return str(dataset_path)


def get_tables(engine):
    metadata = MetaData()
    raw_table = Table("raw_data", metadata, autoload_with=engine)
    clean_table = Table("clean_data", metadata, autoload_with=engine)
    inference_table = Table("inference_logs", metadata, autoload_with=engine)
    return raw_table, clean_table, inference_table


def get_next_batch_number(engine, raw_table: Table) -> int:
    with engine.begin() as connection:
        current = connection.execute(select(func.max(raw_table.c.batch_id))).scalar()
    return int(current or 0) + 1


def read_source_batch(batch_id: int, batch_size: int) -> pd.DataFrame:
    source_path = ensure_dataset_present()
    df = pd.read_csv(source_path)
    start = (batch_id - 1) * batch_size
    end = start + batch_size
    batch = df.iloc[start:end].copy()
    return batch


def ingest_raw_batch(batch_size: int | None = None) -> dict[str, Any]:
    batch_size = batch_size or int(get_env("BATCH_SIZE", "15000"))
    source_path = ensure_dataset_present()
    engine = get_engine()
    raw_table, _, _ = get_tables(engine)
    batch_id = get_next_batch_number(engine, raw_table)
    batch_df = read_source_batch(batch_id=batch_id, batch_size=batch_size)

    if batch_df.empty:
        return {"batch_id": batch_id, "rows_inserted": 0, "status": "no-more-data"}

    payload_df = batch_df.fillna(value=pd.NA).replace({pd.NA: None})
    load_timestamp = utc_now()
    records = []
    for _, row in payload_df.iterrows():
        payload = {k: row[k] for k in payload_df.columns}
        row_hash = pd.util.hash_pandas_object(pd.Series(payload), index=False).astype(str).iloc[0]
        records.append(
            {
                "batch_id": batch_id,
                "source_file": source_path,
                "load_timestamp": load_timestamp,
                "status": "loaded",
                "row_hash": row_hash,
                "payload": payload,
            }
        )

    with engine.begin() as connection:
        stmt = insert(raw_table).values(records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["row_hash"])
        result = connection.execute(stmt)

    return {
        "batch_id": batch_id,
        "rows_inserted": int(result.rowcount or 0),
        "status": "loaded",
    }


def normalize_target(series: pd.Series) -> pd.Series:
    normalized = series.astype(str).str.strip()
    if normalized.nunique() <= 2:
        first = normalized.dropna().iloc[0]
        return normalized.eq(first).astype(int)

    if {"<30", ">30", "NO"}.issubset(set(normalized.unique())):
        return normalized.eq("<30").astype(int)

    return normalized.factorize()[0]


def build_clean_layer(target_column: str | None = None) -> dict[str, Any]:
    target_column = target_column or get_env("TARGET_COLUMN", "readmitted")
    engine = get_engine()
    raw_table, clean_table, _ = get_tables(engine)

    with engine.begin() as connection:
        raw_rows = connection.execute(select(raw_table)).mappings().all()

    if not raw_rows:
        return {"rows_written": 0, "status": "raw-empty"}

    raw_df = pd.DataFrame([row["payload"] for row in raw_rows])
    if target_column not in raw_df.columns:
        raise KeyError(f"Target column '{target_column}' not present in source dataset")

    raw_df = raw_df.drop_duplicates()
    raw_df = raw_df.replace("?", pd.NA)
    raw_df.columns = [str(col).strip() for col in raw_df.columns]

    feature_candidates = [col for col in DEFAULT_FEATURE_COLUMNS if col in raw_df.columns]
    if not feature_candidates:
        feature_candidates = [col for col in raw_df.columns if col not in ID_COLUMNS and col != target_column]

    cleaned = raw_df[feature_candidates].copy()
    for column in cleaned.columns:
        cleaned[column] = cleaned[column].apply(lambda value: value.strip() if isinstance(value, str) else value)

    target = normalize_target(raw_df[target_column])
    processed_at = utc_now()
    clean_records = []
    for idx, row in cleaned.iterrows():
        payload = row.where(pd.notna(row), None).to_dict()
        payload_text = json.dumps(payload, sort_keys=True)
        row_hash = pd.util.hash_pandas_object(pd.Series([payload_text, int(target.iloc[idx])]), index=False).astype(str).iloc[0]
        clean_records.append(
            {
                "source_batch_id": None,
                "processed_at": processed_at,
                "row_hash": row_hash,
                "features": payload,
                "target_value": str(int(target.iloc[idx])),
            }
        )

    with engine.begin() as connection:
        stmt = insert(clean_table).values(clean_records)
        stmt = stmt.on_conflict_do_nothing(index_elements=["row_hash"])
        result = connection.execute(stmt)

    return {
        "rows_written": int(result.rowcount or 0),
        "feature_columns": feature_candidates,
        "target_column": target_column,
        "status": "clean-built",
    }


def load_clean_dataframe() -> tuple[pd.DataFrame, pd.Series]:
    engine = get_engine()
    _, clean_table, _ = get_tables(engine)
    with engine.begin() as connection:
        rows = connection.execute(select(clean_table)).mappings().all()

    if not rows:
        raise RuntimeError("clean_data table is empty; execute build_clean_layer first")

    features = pd.DataFrame([row["features"] for row in rows])
    target = pd.Series([int(row["target_value"]) for row in rows], name="target")
    return features, target


def split_train_val_test(
    test_size: float = 0.15, val_size: float = 0.15, random_state: int = 42
) -> dict[str, Any]:
    """Particiona clean_data en train/val/test estratificado.

    Devuelve un resumen con tamaños y el balance de clases. Los splits se
    materializan en memoria en el llamador para evitar serializar DataFrames
    grandes vía XCom. Esta función existe como tarea explícita del DAG para
    cumplir con el requisito de separación visible de datos.
    """
    features, target = load_clean_dataframe()
    if target.nunique() < 2:
        raise RuntimeError("Target column must contain at least two classes")

    x_train, x_temp, y_train, y_temp = train_test_split(
        features, target, test_size=test_size + val_size, random_state=random_state, stratify=target
    )
    relative_test = test_size / (test_size + val_size)
    x_val, x_test, y_val, y_test = train_test_split(
        x_temp, y_temp, test_size=relative_test, random_state=random_state, stratify=y_temp
    )
    return {
        "train_rows": int(len(x_train)),
        "val_rows": int(len(x_val)),
        "test_rows": int(len(x_test)),
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_val": float(y_val.mean()),
        "positive_rate_test": float(y_test.mean()),
        "feature_count": int(features.shape[1]),
    }


def build_candidate_models(numeric_features: list[str], categorical_features: list[str]) -> dict[str, Pipeline]:
    numeric_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_features),
            ("cat", categorical_transformer, categorical_features),
        ]
    )

    return {
        "LogisticRegression": Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", LogisticRegression(max_iter=1500)),
            ]
        ),
        "RandomForest": Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", RandomForestClassifier(n_estimators=300, random_state=42)),
            ]
        ),
    }


def configure_mlflow() -> MlflowClient:
    tracking_uri = get_env("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(tracking_uri)
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = get_env("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
    os.environ["AWS_ACCESS_KEY_ID"] = get_env("AWS_ACCESS_KEY_ID", "minioadmin")
    os.environ["AWS_SECRET_ACCESS_KEY"] = get_env("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    os.environ["AWS_DEFAULT_REGION"] = get_env("AWS_DEFAULT_REGION", "us-east-1")
    experiment_name = get_env("MLFLOW_EXPERIMENT_NAME", "Proyecto2-Diabetes")
    mlflow.set_experiment(experiment_name)
    return MlflowClient(tracking_uri=tracking_uri)


def get_current_champion_metric(
    client: MlflowClient, model_name: str, alias: str, metric_key: str
) -> float | None:
    """Recupera la métrica principal del modelo productivo actual.

    Si no existe campeón previo (primera corrida) devuelve None y la
    promoción es automática. Soporta tanto MLflow con aliases como con
    stages (`Production`).
    """
    try:
        version = client.get_model_version_by_alias(model_name, alias)
    except Exception:
        try:
            versions = client.search_model_versions(f"name='{model_name}'")
            production = [v for v in versions if getattr(v, "current_stage", "") == "Production"]
            version = sorted(production, key=lambda item: int(item.version), reverse=True)[0] if production else None
        except Exception:
            version = None

    if version is None:
        return None

    try:
        run = client.get_run(version.run_id)
        return float(run.data.metrics.get(metric_key)) if metric_key in run.data.metrics else None
    except Exception:
        return None


def register_best_model(
    client: MlflowClient,
    run_id: str,
    model_name: str,
    candidate_metric: float,
    metric_key: str = "val_recall",
) -> dict[str, Any]:
    """Registra una versión nueva y la promueve a productivo solo si supera al campeón actual.

    Esto cumple el requisito del enunciado de comparar el desempeño contra
    modelos anteriores antes de promover. Si no hay campeón previo, se
    promueve directamente.
    """
    model_uri = f"runs:/{run_id}/model"
    model_version = mlflow.register_model(model_uri=model_uri, name=model_name)
    alias = get_env("MLFLOW_MODEL_ALIAS", "champion")

    previous_metric = get_current_champion_metric(client, model_name, alias, metric_key)
    promoted = previous_metric is None or candidate_metric >= previous_metric

    state = "registered-only"
    if promoted:
        try:
            client.set_registered_model_alias(model_name, alias, model_version.version)
            state = alias
        except Exception:
            client.transition_model_version_stage(
                model_name,
                model_version.version,
                stage="Production",
                archive_existing_versions=True,
            )
            state = "Production"

    return {
        "model_name": model_name,
        "model_version": model_version.version,
        "state": state,
        "promoted": promoted,
        "candidate_metric": candidate_metric,
        "previous_champion_metric": previous_metric,
        "selection_metric": metric_key,
    }


def train_and_register_model() -> dict[str, Any]:
    features, target = load_clean_dataframe()
    if target.nunique() < 2:
        raise RuntimeError("Target column must contain at least two classes")

    numeric_features = [col for col in features.columns if pd.api.types.is_numeric_dtype(features[col])]
    categorical_features = [col for col in features.columns if col not in numeric_features]
    models = build_candidate_models(numeric_features, categorical_features)
    client = configure_mlflow()
    model_name = get_env("MLFLOW_MODEL_NAME", "DiabetesReadmissionModel")

    x_train, x_temp, y_train, y_temp = train_test_split(
        features, target, test_size=0.3, random_state=42, stratify=target
    )
    x_val, x_test, y_val, y_test = train_test_split(
        x_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )

    best_summary: dict[str, Any] | None = None
    for candidate_name, pipeline in models.items():
        with mlflow.start_run(run_name=f"{candidate_name}-{utc_now().isoformat()}") as run:
            pipeline.fit(x_train, y_train)
            val_pred = pipeline.predict(x_val)
            test_pred = pipeline.predict(x_test)
            val_proba = pipeline.predict_proba(x_val)[:, 1] if hasattr(pipeline, "predict_proba") else None

            metrics = {
                "val_recall": recall_score(y_val, val_pred),
                "val_precision": precision_score(y_val, val_pred, zero_division=0),
                "val_f1": f1_score(y_val, val_pred, zero_division=0),
                "test_recall": recall_score(y_test, test_pred),
                "test_precision": precision_score(y_test, test_pred, zero_division=0),
                "test_f1": f1_score(y_test, test_pred, zero_division=0),
            }
            if val_proba is not None:
                metrics["val_roc_auc"] = roc_auc_score(y_val, val_proba)

            mlflow.log_param("model_name", candidate_name)
            mlflow.log_param("target_column", get_env("TARGET_COLUMN", "readmitted"))
            mlflow.log_param("feature_columns", json.dumps(list(features.columns)))
            mlflow.log_metrics(metrics)
            mlflow.log_dict({"feature_columns": list(features.columns)}, "feature_columns.json")

            signature = infer_signature(x_train, pipeline.predict(x_train))
            mlflow.sklearn.log_model(
                sk_model=pipeline,
                artifact_path="model",
                signature=signature,
                input_example=x_train.head(3),
            )

            if best_summary is None or metrics["val_recall"] > best_summary["metrics"]["val_recall"]:
                best_summary = {
                    "run_id": run.info.run_id,
                    "candidate_name": candidate_name,
                    "metrics": metrics,
                }

    if best_summary is None:
        raise RuntimeError("No model runs were created")

    registration = register_best_model(
        client,
        best_summary["run_id"],
        model_name,
        candidate_metric=best_summary["metrics"]["val_recall"],
        metric_key="val_recall",
    )
    return {
        **best_summary,
        **registration,
        "trained_at": utc_now().isoformat(),
    }


def run_pipeline() -> dict[str, Any]:
    raw_result = ingest_raw_batch()
    if raw_result["rows_inserted"] == 0:
        return {"status": "no-new-data", **raw_result}

    clean_result = build_clean_layer()
    train_result = train_and_register_model()
    return {
        "status": "completed",
        "raw": raw_result,
        "clean": clean_result,
        "training": train_result,
    }


if __name__ == "__main__":
    summary = run_pipeline()
    print(json.dumps(summary, indent=2, default=str))
