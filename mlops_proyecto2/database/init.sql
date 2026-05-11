-- =====================================================================
-- CONFIGURACIÓN DE INFRAESTRUCTURA
-- =====================================================================

-- 1. Crear base de datos independiente para Airflow (Evita colisiones con MLflow)
CREATE DATABASE airflow_db;

-- =====================================================================
-- TABLAS DEL PROYECTO (Se crean por defecto en la base de datos mlops_db)
-- =====================================================================

-- Capa 1: Datos Crudos (RAW DATA)
-- Almacena los datos originales cargados por lotes desde el archivo fuente[cite: 1]
CREATE TABLE IF NOT EXISTS raw_data (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR(50) NOT NULL,
    load_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_file VARCHAR(255),
    status VARCHAR(50) DEFAULT 'loaded',
    record_data JSONB NOT NULL -- Contiene todas las columnas originales del CSV
);

-- Capa 2: Datos Procesados (CLEAN DATA)
-- Almacena los datos limpios, transformados y listos para el entrenamiento[cite: 1]
CREATE TABLE IF NOT EXISTS clean_data (
    id SERIAL PRIMARY KEY,
    raw_id INTEGER REFERENCES raw_data(id),
    processed_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    features JSONB NOT NULL, -- Características usadas por el modelo
    readmitted_binary INTEGER NOT NULL -- Variable objetivo unificada (0 o 1)
);

-- Capa 3: Registros de Inferencia (INFERENCE LOGS)
-- Almacena el historial de predicciones realizadas por la API de FastAPI[cite: 1]
CREATE TABLE IF NOT EXISTS inference_logs (
    request_id UUID PRIMARY KEY,
    inference_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    input_data JSONB NOT NULL,
    prediction INTEGER NOT NULL,
    probability FLOAT,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    response_time_ms FLOAT NOT NULL
);