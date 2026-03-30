-- Asegurar que mlflow_user existe (por si el entrypoint no lo creó antes de los init scripts)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mlflow_user') THEN
    CREATE ROLE mlflow_user WITH LOGIN PASSWORD 'mlflow_pass';
  END IF;
END
$$;

-- Permisos para MLflow: crear tablas en schema public
GRANT ALL PRIVILEGES ON DATABASE mlflow_db TO mlflow_user;
GRANT ALL ON SCHEMA public TO mlflow_user;
GRANT CREATE ON SCHEMA public TO mlflow_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO mlflow_user;
