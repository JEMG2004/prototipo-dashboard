"""Almacenamiento en archivos (sección 6 del Plan): sin motor de base de datos.

- Línea base: datos/generados/linea_base.csv (+ .json con su información).
- Modelo entrenado: datos/generados/modelo/<versión>.joblib.
- Resultados: datos/generados/resultados/<id>/ (resumen.json, riesgos.csv, poblacion_r1.csv).
- Registro de ejecuciones: datos/generados/registro.csv.

Si al final se usa SQLite, solo cambia este archivo.

Publicado, la carpeta se cambia con la variable de entorno CARPETA_GENERADOS: la ruta del disco persistente (Render) o
del volumen (Fly.io). Sin disco (plan gratis de Render), todo se borra cuando el servicio se reinicia o se duerme.

El disco no existe mientras la plataforma construye, así que precalcular.py deja la línea base y el modelo en
datos/generados, dentro de la publicación, y la primera vez que la app arranca con el disco vacío los copia ahí.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path

import joblib
import pandas as pd

from dominio import Ejecucion, Poblacion

SEMILLA = Path(__file__).resolve().parent / "generados"
CARPETA = Path(os.environ.get("CARPETA_GENERADOS") or SEMILLA)
RESULTADOS = CARPETA / "resultados"
MODELOS = CARPETA / "modelo"
REGISTRO = CARPETA / "registro.csv"


def _sembrar() -> None:
    """Con un disco persistente vacío, copia lo que precalcular.py dejó en datos/generados. Si ya tiene algo, no lo toca."""
    if CARPETA.resolve() == SEMILLA.resolve() or not (SEMILLA / "linea_base.json").exists():
        return
    if CARPETA.exists() and any(CARPETA.iterdir()):
        return
    try:
        shutil.copytree(SEMILLA, CARPETA, dirs_exist_ok=True)
    except OSError as error:  # si no se puede copiar, la app genera todo en la primera visita
        print(f"No se pudo copiar la línea base precalculada a {CARPETA}: {error}")


_sembrar()

COLUMNAS_REGISTRO = [
    "fecha", "id", "escenario", "politica", "modo", "replicas", "segmento", "estudiantes_segmento",
    "estudiantes_cambiados", "estudiantes_regenerados", "generador", "modelo_llm", "version_prompt",
    "hash_prompt", "tokens_entrada_estimados", "llamadas_estimadas", "tiempo_estimado_min",
    "costo_estimado_usd", "duracion_s", "reutilizada", "linea_base", "version_modelo",
]


def _asegurar() -> None:
    for c in (CARPETA, RESULTADOS, MODELOS):
        c.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- línea base
def guardar_linea_base(pob: Poblacion) -> None:
    _asegurar()
    pob.datos.to_csv(CARPETA / "linea_base.csv", index=False, encoding="utf-8")
    info = {"version": pob.version, "n": pob.n, "semilla": pob.semilla, "creada": pob.creada, "origen": pob.origen,
            "version_generador": pob.version_generador}
    (CARPETA / "linea_base.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")


def info_linea_base() -> dict | None:
    ruta = CARPETA / "linea_base.json"
    if not ruta.exists() or not (CARPETA / "linea_base.csv").exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def cargar_linea_base(tipos: dict) -> Poblacion | None:
    info = info_linea_base()
    if info is None:
        return None
    datos = pd.read_csv(CARPETA / "linea_base.csv", dtype=tipos, keep_default_na=False, encoding="utf-8")
    return Poblacion(datos=datos, **info)


# ---------------------------------------------------------------- modelo
def ruta_modelo(version: str) -> Path:
    _asegurar()
    return MODELOS / f"{version}.joblib"


def guardar_modelo(objeto, version: str) -> None:
    joblib.dump(objeto, ruta_modelo(version))


def cargar_modelo(version: str):
    ruta = ruta_modelo(version)
    return joblib.load(ruta) if ruta.exists() else None


# ---------------------------------------------------------------- resultados
def guardar_resultado(ejecucion: Ejecucion, resumen: dict, riesgos: pd.DataFrame, poblacion_r1: pd.DataFrame) -> None:
    _asegurar()
    carpeta = RESULTADOS / ejecucion.id
    carpeta.mkdir(parents=True, exist_ok=True)
    datos = {"ejecucion": asdict(ejecucion), **resumen}
    (carpeta / "resumen.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    riesgos.to_csv(carpeta / "riesgos.csv", index=False, encoding="utf-8")
    poblacion_r1.to_csv(carpeta / "poblacion_r1.csv", index=False, encoding="utf-8")


def listar_resultados() -> list[dict]:
    """Todos los resultados guardados, del más reciente al más antiguo."""
    if not RESULTADOS.exists():
        return []
    salida = []
    for ruta in RESULTADOS.glob("*/resumen.json"):
        try:
            salida.append(json.loads(ruta.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(salida, key=lambda d: d["ejecucion"]["fecha"], reverse=True)


def buscar_por_clave(clave: str) -> dict | None:
    for r in listar_resultados():
        if r["ejecucion"]["clave"] == clave:
            return r
    return None


def cargar_riesgos(id_ejecucion: str) -> pd.DataFrame:
    return pd.read_csv(RESULTADOS / id_ejecucion / "riesgos.csv", encoding="utf-8")


# ---------------------------------------------------------------- registro
def registrar(fila: dict) -> None:
    _asegurar()
    nueva = pd.DataFrame([{c: fila.get(c, "") for c in COLUMNAS_REGISTRO}])
    nueva.to_csv(REGISTRO, mode="a", header=not REGISTRO.exists(), index=False, encoding="utf-8")


def cargar_registro() -> pd.DataFrame:
    if not REGISTRO.exists():
        return pd.DataFrame(columns=COLUMNAS_REGISTRO)
    return pd.read_csv(REGISTRO, encoding="utf-8", keep_default_na=False)
