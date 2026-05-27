-- 1. Crear base de datos independiente para Airflow
CREATE DATABASE airflow_db;

-- 2. Capa 1: Datos Crudos (RAW DATA)
CREATE TABLE IF NOT EXISTS raw_data (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(100) NOT NULL,
    load_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'loaded',
    record_data JSONB NOT NULL
);

-- 3. Capa 2: Datos Procesados (CLEAN DATA)
CREATE TABLE IF NOT EXISTS clean_data (
    id SERIAL PRIMARY KEY,
    raw_id INTEGER REFERENCES raw_data(id),
    processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    features JSONB NOT NULL,
    price NUMERIC -- Variable objetivo (Regresión)
);

-- 4. Capa 3: Registros de Inferencia (INFERENCE LOGS)
CREATE TABLE IF NOT EXISTS inference_logs (
    request_id UUID PRIMARY KEY,
    inference_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_data JSONB NOT NULL,
    prediction NUMERIC NOT NULL, -- Ahora es un valor continuo
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    response_time_ms FLOAT NOT NULL,
    status VARCHAR(50) DEFAULT 'success', -- Nuevo: RF8
    error_message TEXT -- Nuevo: RF8
);