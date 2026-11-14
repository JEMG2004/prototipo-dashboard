"""Recursos que comparten las páginas. Se cargan una vez y quedan en caché."""
from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass

import numpy as np
import streamlit as st

from datos import repositorio as repo
from dominio import Poblacion
from generador.catalogo import Catalogo, Reglas, cargar_catalogo, cargar_parametros, cargar_reglas
from generador.plantilla_prompt import PlantillaPrompt
from generador.simulado import GeneradorSimulado
from modelo.modelo import VERSION_MODELO, ModeloRiesgo


@dataclass
class Recursos:
    catalogo: Catalogo
    reglas: Reglas
    params: dict
    generador: GeneradorSimulado
    plantilla: PlantillaPrompt


@st.cache_resource(show_spinner="Preparando el generador simulado…")
def recursos() -> Recursos:
    catalogo = cargar_catalogo()
    reglas = cargar_reglas(catalogo)
    params = cargar_parametros()
    return Recursos(catalogo, reglas, params, GeneradorSimulado(catalogo, reglas), PlantillaPrompt(catalogo, reglas))


def ahora() -> str:
    return dt.datetime.now().isoformat(timespec="microseconds")


def tipos_columnas(catalogo: Catalogo) -> dict:
    tipos = {"id": str, "desertor": str}
    for v in catalogo:
        if v.tipo == "numerica":
            tipos[v.nombre] = float if v.decimales else int
        elif v.tipo == "ordinal":
            tipos[v.nombre] = int
        else:
            tipos[v.nombre] = str
    return tipos


def version_modelo() -> str:
    r = recursos()
    texto = f"{VERSION_MODELO}|{r.generador.version}|{r.params['poblacion']}|{r.params['modelo']}"
    return "modelo-" + hashlib.sha1(texto.encode()).hexdigest()[:8]


@st.cache_resource(show_spinner="Entrenando el modelo con una población sintética aparte (solo la primera vez)…")
def modelo(version: str) -> ModeloRiesgo:
    try:
        guardado = repo.cargar_modelo(version)
    except Exception:  # noqa: BLE001 - un archivo viejo o de otra versión se vuelve a entrenar
        guardado = None
    if guardado is not None:
        return guardado
    r = recursos()
    pp, mp = r.params["poblacion"], r.params["modelo"]
    entrenamiento = r.generador.generar(pp["n_entrenamiento"], pp["semilla_entrenamiento"])
    m = ModeloRiesgo(r.catalogo, mp["arboles"], mp["min_muestras_hoja"], pp["semilla_entrenamiento"])
    m.entrenar(entrenamiento, mp["proporcion_prueba"], pp["semilla_entrenamiento"], mp["umbral_riesgo"], r.generador.version)
    m.version = version
    repo.guardar_modelo(m, version)
    return m


def modelo_actual() -> ModeloRiesgo:
    return modelo(version_modelo())


@st.cache_data(show_spinner=False)
def _leer_linea_base(version: str) -> Poblacion | None:
    return repo.cargar_linea_base(tipos_columnas(recursos().catalogo))


def crear_linea_base(n: int, semilla: int) -> Poblacion:
    r = recursos()
    datos = r.generador.generar(int(n), int(semilla))
    pob = Poblacion(datos=datos, version=r.generador.huella_poblacion(int(n), int(semilla)), n=int(n),
                    semilla=int(semilla), creada=ahora(), origen=r.generador.nombre,
                    version_generador=r.generador.version)
    repo.guardar_linea_base(pob)
    _leer_linea_base.clear()
    riesgo_base.clear()
    return pob


def linea_base() -> Poblacion:
    pp = recursos().params["poblacion"]
    info = repo.info_linea_base()
    if info is None:
        with st.spinner("Generando la línea base por primera vez…"):
            return crear_linea_base(pp["n_linea_base"], pp["semilla_linea_base"])
    pob = _leer_linea_base(info["version"])
    if pob is None:
        return crear_linea_base(pp["n_linea_base"], pp["semilla_linea_base"])
    faltan = [v for v in recursos().catalogo.nombres if v not in pob.datos.columns]
    if faltan:
        # El catálogo ganó variables que la línea base guardada no tiene: hay que generarla de nuevo.
        with st.spinner("El catálogo cambió: generando la línea base de nuevo…"):
            return crear_linea_base(pob.n, pob.semilla)
    return pob


def linea_base_desactualizada() -> bool:
    """True si la línea base se generó con otro catálogo u otras reglas."""
    info = repo.info_linea_base()
    return bool(info) and info.get("version_generador") != recursos().generador.version


@st.cache_data(show_spinner="Estimando el riesgo de la línea base…")
def riesgo_base(version_base: str, version_del_modelo: str) -> np.ndarray:
    return modelo(version_del_modelo).predecir(linea_base().datos)


def riesgo_base_actual() -> np.ndarray:
    return riesgo_base(linea_base().version, version_modelo())


@st.cache_data(show_spinner=False)
def muestra_para_prompt(version_generador: str):
    """Una muestra grande del generador para mostrar el prompt de la línea base."""
    return recursos().generador.generar(20_000, 99)


def sensibilidad_palancas(version_base: str, version_del_modelo: str) -> list[dict]:
    """¿El modelo responde a cada palanca? Se lleva cada palanca hacia su valor favorable en toda la
    población (ajuste directo) y se compara el cambio del modelo con el que dicen las reglas."""
    return _sensibilidad(version_base, version_del_modelo)


def _favorable(var, regla) -> tuple:
    """El cambio favorable de una palanca, según la dirección de su regla de deserción."""
    if var.tipo in ("binaria", "categorica"):
        efectos = {v: (regla.efecto.get(v, 0.0) if regla else 0.0) for v in var.valores}
        mejor = min(var.valores, key=lambda v: efectos[v])
        return "categoria", mejor, f"todos a «{mejor}»"
    signo = -1 if (regla and regla.efecto > 0) else 1
    paso = 1 if var.tipo == "ordinal" else round(0.1 * (var.maximo - var.minimo), 2)
    texto = f"{'+' if signo > 0 else '−'}{var.formatear(paso)} a todos"
    return "numero", signo * paso, texto


@st.cache_data(show_spinner="Probando cómo responde el modelo a cada palanca…")
def _sensibilidad(version_base: str, version_del_modelo: str) -> list[dict]:
    r = recursos()
    base = linea_base().datos
    m = modelo(version_del_modelo)
    p0 = riesgo_base(version_base, version_del_modelo)
    verdad0 = r.generador.prob_desercion(base)
    reglas = {x.origen: x for x in r.reglas.desercion}
    filas = []
    for var in r.catalogo.palancas:
        clase, valor, texto = _favorable(var, reglas.get(var.nombre))
        df = base.copy()
        if clase == "categoria":
            df[var.nombre] = valor
        else:
            nuevo = np.clip(df[var.nombre].to_numpy(dtype=float) + valor, var.minimo, var.maximo)
            df[var.nombre] = nuevo.astype(int) if var.tipo == "ordinal" else np.round(nuevo, var.decimales)
        cambiados = (df[var.nombre] != base[var.nombre]).to_numpy()
        p1 = p0.copy()
        if cambiados.any():
            p1[cambiados] = m.predecir(df.loc[cambiados])
        filas.append({
            "variable": var.nombre,
            "etiqueta": var.etiqueta,
            "cambio": texto,
            "modelo_pp": float(100 * (p1.mean() - p0.mean())),
            "reglas_pp": float(100 * (r.generador.prob_desercion(df).mean() - verdad0.mean())),
            "estudiantes": int(cambiados.sum()),
        })
    return filas
