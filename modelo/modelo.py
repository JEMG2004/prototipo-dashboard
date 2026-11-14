"""Modelo predictivo: entrenar, predecir y calibrar (paquete "modelo" de la sección 7.8).

Se entrena con una población sintética aparte de la línea base. Si se
entrenara con la misma población, el bosque aleatorio "recordaría" a esos
estudiantes y un escenario mezclaría ese efecto con el de la política.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from generador.catalogo import Catalogo

VERSION_MODELO = "bosque-v1"


class ModeloRiesgo:
    def __init__(self, catalogo: Catalogo, arboles: int = 300, min_hoja: int = 5, semilla: int = 7):
        self.catalogo = catalogo
        self.numericas = [v.nombre for v in catalogo if v.tipo in ("numerica", "ordinal")]
        self.categoricas = [v.nombre for v in catalogo if v.tipo in ("binaria", "categorica")]
        self.columnas = catalogo.nombres
        pre = ColumnTransformer(
            [
                ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), self.categoricas),
                ("num", "passthrough", self.numericas),
            ]
        )
        bosque = RandomForestClassifier(n_estimators=arboles, min_samples_leaf=min_hoja, random_state=semilla, n_jobs=-1)
        self.pipeline = Pipeline([("pre", pre), ("bosque", bosque)])
        self.metricas: dict = {}
        self.version = ""

    def _x(self, df: pd.DataFrame) -> pd.DataFrame:
        x = df[self.columnas].copy()
        for c in self.categoricas:
            x[c] = x[c].astype(object)
        for c in self.numericas:
            x[c] = x[c].astype(float)
        return x

    def entrenar(self, df: pd.DataFrame, proporcion_prueba: float, semilla: int, umbral: float, huella_datos: str) -> dict:
        x = self._x(df)
        y = (df["desertor"] == "Sí").astype(int).to_numpy()
        x_tr, x_te, y_tr, y_te = train_test_split(x, y, test_size=proporcion_prueba, random_state=semilla, stratify=y)
        self.pipeline.fit(x_tr, y_tr)
        p = self.pipeline.predict_proba(x_te)[:, 1]
        pred = (p >= umbral).astype(int)
        obs, media = calibration_curve(y_te, p, n_bins=10, strategy="quantile")
        imp = permutation_importance(self.pipeline, x_te, y_te, scoring="roc_auc", n_repeats=5, random_state=semilla, n_jobs=1)
        self.metricas = {
            "n_entrenamiento": int(len(x_tr)),
            "n_prueba": int(len(x_te)),
            "tasa_desertores": float(y.mean()),
            "auc": float(roc_auc_score(y_te, p)),
            "f1": float(f1_score(y_te, pred, zero_division=0)),
            "precision": float(precision_score(y_te, pred, zero_division=0)),
            "recall": float(recall_score(y_te, pred, zero_division=0)),
            "brier": float(brier_score_loss(y_te, p)),
            "brier_referencia": float(brier_score_loss(y_te, np.full(len(y_te), y_tr.mean()))),
            "umbral": float(umbral),
            "calibracion": {"predicho": media.tolist(), "observado": obs.tolist()},
            "importancia": {c: float(v) for c, v in zip(x.columns, imp.importances_mean)},
            "importancia_sd": {c: float(v) for c, v in zip(x.columns, imp.importances_std)},
        }
        texto = f"{VERSION_MODELO}|{huella_datos}|{self.pipeline.named_steps['bosque'].get_params()}"
        self.version = "modelo-" + hashlib.sha1(texto.encode()).hexdigest()[:8]
        return self.metricas

    def predecir(self, df: pd.DataFrame) -> np.ndarray:
        if len(df) == 0:
            return np.zeros(0)
        return self.pipeline.predict_proba(self._x(df))[:, 1]
