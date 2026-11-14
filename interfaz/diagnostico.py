"""Pantalla 5: el diagnóstico (sección 7.9 del Plan; validación de la sección 2.4 del anteproyecto).

Cuatro revisiones de que la herramienta es coherente con sus propios supuestos, antes de confiar en un escenario:
1. la población generada se parece a lo supuesto (metas de entrada);
2. el modelo reacciona a cada palanca;
3. sin cambios no hay efecto, y con más cambio hay más efecto (prueba nula y cambios grandes);
4. cuánto cambia un escenario solo por azar (variabilidad entre réplicas).
"""
import numpy as np
import pandas as pd
import streamlit as st

from datos import repositorio as repo
from dominio import Escenario
from escenarios.aplicar import ejecutar
from escenarios.comparacion import clasificar
from escenarios.politicas_ejemplo import PERSONALIZADA, POLITICAS
from generador.validacion import filas_repetidas, metas_de_entrada
from interfaz import componentes as ui
from interfaz import estado
from interfaz import graficos as g

r = estado.recursos()
cat = r.catalogo
params = r.params
pob = estado.linea_base()
base = pob.datos
modelo = estado.modelo_actual()
riesgo = estado.riesgo_base_actual()
ss = st.session_state
MODOS = {"regeneracion": "Regeneración", "ajuste": "Ajuste directo"}


# ------------------------------------------------------------------ cálculos de las cuatro revisiones
# 1. Metas de entrada
metas = metas_de_entrada(base, cat)
ref_jsd = params["diagnostico"]["jsd_referencia"]
cumplen = int((metas["jsd"] < ref_jsd).sum())
repetidas = filas_repetidas(base, cat.nombres)
bien_1 = cumplen == len(metas) and repetidas == 0

# 2. Respuesta del modelo a cada palanca
sens = pd.DataFrame(estado.sensibilidad_palancas(pob.version, modelo.version))
minimo = params["diagnostico"]["respuesta_minima_pp"]
avisos_2 = []
for _, f in sens.iterrows():
    cifras = f"{ui.num(f['modelo_pp'], 2)} puntos según el modelo, frente a {ui.num(f['reglas_pp'], 2)} según las reglas"
    if abs(f["modelo_pp"]) < minimo:
        avisos_2.append((f["etiqueta"], f"el modelo casi no reacciona a esta variable ({cifras}). Un escenario con esta "
                                        "palanca mostraría un efecto cercano a cero por culpa del modelo, no porque la "
                                        "política no sirva."))
    elif abs(f["reglas_pp"]) > 0 and abs(f["modelo_pp"]) < 0.5 * abs(f["reglas_pp"]):
        avisos_2.append((f["etiqueta"], f"el modelo reacciona a esta variable mucho menos de lo que dicen las reglas "
                                        f"({cifras}). Los escenarios con esta palanca subestimarán su efecto."))

# 3. Prueba nula y cambios grandes (se corre con el botón; el resultado queda en la sesión)
dosis = params["diagnostico"]["dosis"]
resultado_3 = ss.get("diag_resultado")
evaluacion_3 = None
if resultado_3:
    tabla_3 = pd.DataFrame(resultado_3["filas"])
    nula = tabla_3[tabla_3["dosis"] == 0].iloc[0]
    resto = tabla_3[tabla_3["dosis"] > 0].reset_index(drop=True)
    signo = np.sign(tabla_3.loc[tabla_3["dosis"] == 1, "delta"].iloc[0]) if (tabla_3["dosis"] == 1).any() else -1
    piso = params["clasificacion"]["piso_ruido_relativo"] * float(nula["base"])
    tolerancia = [2 * max(a_, b_, piso / 2) for a_, b_ in zip(resto["sd"][:-1], resto["sd"][1:])]
    monotona = all(signo * (resto["delta"][i + 1] - resto["delta"][i]) >= -tolerancia[i] for i in range(len(resto) - 1))
    mismo_sentido = all(signo * f.delta >= -2 * max(f.sd, piso / 2) for f in resto.itertuples())
    evaluacion_3 = {"nula_en_ruido": nula["nivel"] == "ruido", "creciente": monotona and mismo_sentido}

# 4. Variabilidad entre réplicas de los escenarios ya ejecutados con esta línea base
ejecutados = [x for x in repo.listar_resultados() if x["ejecucion"]["linea_base"] == pob.version]
filas_4 = []
for x in ejecutados:
    e = x["ejecucion"]["escenario"]
    cl = clasificar(x["base"]["desertores_poblacion"], [y["desertores_poblacion"] for y in x["replicas"]], params)
    filas_4.append({"Escenario": e["nombre"], "Modo": MODOS[e["modo"]].lower(), "Réplicas": len(x["replicas"]),
                    "Cambio medio": round(cl["delta"], 2), "Desviación típica": round(cl["sd"], 2),
                    "Rango": f"{ui.con_signo(cl['min'] - cl['base'], 1)} a {ui.con_signo(cl['max'] - cl['base'], 1)}",
                    "Efecto": cl["etiqueta"]})


# ------------------------------------------------------------------ pantalla
ui.encabezado("Diagnóstico", "Revisiones de que la herramienta se comporta como debe, antes de confiar en un resultado.")
ui.proposito("comprobar que la herramienta es coherente con sus propios supuestos. Como no hay datos reales para medir "
             "el efecto de una política, el anteproyecto (sección 2.4) propone revisar estas cuatro cosas.")

ui.explicacion(
    "¿Cómo se usa esta pantalla?",
    """
Piénselo como la revisión de una balanza antes de pesar: si marca 2 kilos sin nada encima, no sirve. Aquí se revisa
lo mismo con la herramienta, en cuatro preguntas:

1. **¿La población generada se parece a lo que se supuso?** Si no, todo lo demás parte de una población equivocada.
2. **¿El modelo reacciona a cada palanca?** Si el modelo no usa una variable, una política sobre ella mostrará un efecto
   casi nulo aunque las reglas digan que sirve.
3. **¿Sin cambios no hay efecto, y con más cambio hay más efecto?** Si regenerar sin cambiar nada mueve el resultado, o si
   duplicar el cambio da menos efecto, algo anda mal en el generador o en las reglas.
4. **¿Cuánto cambia un escenario solo por azar?** Si los resultados varían mucho entre réplicas, hacen falta más réplicas
   para distinguir el efecto del azar.

Si las cuatro salen bien, los resultados son coherentes con los supuestos. **No dicen si los supuestos son ciertos**: eso
se revisa con el coordinador, en la pantalla Supuestos.

Con el generador simulado casi todo sale bien por construcción. Esta pantalla importa de verdad cuando se conecte el
modelo de lenguaje, que puede no seguir el prompt al pie de la letra.
""",
    abierta=True,
)


def _estado(columna, titulo: str, estado_: str, detalle: str) -> None:
    colores = {"Bien": ("green", ":material/check_circle:"), "Revisar": ("orange", ":material/warning:"),
               "Sin correr": ("gray", ":material/schedule:"), "Informativo": ("gray", ":material/info:")}
    color, icono = colores[estado_]
    with columna.container(border=True):
        st.markdown(f"**{titulo}**")
        st.badge(estado_, icon=icono, color=color)
        st.caption(detalle)


st.subheader("Resumen")
s1, s2, s3, s4 = st.columns(4)
_estado(s1, "1 · Se parece a lo supuesto", "Bien" if bien_1 else "Revisar",
        f"{cumplen} de {len(metas)} variables bajo el criterio; {ui.num(repetidas)} estudiantes repetidos.")
_estado(s2, "2 · El modelo ve las palancas", "Bien" if not avisos_2 else "Revisar",
        f"{len(sens) - len(avisos_2)} de {len(sens)} palancas sin problema" +
        (f"; revisar: {', '.join(a for a, _ in avisos_2)}." if avisos_2 else "."))
if evaluacion_3 is None:
    _estado(s3, "3 · Sin cambios, sin efecto", "Sin correr", "Use el botón de la sección 3.")
else:
    bien_3 = evaluacion_3["nula_en_ruido"] and evaluacion_3["creciente"]
    _estado(s3, "3 · Sin cambios, sin efecto", "Bien" if bien_3 else "Revisar",
            f"Sin cambios: {'dentro' if evaluacion_3['nula_en_ruido'] else 'fuera'} del ruido. Efecto creciente: "
            f"{'sí' if evaluacion_3['creciente'] else 'no'}.")
if filas_4:
    _estado(s4, "4 · Azar entre réplicas", "Informativo",
            f"{len(filas_4)} escenario{'s' if len(filas_4) != 1 else ''}; la mayor desviación es de "
            f"{ui.num(max(f['Desviación típica'] for f in filas_4), 1)} desertores.")
else:
    _estado(s4, "4 · Azar entre réplicas", "Sin correr", "Todavía no hay escenarios con esta línea base.")

# 1 ---------------------------------------------------------------------------------------------
st.subheader("1 · ¿La población generada se parece a lo que se supuso?")
ui.proposito("comprobar que el generador siguió las metas del catálogo. Si la población no se parece a lo supuesto, "
             "todo lo demás parte de una población equivocada.")
vista = pd.DataFrame({"Variable": metas["etiqueta"], "JSD": metas["jsd"].round(4),
                      "Mayor diferencia (puntos %)": metas["mayor_diferencia_pp"].round(1)})
c1, c2 = st.columns([3, 2], gap="large")
with c1:
    st.caption("**Cómo se lee:** para cada variable, la divergencia de Jensen-Shannon (JSD) mide cuánto se aleja lo "
               "generado de la referencia del catálogo: 0 es idéntico y 1, nada en común. Por debajo de "
               f"{ui.num(ref_jsd, 1)} (la línea, el criterio que usó Laura en su trabajo) se considera que se parecen.")
    maximo = max(ref_jsd * 1.25, float(metas["jsd"].max()) * 1.1)
    g.mostrar(g.barras(vista, "Variable", "JSD", "Divergencia de Jensen-Shannon", ",.3f",
                       orden=vista["Variable"].tolist(), dominio=[0, maximo], referencia=ref_jsd,
                       texto_referencia=f"Criterio: {ui.num(ref_jsd, 1)}", formato_eje=",.2f"), vista)
with c2:
    st.metric("Variables bajo el criterio", f"{cumplen} de {len(metas)}", border=True)
    st.metric("Estudiantes repetidos", ui.num(repetidas), border=True,
              help="Copias exactas de otro estudiante en todas las variables. Un LLM tiende a repetirse.")
    tasa = (base["desertor"] == "Sí").mean()
    st.metric("Marca de desertor", ui.pct(tasa), border=True,
              help=f"Proporción de desertores en la línea base. La meta de las reglas es {ui.pct(r.reglas.tasa_objetivo, 0)}; "
                   "con 1000 estudiantes es normal que se aleje 2 o 3 puntos.")
st.caption("**Si sale mal:** el generador (en el proyecto, el modelo de lenguaje) no siguió el prompt. Hay que ajustar el "
           "prompt o el catálogo antes de simular políticas.")

# 2 ---------------------------------------------------------------------------------------------
st.subheader("2 · ¿El modelo reacciona a cada palanca?")
ui.proposito("saber, antes de usar una palanca en un escenario, si el modelo la tiene en cuenta.")
st.caption("**Cómo se lee:** cada palanca se lleva a su valor más favorable en toda la población y se mide cuánto baja el "
           "riesgo medio. Barra: lo que estima el modelo. Marca: lo que dicen las reglas con que se generaron los datos. "
           "Si la barra es mucho más corta que su marca, el modelo subestima esa palanca.")
vista2 = pd.DataFrame({"Palanca": sens["etiqueta"], "Cambio aplicado": sens["cambio"],
                       "Según el modelo (puntos %)": sens["modelo_pp"].round(2),
                       "Según las reglas (puntos %)": sens["reglas_pp"].round(2),
                       "Estudiantes que cambian": sens["estudiantes"]})
g.mostrar(g.barras_con_marca(vista2, "Palanca", "Según el modelo (puntos %)", "Según las reglas (puntos %)",
                             "Según el modelo", "Según las reglas", "Cambio en el riesgo medio (puntos %)", ",.1f",
                             orden=vista2["Palanca"].tolist(), serie=2), vista2)
for etiqueta, texto in avisos_2:
    st.warning(f"**{etiqueta}:** {texto}", icon=":material/warning:")
st.caption("**Si sale mal:** entrenar el modelo con más estudiantes, revisar la regla de esa variable o probar otro "
           "modelo (PT 2).")

# 3 ---------------------------------------------------------------------------------------------
st.subheader("3 · ¿Sin cambios no hay efecto, y con más cambio hay más efecto?")
ui.proposito("comprobar que el efecto de un escenario viene de la política y no del generador. Es la prueba que promete "
             "el anteproyecto: un escenario sin cambios debe parecerse a la línea base, y un cambio mayor no debe dar un "
             "efecto menor ni contrario.")
st.caption("**Cómo se lee:** se ejecuta una política con distintas intensidades: 0 es regenerar sin cambiar nada, 1 es el "
           "cambio definido y 2, el doble. Con intensidad 0 el resultado debe quedar cerca de cero (dentro del ruido). "
           "Al subir la intensidad, la línea debe alejarse de cero siempre en la misma dirección. La banda es el rango "
           "entre réplicas.")
opciones = [k for k in POLITICAS if k != PERSONALIZADA]
ui.inicial("diag_politica", opciones[0])
ui.inicial("diag_modo", "regeneracion")
ui.inicial("diag_replicas", 5)
a, b, c = st.columns([3, 2, 2])
a.selectbox("Política de prueba", opciones, key="diag_politica")
b.radio("Modo", ["regeneracion", "ajuste"], key="diag_modo", horizontal=True, format_func=lambda m: MODOS[m])
c.slider("Réplicas por intensidad", 2, 10, key="diag_replicas")
if st.button("Correr la prueba", icon=":material/play_arrow:",
             help=f"Ejecuta la política {len(dosis)} veces (intensidades {', '.join(ui.num(d, 2) for d in dosis)}). "
                  "En un servidor gratuito puede tardar cerca de un minuto."):
    pol = POLITICAS[ss["diag_politica"]]
    filas = []
    barra = st.progress(0.0, text="Probando…")
    for k, d in enumerate(dosis):
        esc = Escenario("diagnóstico", ss["diag_politica"], "", pol["segmento"], pol["palancas"], ss["diag_modo"],
                        int(ss["diag_replicas"]), 11)
        resumen, _, _ = ejecutar(esc, base, riesgo, r.generador, modelo, cat, params, dosis=d)
        cl = resumen["clasificacion"]["poblacion"]
        filas.append({"dosis": d, "delta": cl["delta"], "delta_min": cl["min"] - cl["base"],
                      "delta_max": cl["max"] - cl["base"], "sd": cl["sd"], "etiqueta": cl["etiqueta"],
                      "nivel": cl["nivel"], "base": cl["base"]})
        barra.progress((k + 1) / len(dosis), text=f"Intensidad {ui.num(d, 2)}")
    barra.empty()
    ss["diag_resultado"] = {"politica": ss["diag_politica"], "modo": ss["diag_modo"], "filas": filas}
    st.rerun()

if resultado_3:
    k1, k2, k3 = st.columns(3)
    k1.metric("Cambio en desertores sin cambios", ui.con_signo(nula["delta"], 1), border=True,
              help=f"Intensidad 0. Rango entre réplicas: {ui.con_signo(nula['delta_min'], 1)} a "
                   f"{ui.con_signo(nula['delta_max'], 1)}.")
    k2.metric("¿Dentro del ruido?", "Sí" if evaluacion_3["nula_en_ruido"] else "No", border=True,
              help="Si es «Sí», regenerar sin cambios no produce un efecto que se distinga del azar.")
    k3.metric("¿El efecto crece con la intensidad?", "Sí" if evaluacion_3["creciente"] else "Revisar", border=True,
              help="Un cambio mayor no da un efecto menor ni de sentido contrario (con la tolerancia del ruido).")
    st.caption(f"Política: {resultado_3['politica']} · modo {MODOS[resultado_3['modo']].lower()}.")
    vista3 = pd.DataFrame({"Intensidad": tabla_3["dosis"], "Cambio medio en desertores": tabla_3["delta"].round(2),
                           "Mínimo": tabla_3["delta_min"].round(2), "Máximo": tabla_3["delta_max"].round(2),
                           "Desviación típica": tabla_3["sd"].round(2), "Efecto": tabla_3["etiqueta"]})
    g.mostrar(g.dosis(tabla_3), vista3)
st.caption("**Si sale mal:** si la intensidad 0 da un efecto, el generador cambia cosas que la política no pidió; si la "
           "línea se devuelve, alguna regla va en sentido contrario. Hay que revisar el prompt o las reglas.")

# 4 ---------------------------------------------------------------------------------------------
st.subheader("4 · ¿Cuánto cambia un escenario solo por azar?")
ui.proposito("saber si las réplicas alcanzan: si el resultado varía mucho de una réplica a otra, el efecto se puede "
             "confundir con el azar.")
st.caption("**Cómo se lee:** para cada escenario ya ejecutado con esta línea base, el cambio medio frente a ella, cuánto "
           "varía entre réplicas (desviación típica) y su rango. En ajuste directo con cobertura del 100 % no hay azar; "
           "en regeneración siempre hay, porque el generador (o el LLM) produce estudiantes distintos cada vez.")
if not filas_4:
    st.info("Todavía no hay escenarios ejecutados con esta línea base.", icon=":material/info:")
else:
    tabla_var = pd.DataFrame(filas_4)
    st.dataframe(tabla_var, hide_index=True, width="stretch", column_config=g.formato_tabla(tabla_var))
st.caption("**Si sale mal:** si la desviación típica se parece al cambio medio, ejecute más réplicas antes de concluir.")
