"""Comprueba la clave de acceso del tablero publicado (interfaz/acceso.py).

Uso (desde la carpeta del prototipo):  python -m pruebas.prueba_acceso
Sin la clave no se ve ninguna pantalla; con una clave equivocada sale un error; con la buena se ve la línea base.
"""
from __future__ import annotations

import os
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
CLAVE = "clave-de-prueba"


def enviar(at: AppTest, texto: str) -> None:
    at.text_input[0].input(texto)
    at.button[0].click()
    at.run()


def main() -> None:
    os.environ["CLAVE_ACCESO"] = CLAVE
    try:
        at = AppTest.from_file(APP, default_timeout=300)
        at.run()
        assert not at.exception, [e.value for e in at.exception]
        assert [t.label for t in at.text_input] == ["Clave de acceso"]
        assert not at.metric, "Sin la clave no debe verse ninguna pantalla"

        enviar(at, "otra")
        assert any("no es la clave" in e.value for e in at.error), "Debía avisar que la clave es incorrecta"
        assert not at.metric

        enviar(at, CLAVE)
        assert not at.exception, [e.value for e in at.exception]
        assert at.metric, "Con la clave debía verse la línea base"
        print(f"La clave de acceso funciona: {len(at.metric)} indicadores en la línea base.")
    finally:
        os.environ.pop("CLAVE_ACCESO", None)


if __name__ == "__main__":
    main()
