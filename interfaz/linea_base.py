"""Pantalla 1: la línea base (sección 7.2, paso 1)."""
import numpy as np
import pandas as pd
import streamlit as st

from interfaz import componentes as ui
from interfaz import estado
from interfaz import graficos as g

r = estado.recursos()
cat = r.catalogo
pob = estado.linea_base()
modelo = estado.modelo_actual()
riesgo = estado.riesgo_base_actual()
umbral = r.params["modelo"]["umbral_riesgo"]
pp = r.params["poblacion"]
df = pob.datos

ui.encabezado(
    "Línea base",
    "La población del programa tal como está hoy, sin ninguna política nueva. Todo escenario se compara con ella.",
)

ui.explicacion(
    "¿Qué es la línea base, cómo se genera y con qué?",
    f"""
**Qué es.** Una población de {ui.num(pob.n)} estudiantes **sintéticos** (no existen) que representa al programa de
Ingeniería de Sistemas *antes* de aplicar una política. Es el punto de comparación: el efecto estimado de una política
es la diferencia entre su escenario y esta línea base.

**Cómo se genera**, en cuatro pasos:

1. **Variables.** Se parte del catálogo: {len(cat.variables)} variables tomadas de la caracterización de Rosero y
   Velasco (2026), cada una con su distribución de referencia (por ejemplo, el 78 % con promedio entre 3,0 y 5,0).
   Por qué estas y no otras: pestaña *Variables* de **Supuestos**.
2. **Relaciones.** Las reglas de negocio dicen cómo se relacionan las variables (por ejemplo, quien trabaja a tiempo
   completo tiende a preocuparse más por el dinero) y cuánto sube o baja cada una la probabilidad de desertar.
3. **Estudiantes.** El generador crea los estudiantes con esas metas y relaciones, y les pone la marca de desertor
   según las reglas, con una tasa supuesta del {ui.pct(r.reglas.tasa_objetivo, 0)}. En el proyecto, este paso lo hará
   el modelo de lenguaje (LLM) con el prompt; en el prototipo lo hace un **generador simulado**, que sigue los mismos
   supuestos y no gasta nada.
4. **Riesgo.** Un modelo predictivo (un bosque aleatorio), entrenado con *otra* población sintética de
   {ui.num(pp['n_entrenamiento'])} estudiantes, estima la probabilidad de desertar de cada estudiante de la línea base.
   Se entrena con otra población para que no "recuerde" a estos estudiantes.

**Con qué.** Solo con supuestos: el catálogo (`datos/catalogo.yaml`), las reglas (`datos/reglas.yaml`) y el tamaño y la
semilla (`datos/parametros.yaml`). No usa datos de estudiantes reales ni respuestas individuales de la encuesta.

**Cuándo cambia.** Se genera una vez y queda guardada, para que todos los escenarios se comparen contra la misma
población. Se vuelve a generar desde la barra lateral, por ejemplo cuando cambian el catálogo o las reglas. Con la
misma semilla sale la misma población.
""",
    abierta=True,
)

st.subheader("Los números de referencia")
ui.proposito("son los valores contra los que se compara cada escenario. «Desertores esperados» suma el riesgo de "
             "todos los estudiantes: 100 estudiantes con un riesgo del 30 % dan 30 desertores esperados.")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Estudiantes sintéticos", ui.num(pob.n), border=True,
          help="Estudiantes que no existen, generados con el perfil supuesto del programa.")
c2.metric("Desertores esperados", ui.num(riesgo.sum()), border=True,
          help="La suma del riesgo estimado de cada estudiante: lo que se compara en cada escenario.")
c3.metric("Riesgo medio", ui.pct(riesgo.mean()), border=True,
          help="Probabilidad media de desertar que estima el modelo: la proporción estimada de estudiantes en riesgo.")
c4.metric(f"En riesgo alto (≥ {ui.num(100 * umbral)} %)", ui.pct((riesgo >= umbral).mean()), border=True,
          help="Proporción de estudiantes con un riesgo estimado igual o mayor que el umbral.")
st.caption(f"Generada el {ui.fecha(pob.creada)} · semilla {pob.semilla} · {pob.origen} · versión {pob.version}")

if modelo.metricas["auc"] < r.params["modelo"]["auc_minimo"]:
    st.warning("El modelo es débil (AUC menor que "
               f"{ui.num(r.params['modelo']['auc_minimo'], 2)}): use los resultados solo para explorar.",
               icon=":material/warning:")

izq, der = st.columns(2, gap="large")

with izq:
    st.subheader("Riesgo por grupo")
    ui.proposito("ver en qué grupos se concentra el riesgo, para decidir a quién dirigir una política (el segmento de "
                 "un escenario).")
    ui.inicial("lb_grupo", "semestre")
    var = st.selectbox("Ver por", cat.nombres, format_func=lambda n: cat[n].etiqueta, key="lb_grupo")
    v = cat[var]
    grupos = pd.Series(v.agrupar(df[var]))
    filas = []
    for etiqueta in v.categorias_referencia()[0]:
        m = (grupos == etiqueta).to_numpy()
        if m.sum() == 0:
            continue
        filas.append({"Grupo": str(etiqueta), "Estudiantes": int(m.sum()),
                      "Riesgo medio (%)": round(100 * riesgo[m].mean(), 1),
                      "En riesgo alto (%)": round(100 * (riesgo[m] >= umbral).mean(), 1),
                      "Desertores esperados": round(riesgo[m].sum(), 1)})
    tabla = pd.DataFrame(filas)
    st.caption(f"Riesgo medio estimado en cada grupo de «{v.etiqueta}».")
    g.mostrar(
        g.barras(tabla, "Grupo", "Riesgo medio (%)", "Riesgo medio estimado (%)", ",.1f", orden=tabla["Grupo"].tolist(),
                 formato_eje=",.0f"),
        tabla,
    )

with der:
    st.subheader("Cómo se reparte cada variable")
    ui.proposito("comprobar que la población generada se parece a lo que se supuso del programa. Si la barra se aleja "
                 "de su marca, la población no representa bien ese supuesto.")
    ui.inicial("lb_variable", "promedio")
    var2 = st.selectbox("Variable", cat.nombres, format_func=lambda n: cat[n].etiqueta, key="lb_variable")
    v2 = cat[var2]
    etiquetas, referencia = v2.categorias_referencia()
    observada = v2.distribucion(df[var2])
    tabla2 = pd.DataFrame({"Categoría": [str(e) for e in etiquetas],
                           "Población generada (%)": np.round(100 * observada, 1),
                           "Referencia del catálogo (%)": np.round(100 * referencia, 1)})
    st.caption("Barra: lo que tiene la población generada. Marca: la referencia del catálogo.")
    g.mostrar(
        g.barras_con_marca(tabla2, "Categoría", "Población generada (%)", "Referencia del catálogo (%)",
                           "Población generada", "Referencia del catálogo", "Estudiantes (%)", ",.1f",
                           orden=tabla2["Categoría"].tolist(), formato_eje=",.0f"),
        tabla2,
    )
    st.caption(f"**Fuente de la referencia:** {v2.fuente_referencia}")

st.subheader("Distribución del riesgo estimado")
ui.proposito("ver si el riesgo se concentra en pocos estudiantes o se reparte entre muchos. La línea marca el umbral "
             "desde el que un estudiante cuenta como en riesgo alto.")
hist, notas = st.columns([3, 2], gap="large")
with hist:
    bordes = np.linspace(0, 1, 21)
    conteo, _ = np.histogram(riesgo, bins=bordes)
    tabla3 = pd.DataFrame({"Riesgo desde (%)": (100 * bordes[:-1]).round(0), "Riesgo hasta (%)": (100 * bordes[1:]).round(0),
                           "Estudiantes": conteo})
    g.mostrar(g.histograma(pd.Series(riesgo), umbral), tabla3[tabla3["Estudiantes"] > 0])
with notas:
    altos = int((riesgo >= umbral).sum())
    with st.container(border=True):
        st.markdown("**Cómo leerlo**")
        st.markdown(
            "- Cada barra agrupa a los estudiantes con un riesgo parecido, de 5 en 5 puntos.\n"
            f"- Por debajo del umbral hay {ui.num(len(riesgo) - altos)} estudiantes; desde el umbral, {ui.num(altos)} "
            f"({ui.pct(altos / len(riesgo))}), los que cuentan como en riesgo alto.\n"
            "- El riesgo es una estimación del modelo con datos sintéticos: sirve para comparar escenarios, no para "
            "señalar a una persona."
        )
        st.page_link("interfaz/supuestos.py", label="Ver todos los supuestos", icon=":material/arrow_forward:")
