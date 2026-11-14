"""Aplicar una política a la línea base (secciones 7.1 y 7.6 del Plan).

Dos modos:
- Ajuste directo: cambia solo la variable de la palanca, con una regla.
  Instantáneo y gratis; las demás variables no cambian.
- Regeneración: el LLM vuelve a generar el segmento con el prompt modificado.
  Aquí lo hace el generador simulado: conserva las variables de contexto del
  segmento, aplica la nueva meta a la palanca (con la imprecisión de un LLM) y
  vuelve a generar las variables que dependen de ella según las reglas.

En los dos modos, solo se toca la parte de la población que la política
modifica; el resto de la línea base queda igual (Néstor, reunión 5).
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd

from dominio import Escenario, ParametroPolitica, Variable
from escenarios.comparacion import clasificar


def elegibles(df: pd.DataFrame, p: ParametroPolitica, seg: np.ndarray) -> np.ndarray:
    """Quiénes del segmento pueden recibir el cambio."""
    x = df[p.variable]
    if p.operacion == "cambiar":
        m = (x == p.desde).to_numpy()
    elif p.operacion == "fijar_minimo":
        m = x.to_numpy(dtype=float) < float(p.valor) - 1e-9
    elif p.operacion == "fijar_maximo":
        m = x.to_numpy(dtype=float) > float(p.valor) + 1e-9
    else:
        m = np.ones(len(df), bool)
    return m & seg


def transformar(x: np.ndarray, p: ParametroPolitica, var: Variable, dosis: float = 1.0,
                rng: np.random.Generator | None = None, ruido: float = 0.0, redondear: bool = True) -> np.ndarray:
    """El nuevo valor de la palanca. "dosis" escala el tamaño del cambio (1 = el definido)."""
    if p.operacion == "cambiar":
        return np.full(len(x), p.hacia, dtype=object)
    xf = x.astype(float)
    v = float(p.valor)
    if p.operacion == "multiplicar":
        y = xf * (1 + dosis * (v - 1))
    elif p.operacion == "sumar":
        y = xf + dosis * v
    else:  # fijar_minimo / fijar_maximo: solo se aplica a los elegibles
        y = xf + dosis * (v - xf)
    if ruido and rng is not None:
        y = y + rng.normal(0, ruido, len(y))
    y = np.clip(y, var.minimo, var.maximo)
    if not redondear:
        return y
    if var.tipo == "ordinal":
        piso = np.floor(y)
        sube = (rng.random(len(y)) < (y - piso)) if rng is not None else (y - piso) >= 0.5
        return np.clip(piso + sube, var.minimo, var.maximo).astype(int)
    return np.round(y, var.decimales)


def aplicar_politica(base: pd.DataFrame, esc: Escenario, generador, catalogo, rng: np.random.Generator,
                     simulacion: dict, dosis: float = 1.0) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Devuelve la población del escenario, quiénes cambiaron y la máscara del segmento."""
    df = base.copy()
    seg = esc.segmento.mascara(base)
    regenerar = esc.modo == "regeneracion"
    palancas = {p.variable: p for p in esc.palancas}
    a_regenerar = set(generador.descendientes(list(palancas))) if regenerar else set()
    for v in generador.orden:
        if v in a_regenerar and seg.any():
            df.loc[seg, v] = generador.regenerar_variable(df.loc[seg], v, rng)
        if v not in palancas:
            continue
        p = palancas[v]
        var = catalogo[v]
        idx = np.flatnonzero(elegibles(df, p, seg))
        cobertura = min(1.0, p.cobertura * (dosis if p.operacion == "cambiar" else 1.0))
        if regenerar and cobertura > 0:
            cobertura = float(np.clip(cobertura + rng.normal(0, simulacion["desviacion_cobertura"]), 0, 1))
        k = int(round(cobertura * len(idx)))
        if k == 0 or (dosis == 0 and p.operacion != "cambiar"):
            continue
        elegidos = rng.choice(idx, size=k, replace=False)
        col = df.columns.get_loc(v)
        nuevos = transformar(
            df.iloc[elegidos, col].to_numpy(), p, var,
            dosis=1.0 if p.operacion == "cambiar" else dosis,
            rng=rng,
            ruido=simulacion["ruido_numerico"] if (regenerar and var.es_numerica) else 0.0,
        )
        df.iloc[elegidos, col] = nuevos
    cambiados = (df[catalogo.nombres] != base[catalogo.nombres]).any(axis=1).to_numpy()
    return df, cambiados, seg


def comprobar(base: pd.DataFrame, poblaciones: list[pd.DataFrame], esc: Escenario, catalogo, seg: np.ndarray,
              params: dict, dosis: float = 1.0) -> list[dict]:
    """¿La variable de verdad cambió como pedía la política? (comprobación de manipulación)."""
    filas = []
    tol_p = params["comprobacion"]["tolerancia_proporcion"]
    tol_m = params["comprobacion"]["tolerancia_media"]
    for p in esc.palancas:
        var = catalogo[p.variable]
        xb = base.loc[seg, p.variable]
        if not seg.any():
            continue
        if p.operacion == "cambiar":
            cob = min(1.0, p.cobertura * dosis)
            antes = float((xb == p.desde).mean())
            meta = antes * (1 - cob)
            logrados = [float((df.loc[seg, p.variable] == p.desde).mean()) for df in poblaciones]
            medida, tolerancia, es_proporcion = f"% con «{p.desde}» en el segmento", tol_p, True
        else:
            x = xb.to_numpy(dtype=float)
            eleg = elegibles(base, p, seg)[seg]
            t = transformar(x, p, var, dosis=dosis, redondear=False)
            antes = float(x.mean())
            meta = float((x + p.cobertura * (t - x) * eleg).mean())
            logrados = [float(df.loc[seg, p.variable].to_numpy(dtype=float).mean()) for df in poblaciones]
            medida, tolerancia, es_proporcion = "Media en el segmento", tol_m, False
        logrado = float(np.mean(logrados))
        filas.append({
            "variable": p.variable,
            "etiqueta": var.etiqueta,
            "cambio": p.describir(var),
            "medida": medida,
            "es_proporcion": es_proporcion,
            "antes": antes,
            "meta": meta,
            "logrado": logrado,
            "logrado_min": float(np.min(logrados)),
            "logrado_max": float(np.max(logrados)),
            "cumple": bool(abs(logrado - meta) <= tolerancia),
            "tolerancia": tolerancia,
        })
    return filas


def estimar_costo(esc: Escenario, base: pd.DataFrame, params: dict) -> dict:
    """Lo que costaría y tardaría con el LLM, con lo medido en la prueba de generación."""
    ref = params["llm_referencia"]
    seg_n = int(esc.segmento.mascara(base).sum())
    afectados = 0
    seg = esc.segmento.mascara(base)
    for p in esc.palancas:
        afectados += int(round(p.cobertura * elegibles(base, p, seg).sum()))
    afectados = min(afectados, seg_n)
    if esc.modo != "regeneracion":
        return {"segmento": seg_n, "reciben_cambio": afectados, "regenerados": 0, "llamadas": 0, "minutos": 0.0, "usd": 0.0}
    total = seg_n * esc.replicas
    return {
        "segmento": seg_n,
        "reciben_cambio": afectados,
        "regenerados": total,
        "llamadas": math.ceil(seg_n / ref["estudiantes_por_llamada"]) * esc.replicas if seg_n else 0,
        "minutos": total / ref["estudiantes_por_minuto"],
        "usd": total * ref["usd_por_1000_estudiantes"] / 1000,
    }


def copias_frente_base(base: pd.DataFrame, nueva: pd.DataFrame, seg: np.ndarray, columnas: list[str]) -> float:
    """Proporción de estudiantes regenerados que son copia exacta de otro estudiante de la base."""
    tuplas_base = list(map(tuple, base[columnas].astype(str).to_numpy()))
    conteo = Counter(tuplas_base)
    nuevas = list(map(tuple, nueva.loc[seg, columnas].astype(str).to_numpy()))
    propias = [t for t, s in zip(tuplas_base, seg) if s]
    copias = sum(1 for t, propia in zip(nuevas, propias) if conteo[t] - (1 if t == propia else 0) > 0)
    return copias / len(nuevas) if nuevas else 0.0


def ejecutar(esc: Escenario, base: pd.DataFrame, riesgo_base: np.ndarray, generador, modelo, catalogo, params: dict,
             al_avanzar=None, dosis: float = 1.0) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Corre las réplicas del escenario y compara con la línea base."""
    umbral = params["modelo"]["umbral_riesgo"]
    seg = esc.segmento.mascara(base)
    riesgos, replicas, poblaciones = {}, [], []
    for r in range(esc.replicas):
        rng = np.random.default_rng([int(esc.semilla), r, int(round(dosis * 1000))])
        df_r, cambiados, _ = aplicar_politica(base, esc, generador, catalogo, rng, params["simulacion_llm"], dosis)
        p_r = riesgo_base.copy()
        if cambiados.any():
            p_r[cambiados] = modelo.predecir(df_r.loc[cambiados])
        riesgos[f"r{r + 1}"] = p_r
        poblaciones.append(df_r)
        replicas.append({
            "replica": r + 1,
            "desertores_poblacion": float(p_r.sum()),
            "desertores_segmento": float(p_r[seg].sum()),
            "en_riesgo_poblacion": float((p_r >= umbral).mean()),
            "en_riesgo_segmento": float((p_r[seg] >= umbral).mean()) if seg.any() else 0.0,
            "cambiados": int(cambiados.sum()),
        })
        if al_avanzar:
            al_avanzar((r + 1) / esc.replicas, f"Réplica {r + 1} de {esc.replicas}")
    linea = {
        "n_poblacion": int(len(base)),
        "n_segmento": int(seg.sum()),
        "desertores_poblacion": float(riesgo_base.sum()),
        "desertores_segmento": float(riesgo_base[seg].sum()),
        "en_riesgo_poblacion": float((riesgo_base >= umbral).mean()),
        "en_riesgo_segmento": float((riesgo_base[seg] >= umbral).mean()) if seg.any() else 0.0,
    }
    clasificacion = {
        "poblacion": clasificar(linea["desertores_poblacion"], [r["desertores_poblacion"] for r in replicas], params),
        "segmento": clasificar(linea["desertores_segmento"], [r["desertores_segmento"] for r in replicas], params),
    }
    copias = None
    if esc.modo == "regeneracion" and seg.any():
        copias = copias_frente_base(base, poblaciones[0], seg, catalogo.nombres)
    resumen = {
        "base": linea,
        "replicas": replicas,
        "comprobacion": comprobar(base, poblaciones, esc, catalogo, seg, params, dosis),
        "clasificacion": clasificacion,
        "copias_frente_base": copias,
    }
    riesgos_df = pd.DataFrame({"id": base["id"].to_numpy(), "en_segmento": seg, "riesgo_base": riesgo_base, **riesgos})
    return resumen, riesgos_df, poblaciones[0]
