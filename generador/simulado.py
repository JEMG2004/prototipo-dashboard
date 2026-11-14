"""Generador simulado: hace el papel del LLM en el prototipo.

No llama a ninguna API ni gasta tokens. Genera estudiantes sintéticos siguiendo
el catálogo (las metas de cada variable) y las reglas (las relaciones entre
variables y las hipótesis sobre la deserción), que es lo mismo que el prompt
le pedirá al LLM. Así se puede probar todo el tablero antes de conectar el LLM.

Cómo genera: cada variable con "padres" se obtiene de una escala latente
(la suma de los efectos de sus padres más ruido) que luego se corta para que
las proporciones coincidan con la referencia del catálogo. Los cortes se
calibran una vez con una muestra grande, así que las metas se cumplen sin
importar el tamaño de la población.

Para cambiarlo por el LLM: escribir otra clase con los mismos métodos públicos
(generar, regenerar_variable, descendientes, prob_desercion) que llame a la API
con la plantilla del prompt y valide cada lote (ver README).
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from generador.catalogo import Catalogo, Reglas

VERSION_GENERADOR = "simulado-v1"


class GeneradorSimulado:
    nombre = "Generador simulado (sin LLM)"

    def __init__(self, catalogo: Catalogo, reglas: Reglas, n_calibracion: int = 80_000, semilla_calibracion: int = 12345):
        self.catalogo = catalogo
        self.reglas = reglas
        self.padres = {v: [r for r in reglas.relaciones if r.destino == v] for v in catalogo.nombres}
        self.orden = self._orden_topologico()
        self._cal: dict[str, dict] = {}
        self._intercepto = 0.0
        self.version = "-".join([VERSION_GENERADOR, catalogo.huella, reglas.huella])
        self._calibrar(n_calibracion, semilla_calibracion)

    # ------------------------------------------------------------------ estructura
    def _orden_topologico(self) -> list[str]:
        pendientes = {v: {r.origen for r in self.padres[v]} for v in self.catalogo.nombres}
        orden: list[str] = []
        while pendientes:
            listas = [v for v in self.catalogo.nombres if v in pendientes and not (pendientes[v] - set(orden))]
            if not listas:
                raise ValueError("Las relaciones del archivo de reglas forman un ciclo.")
            orden.append(listas[0])
            del pendientes[listas[0]]
        return orden

    def descendientes(self, variables: list[str]) -> list[str]:
        """Las variables que dependen (directa o indirectamente) de las dadas, en orden de generación."""
        hijos: dict[str, set] = {v: set() for v in self.catalogo.nombres}
        for r in self.reglas.relaciones:
            hijos[r.origen].add(r.destino)
        vistos: set[str] = set()
        pila = list(variables)
        while pila:
            for h in hijos[pila.pop()]:
                if h not in vistos:
                    vistos.add(h)
                    pila.append(h)
        return [v for v in self.orden if v in vistos]

    # ------------------------------------------------------------------ muestreo
    def _latente(self, df: pd.DataFrame, v: str, rng: np.random.Generator) -> np.ndarray:
        z = np.zeros(len(df))
        for r in self.padres[v]:
            z += r.contribucion(df[r.origen])
        return z + rng.standard_normal(len(df))

    def _muestrear_raiz(self, v: str, n: int, rng: np.random.Generator) -> np.ndarray:
        var = self.catalogo[v]
        if var.es_numerica:
            p = np.array([i["proporcion"] for i in var.intervalos], float)
            cual = rng.choice(len(var.intervalos), size=n, p=p / p.sum())
            desde = np.array([var.intervalos[k]["desde"] for k in cual], float)
            hasta = np.array([var.intervalos[k]["hasta"] for k in cual], float)
            if var.decimales == 0:
                return rng.integers(desde.astype(int), hasta.astype(int) + 1)
            return np.round(rng.uniform(desde, hasta), var.decimales)
        etiquetas, p = var.categorias_referencia()
        idx = rng.choice(len(etiquetas), size=n, p=p / p.sum())
        return np.asarray(var.valores, dtype=object)[idx] if var.tipo != "ordinal" else np.asarray(var.valores)[idx]

    def _discretizar(self, v: str, z: np.ndarray) -> np.ndarray:
        var = self.catalogo[v]
        cal = self._cal[v]
        if var.es_numerica:
            u = np.interp(z, cal["z"], cal["u"])
            cu = np.array([c[0] for c in var.cuantiles], float)
            cx = np.array([c[1] for c in var.cuantiles], float)
            x = np.interp(u, cu, cx)
            return np.round(np.clip(x, var.minimo, var.maximo), var.decimales)
        idx = np.searchsorted(cal["cortes"], z)
        valores = np.asarray(var.valores) if var.tipo == "ordinal" else np.asarray(var.valores, dtype=object)
        return valores[idx]

    def _calibrar(self, n: int, semilla: int) -> None:
        rng = np.random.default_rng(semilla)
        df = pd.DataFrame(index=range(n))
        for v in self.orden:
            var = self.catalogo[v]
            if not self.padres[v]:
                df[v] = self._muestrear_raiz(v, n, rng)
                continue
            z = self._latente(df, v, rng)
            if var.es_numerica:
                if not var.cuantiles:
                    raise ValueError(f"{v} tiene padres y es numérica: necesita 'cuantiles' en el catálogo.")
                q = np.linspace(0, 1, 2001)
                self._cal[v] = {"z": np.quantile(z, q), "u": q}
            else:
                _, p = var.categorias_referencia()
                self._cal[v] = {"cortes": np.quantile(z, np.cumsum(p)[:-1])}
            df[v] = self._discretizar(v, z)
        # Intercepto de la marca de desertor para que la tasa sea la del archivo de reglas.
        logit = self._logit_desercion(df, 0.0)
        bajo, alto = -10.0, 10.0
        for _ in range(60):
            medio = (bajo + alto) / 2
            if (1 / (1 + np.exp(-(logit + medio)))).mean() < self.reglas.tasa_objetivo:
                bajo = medio
            else:
                alto = medio
        self._intercepto = (bajo + alto) / 2

    # ------------------------------------------------------------------ API pública
    def _logit_desercion(self, df: pd.DataFrame, intercepto: float | None = None) -> np.ndarray:
        z = np.full(len(df), self._intercepto if intercepto is None else intercepto)
        for r in self.reglas.desercion:
            z = z + r.contribucion(df[r.origen])
        return z

    def prob_desercion(self, df: pd.DataFrame) -> np.ndarray:
        """Probabilidad de la marca de desertor según las reglas (la "verdad" del simulador)."""
        return 1 / (1 + np.exp(-self._logit_desercion(df)))

    def generar(self, n: int, semilla: int, con_desertor: bool = True) -> pd.DataFrame:
        """Una población nueva. Con la misma semilla sale la misma población."""
        rng = np.random.default_rng(semilla)
        df = pd.DataFrame({"id": [f"E{i + 1:05d}" for i in range(n)]})
        for v in self.orden:
            if not self.padres[v]:
                df[v] = self._muestrear_raiz(v, n, rng)
            else:
                df[v] = self._discretizar(v, self._latente(df, v, rng))
        columnas = ["id"] + self.catalogo.nombres
        if con_desertor:
            df["desertor"] = np.where(rng.random(n) < self.prob_desercion(df), "Sí", "No")
            columnas.append("desertor")
        return df[columnas]

    def regenerar_variable(self, filas: pd.DataFrame, v: str, rng: np.random.Generator) -> np.ndarray:
        """Vuelve a generar una variable para las filas dadas, a partir de los valores actuales de sus padres."""
        if not self.padres[v]:
            return self._muestrear_raiz(v, len(filas), rng)
        return self._discretizar(v, self._latente(filas, v, rng))

    def huella_poblacion(self, n: int, semilla: int) -> str:
        texto = f"{self.version}|{n}|{semilla}"
        return "base-" + hashlib.sha1(texto.encode()).hexdigest()[:8]
