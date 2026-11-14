"""Clases del dominio (sección 7.8 del Plan).

Variable, Regla de negocio, Parámetro de política, Escenario, Población,
Ejecución y Resultado. Son las mismas que irán en el diagrama de clases.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

TIPOS = ("binaria", "ordinal", "categorica", "numerica")


def _num(x: float, decimales: int = 1) -> str:
    """Número con coma decimal, para los textos que ve el coordinador."""
    texto = f"{x:,.{decimales}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


@dataclass
class Variable:
    """Una fila del catálogo (sección 7.4)."""

    nombre: str
    etiqueta: str
    pregunta: str
    factor_men: str
    categoria_tabla12: str
    tipo: str
    valores: list = field(default_factory=list)
    rango: tuple | None = None
    decimales: int = 0
    ordenada: bool = False
    referencia: dict = field(default_factory=dict)
    intervalos: list = field(default_factory=list)
    cuantiles: list = field(default_factory=list)
    fuente_variable: str = "Rosero y Velasco (2026), Tabla 12 y formulario"
    fuente_referencia: str = "Supuesto."
    palanca: bool = False
    uso: str = ""
    nota: str = ""

    @property
    def es_numerica(self) -> bool:
        return self.tipo == "numerica"

    @property
    def es_ordenable(self) -> bool:
        """Se puede filtrar por rango y sumar (numérica u ordinal)."""
        return self.tipo in ("numerica", "ordinal")

    @property
    def minimo(self) -> float:
        return float(self.rango[0]) if self.rango else float(min(self.valores))

    @property
    def maximo(self) -> float:
        return float(self.rango[1]) if self.rango else float(max(self.valores))

    def formatear(self, x: Any) -> str:
        if self.es_numerica:
            return _num(float(x), self.decimales)
        if self.tipo == "ordinal":
            x = float(x)
            return str(int(round(x))) if abs(x - round(x)) < 1e-9 else _num(x, 1)
        return str(x)

    def describir_valores(self) -> str:
        if self.es_numerica:
            detalle = "número entero" if self.decimales == 0 else f"con {'un decimal' if self.decimales == 1 else f'{self.decimales} decimales'}"
            return f"{self.formatear(self.minimo)} a {self.formatear(self.maximo)}, {detalle}"
        if self.tipo == "ordinal":
            return f"enteros de {self.formatear(self.minimo)} a {self.formatear(self.maximo)}"
        return " / ".join(str(v) for v in self.valores)

    @property
    def tipo_legible(self) -> str:
        return {"binaria": "binaria", "ordinal": "ordinal", "categorica": "categórica", "numerica": "numérica"}[self.tipo]

    def etiquetas_intervalos(self) -> list[str]:
        return [f"{self.formatear(i['desde'])}–{self.formatear(i['hasta'])}" for i in self.intervalos]

    def bordes_intervalos(self) -> list[float]:
        """Bordes para agrupar valores numéricos en los intervalos de referencia."""
        bordes = [self.intervalos[0]["desde"] - 1e-9]
        for a, b in zip(self.intervalos[:-1], self.intervalos[1:]):
            bordes.append((a["hasta"] + b["desde"]) / 2)
        bordes.append(self.intervalos[-1]["hasta"] + 1e-9)
        return bordes

    def categorias_referencia(self) -> tuple[list, np.ndarray]:
        """Categorías (o intervalos) y proporciones de referencia, en orden."""
        if self.es_numerica:
            return self.etiquetas_intervalos(), np.array([i["proporcion"] for i in self.intervalos], float)
        return list(self.valores), np.array([self.referencia[v] for v in self.valores], float)

    def agrupar(self, serie: pd.Series) -> pd.Series:
        """Convierte los valores en las categorías de referencia (intervalos si es numérica)."""
        if self.es_numerica:
            return pd.cut(serie.astype(float), bins=self.bordes_intervalos(), labels=self.etiquetas_intervalos())
        return pd.Categorical(serie, categories=list(self.valores), ordered=self.tipo == "ordinal" or self.ordenada)

    def distribucion(self, serie: pd.Series) -> np.ndarray:
        etiquetas, _ = self.categorias_referencia()
        grupos = pd.Series(self.agrupar(serie))
        conteo = grupos.value_counts().reindex(etiquetas, fill_value=0).to_numpy(float)
        total = conteo.sum()
        return conteo / total if total else conteo


@dataclass
class ReglaNegocio:
    """Un supuesto: cómo se genera una variable o cómo afecta la marca de desertor."""

    id: str
    tipo: str            # "relacion" | "desercion"
    destino: str
    origen: str
    forma: str           # "lineal" | "categoria"
    efecto: Any
    centro: float = 0.0
    fuerza: str = ""
    descripcion: str = ""
    fuente: str = "Supuesto."

    def contribucion(self, serie: pd.Series) -> np.ndarray:
        if self.forma == "lineal":
            return self.efecto * (serie.to_numpy(dtype=float) - self.centro)
        valores = serie.map(lambda x: self.efecto.get(x, 0.0))
        return valores.to_numpy(dtype=float)

    def describir_efecto(self) -> str:
        if self.forma == "lineal":
            return f"{_num(self.efecto, 2)} por unidad (alrededor de {_num(self.centro, 1)})"
        return "; ".join(f"{k}: {_num(v, 2)}" for k, v in self.efecto.items())


@dataclass
class Condicion:
    """Una condición del segmento: un rango (numéricas y ordinales) o una lista de categorías."""

    variable: str
    valores: list | None = None
    minimo: float | None = None
    maximo: float | None = None

    def mascara(self, df: pd.DataFrame) -> np.ndarray:
        serie = df[self.variable]
        if self.valores is not None:
            return serie.isin(self.valores).to_numpy()
        x = serie.to_numpy(dtype=float)
        m = np.ones(len(x), bool)
        if self.minimo is not None:
            m &= x >= self.minimo - 1e-9
        if self.maximo is not None:
            m &= x <= self.maximo + 1e-9
        return m

    def describir(self, var: Variable) -> str:
        if self.valores is not None:
            return f"{var.etiqueta}: {', '.join(str(v) for v in self.valores)}"
        return f"{var.etiqueta} entre {var.formatear(self.minimo)} y {var.formatear(self.maximo)}"


@dataclass
class Segmento:
    """A quién va la política. Sin condiciones es toda la población."""

    condiciones: list[Condicion] = field(default_factory=list)

    def mascara(self, df: pd.DataFrame) -> np.ndarray:
        m = np.ones(len(df), bool)
        for c in self.condiciones:
            m &= c.mascara(df)
        return m

    def describir(self, catalogo) -> str:
        if not self.condiciones:
            return "Toda la población"
        return " y ".join(c.describir(catalogo[c.variable]) for c in self.condiciones)


OPERACIONES = {
    "multiplicar": "Multiplicar por",
    "sumar": "Sumar",
    "fijar_minimo": "Subir hasta un mínimo de",
    "fijar_maximo": "Bajar hasta un máximo de",
    "cambiar": "Cambiar de categoría",
}


def operaciones_para(var: Variable) -> list[str]:
    if var.tipo == "numerica":
        return ["multiplicar", "sumar", "fijar_minimo"]
    if var.tipo == "ordinal":
        return ["sumar", "fijar_maximo", "fijar_minimo"]
    return ["cambiar"]


@dataclass
class ParametroPolitica:
    """Una palanca: qué variable cambia, cómo y a qué proporción de los elegibles llega."""

    variable: str
    operacion: str
    valor: float | None = None
    desde: str | None = None
    hacia: str | None = None
    cobertura: float = 1.0

    def describir(self, var: Variable) -> str:
        quienes = {
            "cambiar": f"de quienes tienen «{self.desde}»",
            "fijar_minimo": "de quienes están por debajo",
            "fijar_maximo": "de quienes están por encima",
        }.get(self.operacion, "del segmento")
        cob = f" (llega al {_num(100 * self.cobertura, 0)} % {quienes})" if self.cobertura < 0.999 else ""
        if self.operacion == "cambiar":
            return f"{var.etiqueta}: de «{self.desde}» a «{self.hacia}»{cob}"
        if self.operacion == "multiplicar":
            pct = (self.valor - 1) * 100
            signo = "+" if pct >= 0 else "−"
            return f"{var.etiqueta}: ×{_num(self.valor, 2)} ({signo}{_num(abs(pct), 0)} %){cob}"
        if self.operacion == "sumar":
            signo = "+" if self.valor >= 0 else "−"
            return f"{var.etiqueta}: {signo}{var.formatear(abs(self.valor)) if var.es_numerica else _num(abs(self.valor), 0)}{cob}"
        if self.operacion == "fijar_minimo":
            return f"{var.etiqueta}: mínimo {var.formatear(self.valor)}{cob}"
        if self.operacion == "fijar_maximo":
            return f"{var.etiqueta}: máximo {var.formatear(self.valor)}{cob}"
        return f"{var.etiqueta}: {self.operacion}"


@dataclass
class Escenario:
    """Lo que define el coordinador en la pantalla Escenario."""

    nombre: str
    politica: str
    descripcion: str
    segmento: Segmento
    palancas: list[ParametroPolitica]
    modo: str = "ajuste"                 # "ajuste" | "regeneracion"
    replicas: int = 5
    semilla: int = 1
    efecto_esperado: float | None = None  # % de cambio en desertores esperados que anotó el coordinador

    def a_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, d: dict) -> "Escenario":
        d = dict(d)
        d["segmento"] = Segmento([Condicion(**c) for c in d["segmento"]["condiciones"]])
        d["palancas"] = [ParametroPolitica(**p) for p in d["palancas"]]
        return cls(**d)

    def clave(self, *versiones: str) -> str:
        """Identifica el resultado: si nada de esto cambia, no hay que volver a generar ni pagar."""
        parte = {
            "segmento": asdict(self.segmento),
            "palancas": [asdict(p) for p in self.palancas],
            "modo": self.modo,
            "replicas": self.replicas,
            "semilla": self.semilla,
            "versiones": list(versiones),
        }
        texto = json.dumps(parte, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]


@dataclass
class Poblacion:
    """Una población sintética guardada (la línea base)."""

    datos: pd.DataFrame
    version: str
    n: int
    semilla: int
    creada: str
    origen: str = "Generador simulado (sin LLM)"
    version_generador: str = ""


@dataclass
class Ejecucion:
    """Una corrida de un escenario: lo que va al registro."""

    id: str
    clave: str
    escenario: dict
    fecha: str
    duracion_s: float
    reutilizada: bool
    generador: str
    modelo_llm: str
    version_prompt: str
    hash_prompt: str
    tokens_entrada_estimados: int
    llamadas_estimadas: int
    estudiantes_regenerados: int
    tiempo_estimado_min: float
    costo_estimado_usd: float
    linea_base: str
    version_modelo: str


@dataclass
class Resultado:
    """Lo que se compara en la pantalla Resultados."""

    ejecucion_id: str
    base: dict
    replicas: list
    comprobacion: list
    clasificacion: dict
    copias_frente_base: float | None = None
