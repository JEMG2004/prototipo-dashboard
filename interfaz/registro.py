"""Pantalla 6: el registro de ejecuciones (sección 7.3). Sirve también para el análisis de costos."""
import pandas as pd
import streamlit as st

from datos import repositorio as repo
from interfaz import componentes as ui
from interfaz import estado
from interfaz import graficos as g

r = estado.recursos()
ui.encabezado("Registro", "Cada ejecución: modo, réplicas, versión del prompt, tokens y costo estimados.")
ui.proposito("llevar la cuenta de cada ejecución para el análisis de costos del proyecto (actividad 1.4): cuántas "
             "llamadas al modelo de lenguaje haría, cuántos tokens y cuánto costaría, y cuántas veces se reutilizó un "
             "resultado guardado en vez de pagarlo de nuevo.")

registro = repo.cargar_registro()
if registro.empty:
    st.info("Todavía no hay ejecuciones.", icon=":material/info:")
    st.page_link("interfaz/escenario.py", label="Crear un escenario", icon=":material/arrow_forward:")
    st.stop()

numericas = ["replicas", "estudiantes_segmento", "estudiantes_cambiados", "estudiantes_regenerados",
             "tokens_entrada_estimados", "llamadas_estimadas", "tiempo_estimado_min", "costo_estimado_usd", "duracion_s"]
for c in numericas:
    registro[c] = pd.to_numeric(registro[c], errors="coerce").fillna(0)
registro = registro.sort_values("fecha", ascending=False)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Ejecuciones", ui.num(len(registro)), border=True)
k2.metric("Reutilizadas", ui.num((registro["reutilizada"] == "Sí").sum()), border=True,
          help="Escenarios repetidos que se sacaron de lo guardado: no se pagan de nuevo.")
k3.metric("Generados con el LLM", ui.num(registro["estudiantes_regenerados"].sum()), border=True,
          help="Estudiantes que habría generado el LLM (en el prototipo, el simulador).")
k4.metric("Costo estimado", ui.usd(registro["costo_estimado_usd"].sum()), border=True,
          help=f"Si se hubiera usado {r.params['llm_referencia']['modelo']}, con lo medido en la prueba de generación. "
               "En el prototipo el costo real es cero.")

vista = pd.DataFrame({
    "Fecha": registro["fecha"].map(ui.fecha),
    "Escenario": registro["escenario"],
    "Modo": registro["modo"].map({"ajuste": "ajuste directo", "regeneracion": "regeneración"}),
    "Réplicas": registro["replicas"].astype(int),
    "Costo estimado (US$)": registro["costo_estimado_usd"].round(4),
    "Tokens de entrada (estimados)": registro["tokens_entrada_estimados"].astype(int),
    "Llamadas (estimadas)": registro["llamadas_estimadas"].astype(int),
    "Tiempo con el LLM (min)": registro["tiempo_estimado_min"].round(1),
    "Generados con el LLM": registro["estudiantes_regenerados"].astype(int),
    "Reutilizada": registro["reutilizada"],
    "Versión del prompt": registro["version_prompt"],
    "Huella del prompt": registro["hash_prompt"],
    "Modelo de lenguaje": registro["modelo_llm"],
    "Generador": registro["generador"],
    "Segmento": registro["segmento"],
    "Estudiantes con cambios": registro["estudiantes_cambiados"].astype(int),
    "Duración real (s)": registro["duracion_s"].round(2),
    "Línea base": registro["linea_base"],
    "Modelo predictivo": registro["version_modelo"],
})
st.dataframe(vista, hide_index=True, width="stretch", column_config=g.formato_tabla(vista))
st.download_button("Descargar el registro (CSV)", registro.to_csv(index=False).encode("utf-8"),
                   file_name="registro_ejecuciones.csv", mime="text/csv", icon=":material/download:")
st.caption("Los tokens se estiman con unos 4 caracteres por token. Sin filas reales en el prompt, cada llamada debería "
           "salir más pequeña y más barata que en la prueba, así que el costo está más bien sobreestimado.")
