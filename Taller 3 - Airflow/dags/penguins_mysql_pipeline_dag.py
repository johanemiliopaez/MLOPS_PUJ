"""
DAG de Airflow para pipeline Penguins con MySQL.

Pasos:
1) Limpiar tablas penguins_raw y penguins.
2) Cargar CSV en penguins_raw.
3) Preprocesar datos (seccion 1 de train.py) y guardar en penguins.
4) Entrenar RF y LR (seccion 2 de train.py) y guardar PKL en /shared/Modelos.
"""

from __future__ import annotations

import os
from datetime import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator


RAW_TABLE = "penguins_raw"
CURATED_TABLE = "penguins"
CSV_PATH = "/shared/dataset/penguins.csv"
MODELS_DIR = "/shared/modelos"


def _get_engine():
    from sqlalchemy import create_engine

    user = os.getenv("MYSQL_USER", "airflow_user")
    password = os.getenv("MYSQL_PASSWORD", "airflow_pass")
    database = os.getenv("MYSQL_DATABASE", "airflow_lab")
    host = os.getenv("MYSQL_HOST", "mysql")
    port = os.getenv("MYSQL_PORT", "3306")

    uri = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    return create_engine(uri)


def step_1_clear_tables():
    from sqlalchemy import text

    engine = _get_engine()
    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {RAW_TABLE}"))
        conn.execute(text(f"DELETE FROM {CURATED_TABLE}"))
    print("Tablas limpiadas: penguins_raw y penguins.")


def step_2_load_raw():
    import pandas as pd

    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"No existe el CSV en: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, dtype=str, keep_default_na=False)
    if df.empty:
        raise ValueError("El CSV esta vacio.")

    engine = _get_engine()
    df.to_sql(RAW_TABLE, con=engine, if_exists="append", index=False, method="multi")
    print(f"Registros cargados en {RAW_TABLE}: {len(df)}")


def step_3_preprocess():
    import numpy as np
    import pandas as pd
    from sqlalchemy import text

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(f"SELECT * FROM {RAW_TABLE}", conn)

    if df.empty:
        raise ValueError(f"No hay datos en la tabla {RAW_TABLE}.")

    # 1) Limpieza: reemplazo de "NA" y dropna
    df = df.replace("NA", np.nan)
    df = df.dropna()

    # 2) Transformacion: conversion numerica y limpieza final
    numeric_cols = [
        "bill_length_mm",
        "bill_depth_mm",
        "flipper_length_mm",
        "body_mass_g",
        "year",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna()

    # 3) Validacion
    assert df["species"].notna().all(), "species tiene nulos"
    assert df["species"].nunique() >= 2, "Se necesitan al menos 2 clases en species"
    assert len(df) > 0, "DataFrame vacio tras limpieza"

    # La tabla destino fue definida como VARCHAR, por lo que convertimos a string.
    expected_cols = [
        "species",
        "island",
        "bill_length_mm",
        "bill_depth_mm",
        "flipper_length_mm",
        "body_mass_g",
        "sex",
        "year",
    ]
    df = df[expected_cols].astype(str)

    with engine.begin() as conn:
        conn.execute(text(f"DELETE FROM {CURATED_TABLE}"))
    df.to_sql(CURATED_TABLE, con=engine, if_exists="append", index=False, method="multi")
    print(f"Registros procesados guardados en {CURATED_TABLE}: {len(df)}")


def step_4_train():
    import joblib
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    engine = _get_engine()
    with engine.connect() as conn:
        df = pd.read_sql(f"SELECT * FROM {CURATED_TABLE}", conn)

    if df.empty:
        raise ValueError(f"No hay datos en la tabla {CURATED_TABLE}.")

    # Datos de penguins vienen como VARCHAR: convertir numericos.
    numeric_cols = [
        "bill_length_mm",
        "bill_depth_mm",
        "flipper_length_mm",
        "body_mass_g",
        "year",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna()

    target = "species"
    feature_cols = [c for c in df.columns if c != target]
    X = df[feature_cols]
    y = df[target]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    numeric_features = [f for f in numeric_cols if f in feature_cols]
    categorical_features = [f for f in feature_cols if f not in numeric_features]

    transformers = []
    if numeric_features:
        transformers.append(("num", StandardScaler(), numeric_features))
    if categorical_features:
        transformers.append(
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features)
        )
    preprocessor = ColumnTransformer(transformers, remainder="passthrough")

    estimators = {
        "RF": RandomForestClassifier(n_estimators=100, random_state=42),
        "LR": LogisticRegression(max_iter=1000, random_state=42),
    }

    os.makedirs(MODELS_DIR, exist_ok=True)

    for model_name, estimator in estimators.items():
        pipeline = Pipeline(
            [
                ("preprocessor", preprocessor),
                ("classifier", estimator),
            ]
        )
        pipeline.fit(X_train, y_train)
        model_path = os.path.join(MODELS_DIR, f"{model_name}.pkl")
        joblib.dump(pipeline, model_path)
        print(f"Modelo guardado: {model_path}")


with DAG(
    dag_id="penguins_mysql_pipeline",
    description="Pipeline Penguins: MySQL raw->preprocess->training",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["penguins", "mysql", "mlops"],
) as dag:
    task_clear_tables = PythonOperator(
        task_id="step_1_clear_tables",
        python_callable=step_1_clear_tables,
    )

    task_load_raw = PythonOperator(
        task_id="step_2_load_raw",
        python_callable=step_2_load_raw,
    )

    task_preprocess = PythonOperator(
        task_id="step_3_preprocess",
        python_callable=step_3_preprocess,
    )

    task_train = PythonOperator(
        task_id="step_4_train",
        python_callable=step_4_train,
    )

    task_clear_tables >> task_load_raw >> task_preprocess >> task_train
