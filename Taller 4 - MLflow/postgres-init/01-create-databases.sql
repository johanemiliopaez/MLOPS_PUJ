-- Usar mlflow_db con schema taller_data para datos del taller (evita crear data_db que requería GRANT previo)
CREATE SCHEMA IF NOT EXISTS taller_data;

-- Tabla datos raw (dataset Penguins original)
CREATE TABLE IF NOT EXISTS taller_data.data_raw (
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
CREATE TABLE IF NOT EXISTS taller_data.data_procesada (
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

GRANT ALL PRIVILEGES ON SCHEMA taller_data TO mlflow_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA taller_data TO mlflow_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA taller_data TO mlflow_user;
