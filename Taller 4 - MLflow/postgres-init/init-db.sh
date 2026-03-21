#!/bin/bash
set -e

echo "Iniciando configuración de bases de datos múltiples..."

# 1. Crear usuario para MLflow y la base de datos de datos
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Crear usuario mlflow_user si no existe
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mlflow_user') THEN
        CREATE ROLE mlflow_user WITH LOGIN PASSWORD 'mlflow_pass';
      END IF;
    END
    \$\$;

    -- Dar permisos sobre la base de datos mlflow_db (creada por el docker-compose)
    GRANT ALL PRIVILEGES ON DATABASE mlflow_db TO mlflow_user;
    ALTER DATABASE mlflow_db OWNER TO mlflow_user;

    -- Crear la nueva base de datos separada para los datos del taller
    CREATE DATABASE data_db;
EOSQL

# 2. Conectarse específicamente a data_db para crear las tablas
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "data_db" <<-EOSQL
    -- Tabla datos raw (dataset Penguins original)
    CREATE TABLE IF NOT EXISTS data_raw (
        id SERIAL PRIMARY KEY,
        species VARCHAR(50),
        island VARCHAR(50),
        bill_length_mm FLOAT,
        bill_depth_mm FLOAT,
        flipper_length_mm FLOAT,
        body_mass_g FLOAT,
        sex VARCHAR(20),
        year INT
    );

    -- Tabla datos procesados (listos para entrenamiento)
    CREATE TABLE IF NOT EXISTS data_procesada (
        id SERIAL PRIMARY KEY,
        bill_length_mm FLOAT,
        bill_depth_mm FLOAT,
        flipper_length_mm FLOAT,
        body_mass_g FLOAT,
        island_encoded INT,
        sex_encoded INT,
        year INT,
        species_encoded INT
    );
EOSQL

echo "Configuración de bases de datos finalizada con éxito."