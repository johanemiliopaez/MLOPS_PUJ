"""
Pipeline de entrenamiento con multiples tecnicas de ML.
Registra experimentos en MLflow y busca los mejores hiperparametros por tecnica.
"""

import json
import os
from itertools import product
from typing import Dict, List, Tuple

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(PROJECT_ROOT, "Dataset", "penguins.csv")
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(MODEL_DIR, "reports")

EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "penguins-multi-techniques-v2")
TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
CV_FOLDS = 5
RANDOM_STATE = 42


def load_and_prepare_data() -> Tuple[pd.DataFrame, pd.Series, List[str]]:
    """Carga y limpieza basica del dataset."""
    df = pd.read_csv(DATASET_PATH)
    df = df.replace("NA", np.nan)

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
    target_col = "species"
    feature_cols = [c for c in df.columns if c != target_col]

    if target_col not in df.columns:
        raise ValueError("No existe la columna objetivo 'species' en el dataset.")
    if df[target_col].nunique() < 2:
        raise ValueError("El target necesita al menos 2 clases para entrenar.")
    if len(df) == 0:
        raise ValueError("No hay datos luego de la limpieza.")

    x_data = df[feature_cols]
    y_data = df[target_col]
    return x_data, y_data, feature_cols


def build_preprocessor(feature_cols: List[str]) -> ColumnTransformer:
    """Preprocesador para columnas numericas y categoricas."""
    numeric_features = [
        "bill_length_mm",
        "bill_depth_mm",
        "flipper_length_mm",
        "body_mass_g",
        "year",
    ]
    numeric_features = [f for f in numeric_features if f in feature_cols]
    categorical_features = [f for f in feature_cols if f not in numeric_features]

    transformers = []
    if numeric_features:
        transformers.append(("num", StandardScaler(), numeric_features))
    if categorical_features:
        transformers.append(
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features)
        )

    return ColumnTransformer(transformers, remainder="drop")


def get_techniques() -> Dict[str, Dict[str, object]]:
    """Define tecnicas y sus grillas de hiperparametros."""
    return {
        "RandomForest": {
            "estimator": RandomForestClassifier(random_state=RANDOM_STATE),
            "param_grid": {
                "n_estimators": [100, 200],
                "max_depth": [None, 8, 15],
                "min_samples_split": [2, 5],
            },
        },
        "LogisticRegression": {
            "estimator": LogisticRegression(random_state=RANDOM_STATE, max_iter=2000),
            "param_grid": {
                "C": [0.1, 1.0, 10.0],
                "solver": ["lbfgs", "saga"],
                "penalty": ["l2"],
            },
        },
        "SVC": {
            "estimator": SVC(probability=True, random_state=RANDOM_STATE),
            "param_grid": {
                "C": [0.5, 1.0, 5.0],
                "kernel": ["rbf", "linear"],
                "gamma": ["scale", "auto"],
            },
        },
        "GradientBoosting": {
            "estimator": GradientBoostingClassifier(random_state=RANDOM_STATE),
            "param_grid": {
                "n_estimators": [100, 200],
                "learning_rate": [0.05, 0.1],
                "max_depth": [2, 3],
            },
        },
    }


def expand_param_grid(param_grid: Dict[str, List[object]]) -> List[Dict[str, object]]:
    """Genera todas las combinaciones de hiperparametros."""
    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]
    combos = []
    for vals in product(*values):
        combos.append(dict(zip(keys, vals)))
    return combos


def ensure_dirs() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


def train_with_search() -> None:
    """Entrena tecnicas, itera hiperparametros y registra en MLflow."""
    ensure_dirs()
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment(EXPERIMENT_NAME)

    x_data, y_data, feature_cols = load_and_prepare_data()
    x_train, x_test, y_train, y_test = train_test_split(
        x_data,
        y_data,
        test_size=0.2,
        random_state=RANDOM_STATE,
        stratify=y_data,
    )

    preprocessor = build_preprocessor(feature_cols)
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    techniques = get_techniques()

    best_by_technique = []

    with mlflow.start_run(run_name="multi-techniques-hyperparam-search"):
        mlflow.log_param("dataset_path", DATASET_PATH)
        mlflow.log_param("cv_folds", CV_FOLDS)
        mlflow.log_param("test_size", 0.2)
        mlflow.log_param("tracking_uri", TRACKING_URI)

        for technique_name, config in techniques.items():
            base_estimator = config["estimator"]
            param_combinations = expand_param_grid(config["param_grid"])

            best_entry = {
                "technique": technique_name,
                "cv_f1_macro": -1.0,
                "test_f1_macro": -1.0,
                "test_accuracy": -1.0,
                "params": {},
                "model_path": "",
            }

            with mlflow.start_run(run_name=f"{technique_name}-search", nested=True):
                mlflow.log_param("technique", technique_name)
                mlflow.log_param("num_combinations", len(param_combinations))

                for idx, params in enumerate(param_combinations, start=1):
                    estimator = clone(base_estimator)
                    estimator.set_params(**params)
                    pipeline = Pipeline(
                        [
                            ("preprocessor", preprocessor),
                            ("classifier", estimator),
                        ]
                    )

                    cv_scores = cross_val_score(
                        pipeline,
                        x_train,
                        y_train,
                        cv=cv,
                        scoring="f1_macro",
                        n_jobs=-1,
                    )
                    cv_f1_macro = float(np.mean(cv_scores))
                    cv_f1_std = float(np.std(cv_scores))

                    with mlflow.start_run(
                        run_name=f"{technique_name}-trial-{idx}",
                        nested=True,
                    ):
                        mlflow.log_param("technique", technique_name)
                        mlflow.log_param("trial_index", idx)
                        mlflow.log_params(params)
                        mlflow.log_metric("cv_f1_macro", cv_f1_macro)
                        mlflow.log_metric("cv_f1_std", cv_f1_std)

                    if cv_f1_macro > best_entry["cv_f1_macro"]:
                        pipeline.fit(x_train, y_train)
                        y_pred = pipeline.predict(x_test)
                        test_f1_macro = float(f1_score(y_test, y_pred, average="macro"))
                        test_accuracy = float(accuracy_score(y_test, y_pred))

                        model_filename = f"{technique_name}_best.pkl"
                        model_path = os.path.join(MODEL_DIR, model_filename)
                        joblib.dump(pipeline, model_path)

                        best_entry = {
                            "technique": technique_name,
                            "cv_f1_macro": cv_f1_macro,
                            "test_f1_macro": test_f1_macro,
                            "test_accuracy": test_accuracy,
                            "params": params,
                            "model_path": model_path,
                        }

                mlflow.log_metric("best_cv_f1_macro", best_entry["cv_f1_macro"])
                mlflow.log_metric("best_test_f1_macro", best_entry["test_f1_macro"])
                mlflow.log_metric("best_test_accuracy", best_entry["test_accuracy"])
                mlflow.log_params(
                    {f"best_{k}": v for k, v in best_entry["params"].items()}
                )
                try:
                    mlflow.sklearn.log_model(
                        sk_model=joblib.load(best_entry["model_path"]),
                        name=f"best_model_{technique_name}",
                    )
                    mlflow.log_artifact(best_entry["model_path"], artifact_path="best_pickles")
                    mlflow.set_tag(f"{technique_name}_artifact_logging", "ok")
                except Exception as exc:
                    # No detener todo el experimento por un error de artifacts.
                    mlflow.set_tag(f"{technique_name}_artifact_logging", f"error: {str(exc)[:200]}")
                    print(f"[WARN] No se pudo subir artifacts de {technique_name}: {exc}")

                best_by_technique.append(best_entry)

        summary_df = pd.DataFrame(
            [
                {
                    "technique": entry["technique"],
                    "cv_f1_macro": entry["cv_f1_macro"],
                    "test_f1_macro": entry["test_f1_macro"],
                    "test_accuracy": entry["test_accuracy"],
                    "params_json": json.dumps(entry["params"], sort_keys=True),
                    "model_path": entry["model_path"],
                }
                for entry in best_by_technique
            ]
        ).sort_values(by="test_f1_macro", ascending=False)

        summary_csv_path = os.path.join(REPORTS_DIR, "best_by_technique.csv")
        summary_json_path = os.path.join(REPORTS_DIR, "best_by_technique.json")
        summary_df.to_csv(summary_csv_path, index=False)
        summary_df.to_json(summary_json_path, orient="records", indent=2)

        try:
            mlflow.log_artifact(summary_csv_path, artifact_path="reports")
            mlflow.log_artifact(summary_json_path, artifact_path="reports")
        except Exception as exc:
            mlflow.set_tag("summary_artifact_logging", f"error: {str(exc)[:200]}")
            print(f"[WARN] No se pudieron subir reportes como artifacts: {exc}")

    print("=" * 70)
    print("Entrenamiento finalizado con registro en MLflow.")
    print(f"Tracking URI: {TRACKING_URI}")
    print(f"Experimento: {EXPERIMENT_NAME}")
    print(f"Reporte CSV: {os.path.join(REPORTS_DIR, 'best_by_technique.csv')}")
    print(f"Reporte JSON: {os.path.join(REPORTS_DIR, 'best_by_technique.json')}")
    print("=" * 70)


if __name__ == "__main__":
    train_with_search()
