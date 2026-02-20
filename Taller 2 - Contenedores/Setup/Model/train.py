"""
Pipeline de entrenamiento para clasificación de especies de pingüinos.
Usa Random Forest (RF) y Logistic Regression (LR) para predecir 'species'.
"""

import os

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Ruta al dataset (desde la raíz del proyecto)
#PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#DATASET_PATH = os.path.join(PROJECT_ROOT, "Dataset", "penguins.csv")
#MODEL_DIR = os.path.dirname(os.path.abspath(__file__))

PROJECT_ROOT = (os.path.dirname(os.getcwd()))
#print (PROJECT_ROOT)
DATASET_PATH = os.path.join(PROJECT_ROOT, "Dataset", "penguins.csv")
MODEL_DIR = PROJECT_ROOT

# ============== 1. PREPARACIÓN DE DATOS ==============

def step_load():
    """1. Carga: leer el CSV del dataset."""
    print("\n--- 1. CARGA ---")
    df = pd.read_csv(DATASET_PATH)
    print(f"Filas: {len(df)}, Columnas: {list(df.columns)}")
    return df


def step_clean(df):
    """2. Limpieza: manejar NA y valores inconsistentes."""
    print("\n--- 2. LIMPIEZA ---")
    # Reemplazar 'NA' string por np.nan si existe
    df = df.replace("NA", np.nan)
    # Eliminar filas con valores faltantes
    before = len(df)
    df = df.dropna()
    print(f"Filas eliminadas por faltantes: {before - len(df)}. Restantes: {len(df)}")
    return df


def step_transform(df):
    """3. Transformación: tipos y formatos adecuados."""
    print("\n--- 3. TRANSFORMACIÓN ---")
    numeric_cols = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g", "year"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna()
    print(f"Tipos numéricos aplicados. Filas: {len(df)}")
    return df


def step_validate(df):
    """4. Validación: comprobar integridad y rangos."""
    print("\n--- 4. VALIDACIÓN ---")
    assert df["species"].notna().all(), "species tiene nulos"
    assert df["species"].nunique() >= 2, "Se necesitan al menos 2 clases en species"
    assert len(df) > 0, "DataFrame vacío tras limpieza"
    print("Validación OK: sin nulos en target, múltiples clases, datos suficientes.")
    return df


def step_feature_engineering(df):
    """5. Ingeniería de características: preparar X e y."""
    print("\n--- 5. INGENIERÍA DE CARACTERÍSTICAS ---")
    target = "species"
    feature_cols = [c for c in df.columns if c != target]
    X = df[feature_cols]
    y = df[target]
    print(f"Features: {list(X.columns)}. Target: {target}. Clases: {list(y.unique())}")
    return X, y, feature_cols


def step_split(X, y, feature_cols):
    """6. División: train/test con estratificación por species."""
    print("\n--- 6. DIVISIÓN ---")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    return X_train, X_test, y_train, y_test, feature_cols


# ============== 2. CREACIÓN DE MODELOS ==============

def get_preprocessor(feature_cols):
    """Preprocesador: numéricos (escalado) + categóricos (one-hot)."""
    numeric_features = ["bill_length_mm", "bill_depth_mm", "flipper_length_mm", "body_mass_g", "year"]
    numeric_features = [f for f in numeric_features if f in feature_cols]
    categorical_features = [f for f in feature_cols if f not in numeric_features]
    transformers = []
    if numeric_features:
        transformers.append(("num", StandardScaler(), numeric_features))
    if categorical_features:
        transformers.append(
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features)
        )
    return ColumnTransformer(transformers, remainder="passthrough")


def step_build(model_name="RF"):
    """Construcción: definir pipeline del modelo."""
    print(f"\n--- CONSTRUCCIÓN ({model_name}) ---")
    # feature_cols se define después del split; aquí solo creamos el estimador base
    if model_name == "RF":
        estimator = RandomForestClassifier(n_estimators=100, random_state=42)
    else:
        estimator = LogisticRegression(max_iter=1000, random_state=42)
    return estimator


def step_train(estimator, preprocessor, X_train, y_train, model_name):
    """Entrenamiento: ajustar pipeline completo."""
    print(f"\n--- ENTRENAMIENTO ({model_name}) ---")
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("classifier", estimator),
    ])
    pipeline.fit(X_train, y_train)
    print("Entrenamiento completado.")
    return pipeline


def step_validate_model(pipeline, X_test, y_test, model_name):
    """Validación del modelo: métricas en test."""
    print(f"\n--- VALIDACIÓN DEL MODELO ({model_name}) ---")
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"Accuracy: {acc:.4f}")
    print(classification_report(y_test, y_pred))
    print("Confusion matrix:\n", confusion_matrix(y_test, y_pred))
    return acc


def save_model_as_pkl(pipeline, filename):
    """Guarda el pipeline serializado con extensión .pkl (pickle/joblib)."""
    path = os.path.join(MODEL_DIR, filename)
    joblib.dump(pipeline, path)
    print(f"Modelo guardado: {path}")


def main():
    print("=" * 60)
    print("PIPELINE PENGUINS - Preparación de datos")
    print("=" * 60)

    # --- 1. Preparación de datos (6 pasos) ---
    df = step_load()
    df = step_clean(df)
    df = step_transform(df)
    df = step_validate(df)
    X, y, feature_cols = step_feature_engineering(df)
    X_train, X_test, y_train, y_test, feature_cols = step_split(X, y, feature_cols)

    preprocessor = get_preprocessor(feature_cols)

    print("\n" + "=" * 60)
    print("PIPELINE PENGUINS - Creación de modelos")
    print("=" * 60)

    for model_name in ["RF", "LR"]:
        estimator = step_build(model_name)
        pipeline = step_train(estimator, preprocessor, X_train, y_train, model_name)
        step_validate_model(pipeline, X_test, y_test, model_name)
        save_model_as_pkl(pipeline, f"{model_name}.pkl")

    print("\n" + "=" * 60)
    print("RF.pkl y LR.pkl generados en el directorio Model.")
    print("=" * 60)


if __name__ == "__main__":
    main()
