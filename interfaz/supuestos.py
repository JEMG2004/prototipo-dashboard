"""Pantalla 4: supuestos y límites (sección 7.2, paso 5)."""
import pandas as pd
import streamlit as st

from generador.plantilla_prompt import estimar_tokens
from interfaz import componentes as ui
from interfaz import estado
from interfaz import graficos as g

r = estado.recursos()
cat = r.catalogo
modelo = estado.modelo_actual()
m = modelo.metricas

ui.encabezado(
    "Supuestos",
    "De dónde sale cada número. Los resultados son estimaciones condicionadas a estos supuestos, "
    "no predicciones de lo que pasará en el programa.",
)
ui.proposito("dar transparencia: cada resultado depende de estos supuestos, así que el coordinador puede ver de dónde "
             "sale cada número y pedir cambios.")

st.info(
    "Todo lo que hay aquí es una hipótesis que hay que revisar con el coordinador antes de programar el prompt "
    "definitivo (PT 1.2). Los archivos están en la carpeta *datos*: se cambian sin tocar el código.",
    icon=":material/fact_check:",
)

t_var, t_reglas, t_modelo, t_prompt, t_limites = st.tabs(
    ["Variables", "Reglas", "Modelo", "Prompt de la línea base", "Límites"])

with t_var:
    ui.proposito("saber qué describe a cada estudiante sintético, de dónde sale cada variable y cuáles puede mover una "
                 "política. «¿Palanca? Sí» quiere decir que es un parámetro de política; las demás sirven para elegir el "
                 "segmento o como contexto.")
    st.caption(f"Catálogo de variables (versión {cat.version}, archivo datos/catalogo.yaml). De aquí salen el formulario del escenario, "
               "el diccionario del prompt y las validaciones.")
    filas = []
    for v in cat:
        etiquetas, ref = v.categorias_referencia()
        filas.append({
            "Variable": v.etiqueta,
            "Tipo": v.tipo_legible,
            "Valores o rango": v.describir_valores(),
            "¿Palanca?": "Sí" if v.palanca else "No",
            "Uso": v.uso,
            "Distribución de referencia": "; ".join(f"{e}: {ui.pct(p, 0)}" for e, p in zip(etiquetas, ref)),
            "Fuente de la referencia": v.fuente_referencia,
            "Factor (MEN)": v.factor_men,
            "Categoría en la Tabla 12": v.categoria_tabla12,
            "Pregunta": v.pregunta,
            "Nota": v.nota,
        })
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch", height=35 * (len(filas) + 1) + 3,
                 column_config={"Pregunta": st.column_config.TextColumn(width="large"),
                                "Distribución de referencia": st.column_config.TextColumn(width="large"),
                                "Fuente de la referencia": st.column_config.TextColumn(width="large")})
    st.caption("Fuente de las variables: Rosero y Velasco (2026), Tabla 12 y formulario. Se usan los campos, nunca las "
               "respuestas individuales. Factores del MEN: individuales, académicos, institucionales y socioeconómicos.")

    total_tabla12 = len(cat.variables) + len(cat.no_incluidas)
    st.markdown(f"**¿Por qué estas {len(cat.variables)} variables y no otras?**")
    st.caption(f"La Tabla 12 de Rosero y Velasco (2026) describe {total_tabla12} variables. Se eligieron estas "
               f"{len(cat.variables)} con estos criterios:")
    st.markdown("\n".join(f"- {c}" for c in cat.criterios))
    if cat.no_incluidas:
        with st.expander(f"Las otras {len(cat.no_incluidas)} variables de la Tabla 12 y por qué no entraron",
                         icon=":material/playlist_remove:"):
            st.dataframe(pd.DataFrame(cat.no_incluidas).rename(
                columns={"variable": "Variable", "categoria": "Categoría en la Tabla 12", "motivo": "Por qué no entró"}),
                hide_index=True, width="stretch",
                column_config={"Por qué no entró": st.column_config.TextColumn(width="large")})
            st.caption("Las marcadas como candidatas se pueden agregar en datos/catalogo.yaml si el coordinador las "
                       "necesita para sus políticas.")

with t_reglas:
    ui.proposito("ver las hipótesis con que se generan los estudiantes: cómo se relacionan las variables y qué aumenta o "
                 "reduce la probabilidad de desertar. Son lo primero que se revisa con el coordinador (PT 1.2).")
    st.caption(f"Reglas de negocio (versión {r.reglas.version}, archivo datos/reglas.yaml). Son hipótesis: «no tiene que ser real» "
               "(Néstor, reunión 5).")
    st.markdown("**Cómo se generan las variables** (lo que el prompt describe como relaciones)")
    st.dataframe(pd.DataFrame([{
        "Id": x.id, "Relación": x.descripcion, "Fuerza": x.fuerza, "Fuente": x.fuente,
        "Variable generada": cat[x.destino].etiqueta, "Depende de": cat[x.origen].etiqueta,
        "Efecto (escala latente)": x.describir_efecto()} for x in r.reglas.relaciones]), hide_index=True, width="stretch",
        height=35 * (len(r.reglas.relaciones) + 1) + 3)
    st.markdown(f"**Hipótesis sobre la deserción** (tasa de desertores supuesta: {ui.pct(r.reglas.tasa_objetivo, 0)}, "
                "a ajustar con SPADIES)")
    st.dataframe(pd.DataFrame([{
        "Id": x.id, "Hipótesis": x.descripcion, "Fuerza": x.fuerza, "Fuente": x.fuente,
        "Variable": cat[x.origen].etiqueta, "Efecto (log-odds)": x.describir_efecto()} for x in r.reglas.desercion]),
        hide_index=True, width="stretch", height=35 * (len(r.reglas.desercion) + 1) + 3)
    st.caption("Francisco construyó su «riesgo» con una regla (3 de 6 condiciones), no con desertores reales. Aquí la "
               "marca de desertor también sale de supuestos, y por eso se declara.")

with t_modelo:
    ui.proposito("saber qué tan confiable es el modelo que estima el riesgo de cada estudiante. Si ordena mal a los "
                 "estudiantes o sus probabilidades no están calibradas, los escenarios no sirven.")
    st.caption(f"Bosque aleatorio entrenado con {ui.num(m['n_entrenamiento'])} estudiantes sintéticos y evaluado con "
               f"otros {ui.num(m['n_prueba'])} de la misma población de entrenamiento, que es distinta de la línea base. "
               f"Versión {modelo.version}.")
    if m["auc"] < r.params["modelo"]["auc_minimo"]:
        st.warning("El modelo es débil: use los resultados solo para explorar.", icon=":material/warning:")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("AUC", ui.num(m["auc"], 3), border=True, help="Qué tan bien ordena a los estudiantes por riesgo (0,5 = azar).")
    k2.metric("F1", ui.num(m["f1"], 3), border=True, help=f"Con el umbral de {ui.num(100 * m['umbral'])} %.")
    k3.metric("Recall", ui.num(m["recall"], 3), border=True,
              help="Proporción de desertores que el modelo marca en riesgo alto, con ese umbral.")
    k4.metric("Precisión", ui.num(m["precision"], 3), border=True)
    k5.metric("Brier", ui.num(m["brier"], 3), border=True,
              help=f"Error de las probabilidades (menos es mejor). Sin modelo, con la tasa media: {ui.num(m['brier_referencia'], 3)}.")
    st.caption("En el tablero se comparan desertores esperados (la suma de las probabilidades), así que importa más que "
               "las probabilidades estén bien calibradas que el umbral.")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Calibración**")
        cal = pd.DataFrame(m["calibracion"])
        st.caption("Cada punto es un grupo de estudiantes de prueba: si cae sobre la diagonal, el riesgo estimado "
                   "coincide con la proporción de desertores.")
        g.mostrar(g.calibracion(cal), pd.DataFrame({"Riesgo estimado (%)": (100 * cal["predicho"]).round(1),
                                                     "Desertores observados (%)": (100 * cal["observado"]).round(1)}))
    with c2:
        st.markdown("**Qué variables usa el modelo**")
        imp = pd.DataFrame({"Variable": [cat[k].etiqueta for k in m["importancia"]],
                            "Importancia": [max(0.0, round(1000 * v, 1)) for v in m["importancia"].values()]})
        imp = imp.sort_values("Importancia", ascending=False)
        st.caption("Cuánto empeora el AUC si se desordena cada variable (en milésimas). Cerca de cero: el modelo casi no "
                   "la usa (los valores negativos, que son ruido, se muestran como 0).")
        g.mostrar(g.barras(imp, "Variable", "Importancia", "Pérdida de AUC (milésimas)", ",.1f",
                           orden=imp["Variable"].tolist()), imp)

with t_prompt:
    ui.proposito("ver exactamente qué se le pediría al modelo de lenguaje para generar la población. Solo lleva "
                 "porcentajes y reglas, ninguna fila de estudiantes: así se cuida la privacidad.")
    muestra = estado.muestra_para_prompt(r.generador.version)
    texto = r.plantilla.linea_base(muestra, r.params["llm_referencia"]["estudiantes_por_llamada"])
    st.caption(f"Versión {r.plantilla.version} · ≈ {ui.num(estimar_tokens(texto))} tokens por llamada. Es lo que se "
               "enviaría al LLM para generar la línea base y la población de entrenamiento. Las proporciones por "
               "desertores y no desertores salen de los supuestos, no de datos reales.")
    st.code(texto, language="markdown", wrap_lines=True)

with t_limites:
    ui.proposito("tener presente lo que la herramienta no hace antes de interpretar un resultado.")
    st.markdown(
        "- **Los estudiantes no existen.** La población es sintética y sigue los supuestos de esta pantalla.\n"
        "- **El efecto depende de los supuestos.** El modelo aprende las relaciones que el generador supone, así que un "
        "escenario muestra qué pasaría *si* los supuestos fueran ciertos. No es una predicción de lo que hará una política "
        "real ni una medida de su impacto.\n"
        "- **El generador es simulado.** En el prototipo no se llama al LLM: los costos y tiempos son estimaciones con lo "
        "medido en la prueba de generación. Con el LLM, las metas no se cumplen exacto y el efecto puede inflarse si el LLM "
        "exagera las relaciones; para eso están el modo de ajuste directo, las réplicas y el diagnóstico.\n"
        "- **Los criterios de leve o importante son provisionales.** Los fija el coordinador.\n"
        "- **Solo para Ingeniería de Sistemas.** No se pretende generalizar a otros programas.\n"
        "- **Datos que nunca entran:** datos personales reales y respuestas individuales de la encuesta de Francisco. "
        "Al prompt solo llegan porcentajes agregados y reglas."
    )
