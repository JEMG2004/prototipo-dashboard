"""Simulador de políticas de permanencia: prototipo del tablero (sección 7 del Plan).

Ejecutar desde esta carpeta:  streamlit run app.py
Publicado (render.yaml): pide la clave de la variable CLAVE_ACCESO antes de mostrar las pantallas.
"""
import streamlit as st

from interfaz import acceso
from interfaz import componentes as ui

st.set_page_config(page_title="Simulador de permanencia", page_icon=":material/school:", layout="wide")

if not acceso.acceso_permitido():
    st.stop()

ui.preservar_formularios()

paginas = {
    "Simulación": [
        st.Page("interfaz/linea_base.py", title="Línea base", icon=":material/groups:", default=True),
        st.Page("interfaz/escenario.py", title="Escenario", icon=":material/tune:"),
        st.Page("interfaz/resultados.py", title="Resultados", icon=":material/compare_arrows:"),
    ],
    "Transparencia": [
        st.Page("interfaz/supuestos.py", title="Supuestos", icon=":material/fact_check:"),
        st.Page("interfaz/diagnostico.py", title="Diagnóstico", icon=":material/troubleshoot:"),
        st.Page("interfaz/registro.py", title="Registro", icon=":material/receipt_long:"),
    ],
}
pagina = st.navigation(paginas)
ui.barra_lateral()
pagina.run()
