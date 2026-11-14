"""Pantalla 3: comparar cada escenario con la línea base (sección 7.2, paso 4)."""
import pandas as pd
import streamlit as st

from datos import repositorio as repo
from dominio import Escenario
from escenarios.comparacion import clasificar, por_categoria
from interfaz import componentes as ui
from interfaz import estado
from interfaz import graficos as g

r = estado.recursos()
cat = r.catalogo
params = r.params
pob = estado.linea_base()
base = pob.datos
umbral = params["modelo"]["umbral_riesgo"]
ss = st.session_state

ui.encabezado("Resultados", "Cada escenario frente a la línea base, con la variación entre réplicas.")
ui.proposito("responder dos preguntas sobre cada escenario: ¿cambian los desertores esperados frente a la línea base? "
             "y ¿el cambio es importante o puede ser solo azar (ruido)?")

resultados = repo.listar_resultados()
if not resultados:
    st.info("Todavía no hay escenarios ejecutados.", icon=":material/info:")
    st.page_link("interfaz/escenario.py", label="Crear un escenario", icon=":material/arrow_forward:")
    st.stop()

por_id = {x["ejecucion"]["id"]: x for x in resultados}
ids = list(por_id)
MODOS = {"ajuste": "ajuste directo", "regeneracion": "regeneración"}


def nombre_corto(i: str) -> str:
    e = por_id[i]["ejecucion"]["escenario"]
    return f"{e['nombre']} ({MODOS[e['modo']]})"


def etiqueta(i: str) -> str:
    return f"{nombre_corto(i)} · {ui.fecha(por_id[i]['ejecucion']['fecha'])}"


if ss.get("res_escenario") not in ids:
    ss["res_escenario"] = ids[0]
st.selectbox("Escenario", ids, format_func=etiqueta, key="res_escenario")
res = por_id[ss["res_escenario"]]
ej = res["ejecucion"]
esc = Escenario.de_dict(ej["escenario"])
misma_base = ej["linea_base"] == pob.version

c_pob = clasificar(res["base"]["desertores_poblacion"], [x["desertores_poblacion"] for x in res["replicas"]], params)
c_seg = clasificar(res["base"]["desertores_segmento"], [x["desertores_segmento"] for x in res["replicas"]], params)
en_riesgo = sum(x["en_riesgo_poblacion"] for x in res["replicas"]) / len(res["replicas"])
cambiados = sum(x["cambiados"] for x in res["replicas"]) / len(res["replicas"])

st.caption(
    f"**Política:** {esc.politica} · **Segmento:** {esc.segmento.describir(cat)} · "
    f"**Cambios:** {'; '.join(p.describir(cat[p.variable]) for p in esc.palancas)} · "
    f"**Modo:** {MODOS[esc.modo]} · **Réplicas:** {esc.replicas}"
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Desertores esperados", ui.num(c_pob["media"], 1),
          delta=f"{ui.con_signo(c_pob['delta'], 1)} ({ui.con_signo(100 * c_pob['delta_relativo'], 1, ' %')})",
          delta_color="inverse", border=True,
          help=f"Línea base: {ui.num(c_pob['base'], 1)}. Media de {esc.replicas} réplicas; "
               f"rango de {ui.num(c_pob['min'], 1)} a {ui.num(c_pob['max'], 1)}. Es la suma del riesgo de todos los "
               f"estudiantes: un riesgo medio de {ui.pct(c_pob['media'] / res['base']['n_poblacion'])}.")
m2.metric(f"En riesgo alto (≥ {ui.num(100 * umbral)} %)", ui.pct(en_riesgo),
          delta=ui.con_signo(100 * (en_riesgo - res["base"]["en_riesgo_poblacion"]), 1, " pp"), delta_color="inverse",
          border=True, help=f"Línea base: {ui.pct(res['base']['en_riesgo_poblacion'])}.")
m3.metric("Estudiantes con cambios", ui.num(cambiados), border=True,
          help="Estudiantes con al menos una variable distinta a la línea base, en promedio por réplica.")
with m4.container(border=True):
    st.caption("Efecto en la población")
    ui.insignia(c_pob)
    st.caption(f"Ruido: ± {ui.num(c_pob['ruido'], 1)} desertores")

if esc.segmento.condiciones:
    with st.container(border=True):
        s1, s2 = st.columns([3, 1], vertical_alignment="center")
        s1.markdown(
            f"**En el segmento** ({ui.num(res['base']['n_segmento'])} estudiantes): los desertores esperados pasan de "
            f"**{ui.num(c_seg['base'], 1)}** a **{ui.num(c_seg['media'], 1)}** "
            f"({ui.con_signo(100 * c_seg['delta_relativo'], 1, ' %').replace('-', '−')}).")
        with s2:
            ui.insignia(c_seg, "Segmento: ")

if esc.efecto_esperado is not None:
    st.info(f"Antes de ejecutar, usted anotó que esperaba un cambio de {ui.num(esc.efecto_esperado, 0)} % en los "
            f"desertores esperados. Resultado: {ui.num(100 * c_pob['delta_relativo'], 1)} %.", icon=":material/psychology:")

st.caption("**Ruido** es cuánto cambia el resultado solo por azar de una réplica a otra: un cambio que no lo supera no "
           "se distingue del azar. Criterio provisional del prototipo para decir si es leve o importante: dentro del ruido si el cambio no supera "
           f"{params['clasificacion']['veces_desviacion']} desviaciones típicas entre réplicas (o el "
           f"{ui.num(100 * params['clasificacion']['piso_ruido_relativo'])} % de la línea base); leve si es menor que el "
           f"{ui.num(100 * params['clasificacion']['leve_hasta'])} %; importante desde el "
           f"{ui.num(100 * params['clasificacion']['importante_desde'])} %. Lo debe fijar el coordinador.")

tab_grupo, tab_comprobacion, tab_lado, tab_replicas = st.tabs(
    ["Por grupo", "¿La variable cambió?", "Escenarios lado a lado", "Réplicas"])

with tab_grupo:
    ui.proposito("ver en qué grupos actúa la política: dónde baja más el riesgo y dónde casi no cambia.")
    if not misma_base:
        st.warning("Este escenario se ejecutó con otra línea base. Vuelva a ejecutarlo para verlo por grupo.",
                   icon=":material/sync_problem:")
    else:
        riesgos = repo.cargar_riesgos(ej["id"])
        defecto = esc.segmento.condiciones[0].variable if esc.segmento.condiciones else "semestre"
        ui.inicial("res_grupo", defecto)
        var = st.selectbox("Ver por", cat.nombres, format_func=lambda n: cat[n].etiqueta, key="res_grupo")
        tabla = por_categoria(base, riesgos, var, cat, umbral)
        vista = pd.DataFrame({
            "Grupo": tabla["grupo"],
            "Estudiantes": tabla["estudiantes"],
            "Riesgo medio, línea base (%)": tabla["riesgo_base"].round(1),
            "Riesgo medio, escenario (%)": tabla["riesgo_escenario"].round(1),
            "Desertores esperados, línea base": tabla["desertores_base"].round(1),
            "Desertores esperados, escenario": tabla["desertores_escenario"].round(1),
        })
        st.caption(f"Riesgo medio estimado por grupo de «{cat[var].etiqueta}» (con los valores de la línea base, "
                   "antes de la política).")
        g.mostrar(g.pesas(vista, "Grupo", "Riesgo medio, línea base (%)", "Riesgo medio, escenario (%)",
                          "Riesgo medio estimado (%)", ",.1f", orden=vista["Grupo"].tolist(),
                          formato_eje=",.0f"), vista)

with tab_comprobacion:
    ui.proposito("confirmar que la población del escenario cambió como pedía la política antes de atribuirle el efecto. "
                 "Si el promedio debía subir a 3,7 y quedó en 3,5, el efecto que se ve es el de 3,5.")
    filas = []
    for f in res["comprobacion"]:
        v = cat[f["variable"]]

        def fmt(x, f=f, v=v):
            if f["es_proporcion"]:
                return ui.pct(x, 1)
            return ui.num(x, 2)

        filas.append({
            "Palanca": f["cambio"],
            "Qué se mide": f["medida"],
            "Antes": fmt(f["antes"]),
            "Meta": fmt(f["meta"]),
            "Logrado": fmt(f["logrado"]),
            "Rango en las réplicas": f"{fmt(f['logrado_min'])} a {fmt(f['logrado_max'])}",
            "¿Cumple?": "Sí" if f["cumple"] else "Revisar",
        })
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    if any(not f["cumple"] for f in res["comprobacion"]):
        st.warning("Alguna palanca no llegó a la meta. En regeneración, el LLM (aquí, el simulador) no la cumple "
                   "exacto, y una palanca que depende de otra del mismo paquete también se mueve por esa otra. "
                   "Revise antes de interpretar el efecto.", icon=":material/rule:")
    if res.get("copias_frente_base") is not None:
        st.caption(f"Copias exactas frente a la población base, entre los estudiantes regenerados (réplica 1): "
                   f"{ui.pct(res['copias_frente_base'], 1)}.")

with tab_lado:
    ui.proposito("comparar varias políticas sobre la misma línea base, por ejemplo una medida sola frente a un paquete, "
                 "y ver cuál reduce más los desertores esperados y con cuánta incertidumbre.")
    mismos = [i for i in ids if por_id[i]["ejecucion"]["linea_base"] == ej["linea_base"]]
    if "res_comparar" not in ss or not set(ss["res_comparar"]) <= set(mismos):
        ss["res_comparar"] = mismos[:4] if ss["res_escenario"] in mismos[:4] else [ss["res_escenario"]] + mismos[:3]
    st.multiselect("Escenarios", mismos, format_func=etiqueta, key="res_comparar", max_selections=6,
                   help="Solo los que se ejecutaron con la misma línea base, para que la comparación sea justa.")
    elegidos = ss["res_comparar"]
    if elegidos:
        filas, vistos = [], {}
        for i in elegidos:
            x = por_id[i]
            c = clasificar(x["base"]["desertores_poblacion"], [y["desertores_poblacion"] for y in x["replicas"]], params)
            nombre = nombre_corto(i)
            vistos[nombre] = vistos.get(nombre, 0) + 1
            if vistos[nombre] > 1:
                nombre = f"{nombre} #{vistos[nombre]}"
            filas.append({"nombre": nombre, "media": c["media"], "min": c["min"], "max": c["max"],
                          "delta": c["delta"], "rel": c["delta_relativo"], "efecto": c["etiqueta"],
                          "replicas": len(x["replicas"]), "costo": x["ejecucion"]["costo_estimado_usd"]})
        tabla = pd.DataFrame(filas)
        base_valor = por_id[elegidos[0]]["base"]["desertores_poblacion"]
        st.caption("Desertores esperados en toda la población: punto = media de las réplicas; línea = de la menor a la "
                   "mayor. La línea vertical azul es la línea base.")
        vista = pd.DataFrame({
            "Escenario": tabla["nombre"],
            "Desertores esperados (media)": tabla["media"].round(1),
            "Mínimo": tabla["min"].round(1),
            "Máximo": tabla["max"].round(1),
            "Cambio": tabla["delta"].round(1),
            "Cambio (%)": (100 * tabla["rel"]).round(1),
            "Efecto": tabla["efecto"],
            "Réplicas": tabla["replicas"],
            "Costo estimado con el LLM (US$)": tabla["costo"].round(2),
        })
        g.mostrar(g.rango_escenarios(tabla, base_valor, "Desertores esperados", ",.0f"), vista)

with tab_replicas:
    ui.proposito("ver el resultado de cada repetición del escenario. Si varían mucho entre sí, el efecto es incierto y "
                 "conviene ejecutar más réplicas.")
    filas = [{"Réplica": x["replica"], "Desertores esperados": round(x["desertores_poblacion"], 1),
              "En el segmento": round(x["desertores_segmento"], 1),
              "En riesgo alto (%)": round(100 * x["en_riesgo_poblacion"], 1),
              "Estudiantes que cambiaron": x["cambiados"]} for x in res["replicas"]]
    tabla_rep = pd.DataFrame(filas)
    st.dataframe(tabla_rep, hide_index=True, width="stretch", column_config=g.formato_tabla(tabla_rep))
    st.caption(f"Línea base: {ui.num(res['base']['desertores_poblacion'], 1)} desertores esperados. "
               f"Desviación típica entre réplicas: {ui.num(c_pob['sd'], 2)}.")
    riesgos_csv = repo.cargar_riesgos(ej["id"]).to_csv(index=False).encode("utf-8")
    st.download_button("Descargar el riesgo por estudiante (CSV)", riesgos_csv, file_name=f"riesgos_{ej['id']}.csv",
                       mime="text/csv", icon=":material/download:")
