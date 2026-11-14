"""Validaciones de lo generado: ¿la población cumple las metas de entrada? (sección 7.9)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def divergencia_js(p: np.ndarray, q: np.ndarray) -> float:
    """Divergencia de Jensen-Shannon en base 2 (0 = iguales, 1 = sin nada en común)."""
    p = np.asarray(p, float)
    q = np.asarray(q, float)
    p = p / p.sum()
    q = q / q.sum()
    m = (p + q) / 2

    def kl(a, b):
        mascara = a > 0
        return float(np.sum(a[mascara] * np.log2(a[mascara] / b[mascara])))

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def metas_de_entrada(poblacion: pd.DataFrame, catalogo) -> pd.DataFrame:
    """Compara cada variable de la población con su distribución de referencia del catálogo."""
    filas = []
    for v in catalogo:
        etiquetas, referencia = v.categorias_referencia()
        observada = v.distribucion(poblacion[v.nombre])
        filas.append({
            "variable": v.nombre,
            "etiqueta": v.etiqueta,
            "jsd": divergencia_js(observada, referencia),
            "mayor_diferencia_pp": float(100 * np.max(np.abs(observada - referencia))),
            "fuente_referencia": v.fuente_referencia,
        })
    return pd.DataFrame(filas)


def filas_repetidas(poblacion: pd.DataFrame, columnas: list[str]) -> int:
    """Cuántos estudiantes son copia exacta de otro de la misma población."""
    return int(poblacion.duplicated(subset=columnas, keep="first").sum())
