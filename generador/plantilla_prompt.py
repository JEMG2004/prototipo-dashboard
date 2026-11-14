"""Plantilla del prompt (sección 7.5 del Plan).

El coordinador nunca edita el prompt: mueve controles y la herramienta llena la
plantilla con Jinja2. La plantilla tiene partes fijas (contexto, diccionario de
variables, formato de salida, validaciones) y partes con parámetros (metas de
cada variable y relaciones). Cada ejecución guarda la versión del prompt.

Lo que dejó la prueba de generación para la plantilla:
- no poner reglas duras que los datos no cumplen (las relaciones van como tendencias);
- dar las metas en porcentajes, no en conteos exactos;
- describir las relaciones débiles;
- medir las copias (se hace en escenarios/aplicar.py, frente a la población base).

A la API solo llegan estadísticas agregadas y reglas: ninguna fila de estudiantes.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from dominio import Escenario, _num
from escenarios.aplicar import comprobar

VERSION_PROMPT = "prompt-v1"
CARPETA = Path(__file__).resolve().parent / "plantillas"
PROGRAMA = "Ingeniería de Sistemas de la Universidad del Cauca"


def estimar_tokens(texto: str) -> int:
    """Aproximación: unos 4 caracteres por token."""
    return max(1, round(len(texto) / 4))


def _pct(x: float) -> str:
    return f"{_num(100 * x, 0)} %"


def _reparto(var, serie, omitir_ceros: bool = False) -> str:
    etiquetas, _ = var.categorias_referencia()
    dist = var.distribucion(serie)
    if var.tipo == "binaria":
        return f"«Sí» {_pct(dist[list(var.valores).index('Sí')])}"
    return "; ".join(f"{e}: {_pct(p)}" for e, p in zip(etiquetas, dist) if not (omitir_ceros and p < 0.005))


class PlantillaPrompt:
    def __init__(self, catalogo, reglas):
        self.catalogo = catalogo
        self.reglas = reglas
        self.env = Environment(loader=FileSystemLoader(str(CARPETA)), autoescape=False, trim_blocks=True,
                               lstrip_blocks=True, undefined=StrictUndefined, keep_trailing_newline=True)
        contenido = "".join(p.read_text(encoding="utf-8") for p in sorted(CARPETA.glob("*.j2")))
        self.huella = hashlib.sha1(contenido.encode("utf-8")).hexdigest()[:8]
        self.version = f"{VERSION_PROMPT}-{self.huella}"

    def _diccionario(self) -> list[dict]:
        filas = []
        for v in self.catalogo:
            pregunta = v.pregunta.strip()
            if not pregunta.endswith((".", "?")):
                pregunta += "."
            filas.append({"nombre": v.nombre, "tipo": v.tipo_legible, "pregunta": pregunta, "valores": v.describir_valores()})
        return filas

    def _debiles(self, solo_relaciones_de: list[str] | None = None) -> list[str]:
        if solo_relaciones_de is None:
            return [r.descripcion for r in self.reglas.reglas if r.fuerza == "débil"]
        return [r.descripcion for r in self.reglas.relaciones if r.fuerza == "débil" and r.destino in solo_relaciones_de]

    def linea_base(self, muestra, n_lote: int = 30) -> str:
        """Prompt para generar la población (la línea base y la de entrenamiento)."""
        des = muestra[muestra["desertor"] == "Sí"]
        nod = muestra[muestra["desertor"] == "No"]
        distribuciones = [{"etiqueta": v.etiqueta, "desertores": _reparto(v, des[v.nombre]),
                           "no_desertores": _reparto(v, nod[v.nombre])} for v in self.catalogo]
        return self.env.get_template("linea_base.j2").render(
            programa=PROGRAMA,
            variables=self._diccionario(),
            claves=", ".join(self.catalogo.nombres + ["desertor"]),
            n_lote=n_lote,
            tasa=_num(100 * self.reglas.tasa_objetivo, 0),
            distribuciones=distribuciones,
            relaciones=[r.descripcion for r in self.reglas.relaciones],
            debiles=self._debiles(),
        )

    def escenario(self, esc: Escenario, base, generador, params: dict, n_lote: int = 30) -> str:
        """Prompt para volver a generar solo el segmento que toca la política."""
        seg = esc.segmento.mascara(base)
        palancas = [p.variable for p in esc.palancas]
        regeneradas = generador.descendientes(palancas)
        filas = comprobar(base, [base], esc, self.catalogo, seg, params) if seg.any() else []
        metas = []
        for f, p in zip(filas, esc.palancas):
            var = self.catalogo[f["variable"]]
            if f["es_proporcion"]:
                metas.append(f"{var.etiqueta}: el porcentaje con «{p.desde}» pasa de {_pct(f['antes'])} a alrededor de "
                             f"{_pct(f['meta'])}, porque la política llega al {_num(100 * p.cobertura, 0)} % de quienes "
                             f"tenían «{p.desde}» y pasan a «{p.hacia}».")
            else:
                antes = var.formatear(f["antes"]) if var.es_numerica else _num(f["antes"], 1)
                meta = var.formatear(f["meta"]) if var.es_numerica else _num(f["meta"], 1)
                cambio = f["cambio"].split(": ", 1)[-1]
                metas.append(f"{var.etiqueta}: {cambio}. La media en el segmento pasa de {antes} a alrededor de "
                             f"{meta}, sin salir de {var.describir_valores()}.")
        sub = base.loc[seg]
        contexto = [f"{v.etiqueta}: {_reparto(v, sub[v.nombre], omitir_ceros=True)}" for v in self.catalogo
                    if v.nombre not in palancas and v.nombre not in regeneradas] if seg.any() else []
        relaciones = [r.descripcion for r in self.reglas.relaciones if r.destino in regeneradas]
        return self.env.get_template("escenario.j2").render(
            programa=PROGRAMA,
            variables=self._diccionario(),
            claves=", ".join(self.catalogo.nombres),
            n_lote=n_lote,
            segmento=esc.segmento.describir(self.catalogo),
            n_segmento=int(seg.sum()),
            politica=esc.politica,
            metas=metas,
            contexto=contexto,
            regeneradas=[self.catalogo[v].etiqueta for v in regeneradas],
            relaciones=relaciones,
            debiles=self._debiles(regeneradas),
        )
