import os
import time
from datetime import datetime, timezone
from typing import Any

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from mlflow.tracking import MlflowClient
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.dialects.postgresql import insert


REQUEST_COUNTER = Counter("api_requests_total", "Total de solicitudes a la API", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("api_request_latency_seconds", "Latencia de la API", ["endpoint"])

MODEL_CACHE: dict[str, Any] = {
    "loaded_at": None,
    "alias": None,
    "model_name": None,
    "model_version": None,
    "model_uri": None,
    "pyfunc_model": None,
}


class PredictRequest(BaseModel):
    features: dict[str, Any] = Field(..., description="Payload de features para inferencia")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def get_database_uri() -> str:
    user = get_env("POSTGRES_USER", "mlops")
    password = get_env("POSTGRES_PASSWORD", "mlops123")
    host = get_env("POSTGRES_HOST", "postgres")
    port = get_env("POSTGRES_PORT", "5432")
    database = get_env("DATA_DB", "mlops_data")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def get_engine():
    return create_engine(get_database_uri(), future=True)


def ensure_inference_table() -> None:
    engine = get_engine()
    ddl = """
    CREATE TABLE IF NOT EXISTS inference_logs (
        inference_id BIGSERIAL PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE,
        inference_timestamp TIMESTAMPTZ NOT NULL,
        model_name TEXT NOT NULL,
        model_version TEXT NOT NULL,
        model_alias TEXT,
        input_payload JSONB NOT NULL,
        prediction JSONB NOT NULL,
        score DOUBLE PRECISION,
        response_time_ms DOUBLE PRECISION NOT NULL
    );
    """
    with engine.begin() as connection:
        connection.execute(text(ddl))


def configure_mlflow() -> MlflowClient:
    tracking_uri = get_env("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(tracking_uri)
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = get_env("MLFLOW_S3_ENDPOINT_URL", "http://minio:9000")
    os.environ["AWS_ACCESS_KEY_ID"] = get_env("AWS_ACCESS_KEY_ID", "minioadmin")
    os.environ["AWS_SECRET_ACCESS_KEY"] = get_env("AWS_SECRET_ACCESS_KEY", "minioadmin123")
    os.environ["AWS_DEFAULT_REGION"] = get_env("AWS_DEFAULT_REGION", "us-east-1")
    return MlflowClient(tracking_uri=tracking_uri)


def resolve_model_uri(client: MlflowClient) -> tuple[str, str, str | None]:
    model_name = get_env("MLFLOW_MODEL_NAME", "DiabetesReadmissionModel")
    alias = get_env("MLFLOW_MODEL_ALIAS", "champion")

    try:
        version = client.get_model_version_by_alias(model_name, alias)
        return f"models:/{model_name}@{alias}", version.version, alias
    except Exception:
        pass

    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        raise RuntimeError(f"No registered versions found for model '{model_name}'")

    production = [version for version in versions if getattr(version, "current_stage", "") == "Production"]
    selected = sorted(production or versions, key=lambda item: int(item.version), reverse=True)[0]
    return f"models:/{model_name}/{selected.version}", selected.version, getattr(selected, "current_stage", None)


def load_model(force: bool = False) -> None:
    ttl_seconds = int(get_env("MODEL_CACHE_TTL_SECONDS", "300"))
    loaded_at = MODEL_CACHE["loaded_at"]
    is_expired = loaded_at is None or (time.time() - loaded_at) > ttl_seconds
    if not force and MODEL_CACHE["pyfunc_model"] is not None and not is_expired:
        return

    client = configure_mlflow()
    model_name = get_env("MLFLOW_MODEL_NAME", "DiabetesReadmissionModel")
    model_uri, model_version, alias = resolve_model_uri(client)
    pyfunc_model = mlflow.pyfunc.load_model(model_uri)

    MODEL_CACHE.update(
        {
            "loaded_at": time.time(),
            "alias": alias,
            "model_name": model_name,
            "model_version": str(model_version),
            "model_uri": model_uri,
            "pyfunc_model": pyfunc_model,
        }
    )


def score_from_predictions(model, features_df: pd.DataFrame) -> float | None:
    raw_model = getattr(model, "_model_impl", None)
    python_model = getattr(raw_model, "python_model", None)
    if hasattr(python_model, "predict_proba"):
        probabilities = python_model.predict_proba(features_df)
        if len(probabilities.shape) == 2 and probabilities.shape[1] > 1:
            return float(probabilities[:, 1][0])

    internal_model = getattr(raw_model, "model", None)
    if hasattr(internal_model, "predict_proba"):
        probabilities = internal_model.predict_proba(features_df)
        if len(probabilities.shape) == 2 and probabilities.shape[1] > 1:
            return float(probabilities[:, 1][0])
    return None


def log_inference(request_id: str, features: dict[str, Any], prediction: Any, score: float | None, response_time_ms: float) -> None:
    engine = get_engine()
    metadata = MetaData()
    inference_logs = Table("inference_logs", metadata, autoload_with=engine)
    record = {
        "request_id": request_id,
        "inference_timestamp": utc_now(),
        "model_name": MODEL_CACHE["model_name"],
        "model_version": MODEL_CACHE["model_version"],
        "model_alias": MODEL_CACHE["alias"],
        "input_payload": features,
        "prediction": {"value": prediction},
        "score": score,
        "response_time_ms": response_time_ms,
    }
    with engine.begin() as connection:
        stmt = insert(inference_logs).values(record)
        stmt = stmt.on_conflict_do_nothing(index_elements=["request_id"])
        connection.execute(stmt)


app = FastAPI(title="Proyecto 2 - Inference API", version="1.0.0")


@app.on_event("startup")
def startup_event() -> None:
    try:
        ensure_inference_table()
    except Exception:
        # Allow the API to start in degraded mode while Postgres finishes booting.
        pass

    try:
        load_model(force=True)
    except Exception:
        # Allow lazy model loading if MLflow is not ready yet.
        pass


@app.get("/health")
def health() -> dict[str, Any]:
    status = "ok" if MODEL_CACHE["pyfunc_model"] is not None else "degraded"
    return {
        "status": status,
        "model_loaded": MODEL_CACHE["pyfunc_model"] is not None,
        "model_name": MODEL_CACHE["model_name"],
        "model_version": MODEL_CACHE["model_version"],
    }


@app.get("/model-info")
def model_info() -> dict[str, Any]:
    load_model()
    return {
        "model_name": MODEL_CACHE["model_name"],
        "model_version": MODEL_CACHE["model_version"],
        "model_alias": MODEL_CACHE["alias"],
        "model_uri": MODEL_CACHE["model_uri"],
    }


@app.post("/predict")
def predict(request: PredictRequest) -> dict[str, Any]:
    started_at = time.perf_counter()
    endpoint = "/predict"

    try:
        load_model()
        model = MODEL_CACHE["pyfunc_model"]
        if model is None:
            raise RuntimeError("No model available in cache")

        features_df = pd.DataFrame([request.features])
        raw_prediction = model.predict(features_df)
        prediction_value = raw_prediction[0].item() if hasattr(raw_prediction[0], "item") else raw_prediction[0]
        probability = score_from_predictions(model, features_df)
        latency_ms = (time.perf_counter() - started_at) * 1000
        request_id = f"{int(time.time() * 1000)}-{abs(hash(str(request.features))) % 1000000}"
        log_inference(request_id, request.features, prediction_value, probability, latency_ms)

        REQUEST_COUNTER.labels(endpoint=endpoint, status="success").inc()
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency_ms / 1000)
        return {
            "request_id": request_id,
            "prediction": prediction_value,
            "score": probability,
            "model_name": MODEL_CACHE["model_name"],
            "model_version": MODEL_CACHE["model_version"],
            "model_alias": MODEL_CACHE["alias"],
            "processing_time_ms": round(latency_ms, 2),
        }
    except Exception as exc:
        REQUEST_COUNTER.labels(endpoint=endpoint, status="error").inc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
