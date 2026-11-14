"""Comparar un escenario con la línea base: ¿el cambio es leve, importante o ruido?

Los umbrales están en datos/parametros.yaml y son PROVISIONALES: sirven para
probar la interfaz. Cuándo un cambio es "leve" o "importante" lo decide el
coordinador (el 100 → 98 frente al 100 → 50 de Néstor).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def clasificar(base: float, valores: list[float], params: dict) -> dict:
    c = params["clasificacion"]
    d = np.asarray(valores, float) - base
    media = float(d.mean()) if len(d) else 0.0
    sd = float(d.std(ddof=1)) if len(d) > 1 else 0.0
    ruido = max(c["veces_desviacion"] * sd, c["piso_ruido_relativo"] * base)
    relativo = media / base if base > 0 else 0.0
    if abs(media) <= ruido:
        nivel, direccion, etiqueta = "ruido", "ninguna", "Dentro del ruido"
    else:
        magnitud = abs(relativo)
        nivel = "leve" if magnitud < c["leve_hasta"] else ("importante" if magnitud >= c["importante_desde"] else "moderado")
        direccion = "mejora" if media < 0 else "empeora"
        if media < 0:
            etiqueta = f"Mejora {'moderada' if nivel == 'moderado' else nivel}"
        else:
            etiqueta = f"Empeoramiento {nivel}"
    return {
        "base": float(base),
        "media": float(base + media),
        "delta": media,
        "delta_relativo": relativo,
        "sd": sd,
        "min": float(base + d.min()) if len(d) else float(base),
        "max": float(base + d.max()) if len(d) else float(base),
        "ruido": float(ruido),
        "nivel": nivel,
        "direccion": direccion,
        "etiqueta": etiqueta,
    }


def por_categoria(base: pd.DataFrame, riesgos: pd.DataFrame, variable: str, catalogo, umbral: float) -> pd.DataFrame:
    """Riesgo por grupo de una variable (con los valores de la línea base, antes de la política)."""
    var = catalogo[variable]
    grupos = pd.Series(var.agrupar(base[variable]), index=base.index)
    cols = [c for c in riesgos.columns if c.startswith("r") and c[1:].isdigit()]
    filas = []
    for g in var.categorias_referencia()[0]:
        m = (grupos == g).to_numpy()
        n = int(m.sum())
        if n == 0:
            continue
        pb = riesgos.loc[m, "riesgo_base"].to_numpy()
        pe = riesgos.loc[m, cols].to_numpy()
        filas.append({
            "grupo": str(g),
            "estudiantes": n,
            "riesgo_base": 100 * pb.mean(),
            "riesgo_escenario": 100 * pe.mean(),
            "desertores_base": pb.sum(),
            "desertores_escenario": pe.sum(axis=0).mean(),
            "en_riesgo_base": 100 * (pb >= umbral).mean(),
            "en_riesgo_escenario": 100 * (pe >= umbral).mean(),
        })
    return pd.DataFrame(filas)
