CREATE DATABASE mlops_data;
CREATE DATABASE mlflow_meta;
CREATE DATABASE airflow_meta;
\connect mlops_data;

CREATE TABLE IF NOT EXISTS raw_data (
    raw_id BIGSERIAL PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    load_timestamp TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    row_hash TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_data_batch_id ON raw_data(batch_id);
CREATE INDEX IF NOT EXISTS idx_raw_data_load_timestamp ON raw_data(load_timestamp);

CREATE TABLE IF NOT EXISTS clean_data (
    clean_id BIGSERIAL PRIMARY KEY,
    source_batch_id INTEGER,
    processed_at TIMESTAMPTZ NOT NULL,
    row_hash TEXT NOT NULL UNIQUE,
    features JSONB NOT NULL,
    target_value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clean_data_processed_at ON clean_data(processed_at);

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

CREATE INDEX IF NOT EXISTS idx_inference_logs_timestamp ON inference_logs(inference_timestamp);
