"""Recorre todas las pantallas sin abrir el navegador y falla si alguna lanza un error.

Uso (desde la carpeta del prototipo):  python -m pruebas.prueba_app
Ejecuta además dos escenarios (uno por modo) y las pruebas del diagnóstico.
Deja resultados en datos/generados; se pueden borrar sin problema.
"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")

PAGINAS = ["interfaz/linea_base.py", "interfaz/escenario.py", "interfaz/resultados.py", "interfaz/supuestos.py",
           "interfaz/diagnostico.py", "interfaz/registro.py"]


def revisar(at: AppTest, donde: str) -> None:
    if at.exception:
        raise AssertionError(f"{donde}: {[e.value for e in at.exception]}")
    if not any("Para qué sirve" in c.value for c in at.caption):
        raise AssertionError(f"{donde}: falta la explicación de para qué sirve la pantalla")
    avisos = [w.value for w in at.warning]
    print(f"  {donde}: bien ({len(avisos)} avisos)")
    for a in avisos:
        print(f"     aviso: {a[:140]}")


def boton(at: AppTest, texto: str):
    for b in at.button:
        if b.label == texto:
            return b
    raise AssertionError(f"No encontré el botón «{texto}»")


def main() -> None:
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    revisar(at, "inicio")
    for p in PAGINAS:
        at.switch_page(p)
        at.run()
        revisar(at, p)

    at.switch_page("interfaz/escenario.py")
    at.run()
    boton(at, "Ejecutar escenario").click()
    at.run()
    revisar(at, "ejecutar (ajuste directo)")
    at.radio(key="esc_modo").set_value("regeneracion")
    at.run()
    boton(at, "Ejecutar escenario").click()
    at.run()
    revisar(at, "ejecutar (regeneración)")
    boton(at, "Ejecutar escenario").click()
    at.run()
    revisar(at, "ejecutar otra vez (debe reutilizar)")
    assert any("reutiliza" in i.value for i in at.info), "El segundo intento debía reutilizar el resultado"

    at.selectbox(key="esc_politica").set_value("Paquete: apoyo económico, mentorías y psicosocial")
    at.run()
    boton(at, "Ejecutar escenario").click()
    at.run()
    revisar(at, "ejecutar paquete (regeneración)")

    for p in ("interfaz/resultados.py", "interfaz/registro.py"):
        at.switch_page(p)
        at.run()
        revisar(at, p + " con resultados")

    at.switch_page("interfaz/diagnostico.py")
    at.run()
    boton(at, "Correr la prueba").click()
    at.run()
    revisar(at, "diagnóstico con pruebas")
    print("Todas las pantallas funcionan.")


if __name__ == "__main__":
    main()
