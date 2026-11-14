"""Comprueba que, con un disco persistente vacío (CARPETA_GENERADOS), la app copie lo que dejó precalcular.py.

Es lo que pasa la primera vez que arranca en Fly.io con su volumen, o en Render con su disco.
Uso (desde la carpeta del prototipo):  python -m pruebas.prueba_semilla
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    subprocess.run([sys.executable, "precalcular.py"], cwd=RAIZ, check=True, capture_output=True)
    with tempfile.TemporaryDirectory() as tmp:
        disco = Path(tmp) / "generados"
        entorno = dict(os.environ, CARPETA_GENERADOS=str(disco))
        codigo = ("from interfaz import estado\n"
                  "pob = estado.linea_base()\n"
                  "print(pob.n, pob.origen)")
        salida = subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=entorno, check=True,
                                capture_output=True, text=True)
        archivos = sorted(p.relative_to(disco).as_posix() for p in disco.rglob("*") if p.is_file())
        assert "linea_base.csv" in archivos and "linea_base.json" in archivos, archivos
        assert any(a.startswith("modelo/") for a in archivos), archivos
        print(f"El disco vacío recibió {len(archivos)} archivos de datos/generados; la línea base cargó "
              f"({salida.stdout.strip().splitlines()[-1]}).")


if __name__ == "__main__":
    main()
