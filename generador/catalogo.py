"""Carga el catálogo, las reglas y los parámetros desde los YAML de la carpeta datos."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from dominio import ReglaNegocio, Variable

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "datos"


def _leer(nombre: str) -> dict:
    return yaml.safe_load((CARPETA_DATOS / nombre).read_text(encoding="utf-8"))


def _huella(contenido) -> str:
    """Huella del contenido que usa el generador, no del texto del archivo: así, cambiar un comentario o una
    explicación no obliga a regenerar la línea base ni a reentrenar el modelo (con el LLM, eso sería pagar de nuevo)."""
    texto = json.dumps(contenido, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:8]


# Campos de cada variable que solo explican (no cambian lo que se genera).
_SOLO_TEXTO = {"etiqueta", "pregunta", "factor_men", "categoria_tabla12", "fuente_referencia", "uso", "nota"}


class Catalogo:
    def __init__(self, variables: list[Variable], version: str, huella: str, criterios: list[str] | None = None,
                 no_incluidas: list[dict] | None = None):
        self.variables = variables
        self.version = version
        self.huella = huella
        self.criterios = criterios or []          # por qué estas variables
        self.no_incluidas = no_incluidas or []    # las de la Tabla 12 que no entraron, con el motivo
        self._por_nombre = {v.nombre: v for v in variables}

    def __getitem__(self, nombre: str) -> Variable:
        return self._por_nombre[nombre]

    def __iter__(self):
        return iter(self.variables)

    def __contains__(self, nombre: str) -> bool:
        return nombre in self._por_nombre

    @property
    def nombres(self) -> list[str]:
        return [v.nombre for v in self.variables]

    @property
    def palancas(self) -> list[Variable]:
        return [v for v in self.variables if v.palanca]


@dataclass
class Reglas:
    reglas: list[ReglaNegocio]
    tasa_objetivo: float
    version: str
    huella: str

    @property
    def relaciones(self) -> list[ReglaNegocio]:
        return [r for r in self.reglas if r.tipo == "relacion"]

    @property
    def desercion(self) -> list[ReglaNegocio]:
        return [r for r in self.reglas if r.tipo == "desercion"]


def cargar_catalogo() -> Catalogo:
    datos = _leer("catalogo.yaml")
    variables = []
    for d in datos["variables"]:
        if d["tipo"] not in ("binaria", "ordinal", "categorica", "numerica"):
            raise ValueError(f"Tipo desconocido en {d['nombre']}: {d['tipo']}")
        if d.get("rango") is not None:
            d["rango"] = tuple(d["rango"])
        variables.append(Variable(**d))
    for v in variables:
        _, proporciones = v.categorias_referencia()
        if abs(proporciones.sum() - 1) > 1e-6:
            raise ValueError(f"La referencia de {v.nombre} no suma 1 ({proporciones.sum():.3f}).")
    huella = _huella([{k: x for k, x in d.items() if k not in _SOLO_TEXTO} for d in datos["variables"]])
    return Catalogo(variables, datos.get("version", "catalogo"), huella, datos.get("criterios_seleccion"),
                    datos.get("no_incluidas"))


def cargar_reglas(catalogo: Catalogo) -> Reglas:
    datos = _leer("reglas.yaml")
    reglas = [ReglaNegocio(**r) for r in datos["reglas"]]
    for r in reglas:
        if r.origen not in catalogo:
            raise ValueError(f"La regla {r.id} usa una variable que no está en el catálogo: {r.origen}")
        if r.tipo == "relacion" and r.destino not in catalogo:
            raise ValueError(f"La regla {r.id} genera una variable que no está en el catálogo: {r.destino}")
    # Las descripciones y fuentes solo explican; la huella usa lo que cambia la generación.
    contenido = {"tasa": datos["tasa_desercion_objetivo"],
                 "reglas": [{k: x for k, x in r.items() if k not in ("descripcion", "fuente", "fuerza")}
                            for r in datos["reglas"]]}
    return Reglas(reglas, float(datos["tasa_desercion_objetivo"]), datos.get("version", "reglas"), _huella(contenido))


def cargar_parametros() -> dict:
    return _leer("parametros.yaml")
