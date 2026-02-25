"""
FastAPI service for penguins model inference.
"""

from __future__ import annotations

import os

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


RF_PATH = "/shared/modelos/RF.pkl"
LR_PATH = "/shared/modelos/LR.pkl"

app = FastAPI(
    title="Penguins API",
    description="Inference endpoints for RF and LR models.",
    version="1.0.0",
)

model_rf = None
model_lr = None
rf_mtime = None
lr_mtime = None


@app.on_event("startup")
def load_models():
    global model_rf, model_lr, rf_mtime, lr_mtime
    if os.path.isfile(RF_PATH):
        model_rf = joblib.load(RF_PATH)
        rf_mtime = os.path.getmtime(RF_PATH)
    if os.path.isfile(LR_PATH):
        model_lr = joblib.load(LR_PATH)
        lr_mtime = os.path.getmtime(LR_PATH)


def refresh_models_if_changed():
    """
    Recarga modelos si los PKL del volumen compartido fueron actualizados.
    """
    global model_rf, model_lr, rf_mtime, lr_mtime

    if os.path.isfile(RF_PATH):
        current_rf_mtime = os.path.getmtime(RF_PATH)
        if model_rf is None or rf_mtime != current_rf_mtime:
            model_rf = joblib.load(RF_PATH)
            rf_mtime = current_rf_mtime

    if os.path.isfile(LR_PATH):
        current_lr_mtime = os.path.getmtime(LR_PATH)
        if model_lr is None or lr_mtime != current_lr_mtime:
            model_lr = joblib.load(LR_PATH)
            lr_mtime = current_lr_mtime


class PenguinFeatures(BaseModel):
    island: str = Field(..., description="Island: Torgersen, Biscoe or Dream")
    bill_length_mm: float
    bill_depth_mm: float
    flipper_length_mm: float
    body_mass_g: float
    sex: str = Field(..., description="male or female")
    year: int


def _predict(model, payload: PenguinFeatures) -> str:
    row = pd.DataFrame(
        [
            {
                "island": payload.island,
                "bill_length_mm": payload.bill_length_mm,
                "bill_depth_mm": payload.bill_depth_mm,
                "flipper_length_mm": payload.flipper_length_mm,
                "body_mass_g": payload.body_mass_g,
                "sex": payload.sex,
                "year": payload.year,
            }
        ]
    )
    pred = model.predict(row)
    return str(pred[0])


@app.get("/")
def root():
    return {
        "message": "Penguins API",
        "docs": "/docs",
        "models_path": "/shared/modelos",
        "endpoints": {"POST /rf": "Random Forest", "POST /lr": "Logistic Regression"},
    }


@app.post("/rf")
def predict_rf(payload: PenguinFeatures):
    refresh_models_if_changed()
    if model_rf is None:
        raise HTTPException(status_code=503, detail="RF model is not loaded")
    try:
        return {"model": "RF", "species": _predict(model_rf, payload)}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/lr")
def predict_lr(payload: PenguinFeatures):
    refresh_models_if_changed()
    if model_lr is None:
        raise HTTPException(status_code=503, detail="LR model is not loaded")
    try:
        return {"model": "LR", "species": _predict(model_lr, payload)}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
