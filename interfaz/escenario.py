"""Pantalla 2: crear y ejecutar un escenario (sección 7.2, pasos 2 y 3)."""
import datetime as dt
import hashlib
import json
import time

import streamlit as st

from datos import repositorio as repo
from dominio import OPERACIONES, Condicion, Ejecucion, Escenario, ParametroPolitica, Segmento, operaciones_para
from escenarios.aplicar import elegibles, ejecutar, estimar_costo
from escenarios.politicas_ejemplo import PERSONALIZADA, POLITICAS
from generador.plantilla_prompt import estimar_tokens
from interfaz import componentes as ui
from interfaz import estado

r = estado.recursos()
cat = r.catalogo
params = r.params
pob = estado.linea_base()
base = pob.datos
modelo = estado.modelo_actual()
riesgo = estado.riesgo_base_actual()
ss = st.session_state

MAX_CONDICIONES = 3
MAX_PALANCAS = 3
PALANCAS = [v.nombre for v in cat.palancas]
SEGMENTABLES = cat.nombres


# ------------------------------------------------------------------ valores por defecto
def _valor_por_defecto(v, op):
    if op == "multiplicar":
        return 1.10
    if op == "sumar":
        return -1 if v.tipo == "ordinal" else 0.2
    medio = (v.minimo + v.maximo) / 2
    return int(round(medio)) if v.tipo == "ordinal" else round(medio, 1)


def _limites(v, op):
    """(mínimo, máximo, paso) del control del nuevo valor."""
    if op == "multiplicar":
        return 0.5, 2.0, 0.05
    if op == "sumar":
        if v.tipo == "ordinal":
            return -4, 4, 1
        return -2.0, 2.0, 0.1
    if v.tipo == "ordinal":
        return int(v.minimo), int(v.maximo), 1
    return float(v.minimo), float(v.maximo), 0.1


def _entera(v) -> bool:
    return v.tipo == "ordinal" or (v.es_numerica and v.decimales == 0)


def _defaults_condicion(i, var, c=None):
    v = cat[var]
    if v.es_ordenable:
        lo, hi = (c.minimo, c.maximo) if (c and c.minimo is not None) else (v.minimo, v.maximo)
        ss[f"esc_c{i}_rango"] = (int(lo), int(hi)) if _entera(v) else (float(lo), float(hi))
    else:
        ss[f"esc_c{i}_cats"] = list(c.valores) if (c and c.valores) else list(v.valores)


def _defaults_palanca(i, var, p=None):
    v = cat[var]
    op = p.operacion if p else operaciones_para(v)[0]
    ss[f"esc_p{i}_op"] = op
    _defaults_valor(i, var, op, p)
    ss[f"esc_p{i}_cob"] = int(round(100 * (p.cobertura if p else 1.0)))


def _defaults_valor(i, var, op, p=None):
    v = cat[var]
    if op == "cambiar":
        ss[f"esc_p{i}_desde"] = p.desde if p else v.valores[-1]
        ss[f"esc_p{i}_hacia"] = p.hacia if p else v.valores[0]
        return
    valor = p.valor if (p and p.valor is not None) else _valor_por_defecto(v, op)
    entero = v.tipo == "ordinal" and op != "multiplicar"
    ss[f"esc_p{i}_valor"] = int(round(valor)) if entero else float(valor)


def cargar_politica():
    nombre = ss["esc_politica"]
    pol = POLITICAS[nombre]
    ss["esc_nombre"] = "Mi escenario" if nombre == PERSONALIZADA else nombre
    condiciones = pol["segmento"].condiciones
    ss["esc_todos"] = not condiciones
    ss["esc_n_cond"] = max(1, len(condiciones))
    for i in range(MAX_CONDICIONES):
        c = condiciones[i] if i < len(condiciones) else None
        var = c.variable if c else SEGMENTABLES[(i + 2) % len(SEGMENTABLES)]
        ss[f"esc_c{i}_var"] = var
        _defaults_condicion(i, var, c)
    palancas = pol["palancas"]
    ss["esc_n_pal"] = len(palancas)
    usadas = [p.variable for p in palancas]
    libres = [x for x in PALANCAS if x not in usadas]
    for i in range(MAX_PALANCAS):
        p = palancas[i] if i < len(palancas) else None
        var = p.variable if p else (libres.pop(0) if libres else PALANCAS[0])
        ss[f"esc_p{i}_var"] = var
        _defaults_palanca(i, var, p)


if "esc_politica" not in ss:
    ss["esc_politica"] = next(iter(POLITICAS))
    cargar_politica()
ui.inicial("esc_modo", "ajuste")
ui.inicial("esc_replicas", 5)
ui.inicial("esc_semilla", 1)
ui.inicial("esc_esperado_on", False)
ui.inicial("esc_esperado", -10.0)


def _cambio_var_condicion(i):
    _defaults_condicion(i, ss[f"esc_c{i}_var"])


def _cambio_var_palanca(i):
    _defaults_palanca(i, ss[f"esc_p{i}_var"])


def _cambio_operacion(i):
    _defaults_valor(i, ss[f"esc_p{i}_var"], ss[f"esc_p{i}_op"])


# ------------------------------------------------------------------ pantalla
ui.encabezado(
    "Escenario",
    "Defina la política: a quién va, qué variables cambia y cuánto. La herramienta la traduce en "
    "parámetros del prompt y simula solo la parte de la población que cambia.",
)
ui.proposito("traducir una estrategia de permanencia a números (parámetros de política) y simular su efecto sobre la "
             "línea base. Las políticas de la lista son ejemplos para probar la herramienta: las reales las define el "
             "coordinador.")

# 1. Política
with st.container(border=True):
    st.markdown("##### 1 · Política")
    ui.proposito("elegir de qué política parte el escenario. El nombre sirve para encontrarlo después en Resultados.")
    a, b = st.columns([3, 2])
    a.selectbox("Política", list(POLITICAS), key="esc_politica", on_change=cargar_politica,
                help="Las de la lista son ejemplos para probar la herramienta. Las políticas reales las define el coordinador.")
    b.text_input("Nombre del escenario", key="esc_nombre", max_chars=80)
    st.caption(POLITICAS[ss["esc_politica"]]["descripcion"])

# 2. Segmento
with st.container(border=True):
    st.markdown("##### 2 · ¿A quién va?")
    ui.proposito("definir el segmento: los estudiantes a los que llega la política (por ejemplo, semestres 1 a 3). "
                 "El resto de la población queda igual.")
    st.toggle("Toda la población", key="esc_todos")
    condiciones = []
    if not ss["esc_todos"]:
        ui.inicial("esc_n_cond", 1)
        st.columns([1, 3])[0].number_input("Número de condiciones", min_value=1, max_value=MAX_CONDICIONES, step=1,
                                           key="esc_n_cond")
        for i in range(int(ss["esc_n_cond"])):
            c1, c2 = st.columns([2, 3])
            c1.selectbox(f"Variable {i + 1}", SEGMENTABLES, format_func=lambda n: cat[n].etiqueta,
                         key=f"esc_c{i}_var", on_change=_cambio_var_condicion, args=(i,))
            v = cat[ss[f"esc_c{i}_var"]]
            if v.es_ordenable:
                entera = _entera(v)
                paso = 1 if entera else 0.1
                lo, hi = (int(v.minimo), int(v.maximo)) if entera else (float(v.minimo), float(v.maximo))
                c2.slider("Entre", min_value=lo, max_value=hi, step=paso, key=f"esc_c{i}_rango",
                          format="%d" if entera else "%.1f")
                mn, mx = ss[f"esc_c{i}_rango"]
                condiciones.append(Condicion(v.nombre, minimo=float(mn), maximo=float(mx)))
            else:
                c2.multiselect("Incluye", list(v.valores), key=f"esc_c{i}_cats")
                condiciones.append(Condicion(v.nombre, valores=list(ss[f"esc_c{i}_cats"])))
    segmento = Segmento(condiciones)
    seg = segmento.mascara(base)
    n_seg = int(seg.sum())
    st.markdown(f"**Segmento:** {segmento.describir(cat)} → **{ui.num(n_seg)}** estudiantes "
                f"({ui.pct(n_seg / len(base))} de la población).")
    if n_seg == 0:
        st.warning("Ningún estudiante cumple estas condiciones.", icon=":material/person_off:")

# 3. Palancas
with st.container(border=True):
    st.markdown("##### 3 · ¿Qué cambia y cuánto?")
    ui.proposito("decir qué mueve la política. Cada palanca es un parámetro de política: una variable que la política "
                 "puede cambiar (como el promedio), cómo la cambia y a qué parte de los estudiantes llega. Solo se pueden "
                 "mover las variables marcadas como palanca en el catálogo.")
    ui.inicial("esc_n_pal", 1)
    st.columns([1, 3])[0].number_input("Variables que cambia la política", min_value=1, max_value=MAX_PALANCAS,
                                       step=1, key="esc_n_pal")
    palancas = []
    for i in range(int(ss["esc_n_pal"])):
        if ss.get(f"esc_p{i}_var") not in PALANCAS:
            ss[f"esc_p{i}_var"] = PALANCAS[0]
            _defaults_palanca(i, PALANCAS[0])
        v = cat[ss[f"esc_p{i}_var"]]
        ops = operaciones_para(v)
        if ss.get(f"esc_p{i}_op") not in ops:
            ss[f"esc_p{i}_op"] = ops[0]
            _defaults_valor(i, v.nombre, ops[0])
        st.markdown(f"**Palanca {i + 1}**")
        c1, c2, c3, c4 = st.columns([2.2, 2, 2.2, 2])
        c1.selectbox("Variable", PALANCAS, format_func=lambda n: cat[n].etiqueta, key=f"esc_p{i}_var",
                     on_change=_cambio_var_palanca, args=(i,))
        c2.selectbox("Cambio", ops, format_func=lambda o: OPERACIONES[o], key=f"esc_p{i}_op",
                     on_change=_cambio_operacion, args=(i,))
        op = ss[f"esc_p{i}_op"]
        if op == "cambiar":
            d1, d2 = c3.columns(2)
            for k in ("desde", "hacia"):
                if ss.get(f"esc_p{i}_{k}") not in v.valores:
                    ss[f"esc_p{i}_{k}"] = v.valores[-1] if k == "desde" else v.valores[0]
            d1.selectbox("De", list(v.valores), key=f"esc_p{i}_desde")
            d2.selectbox("A", list(v.valores), key=f"esc_p{i}_hacia")
            p = ParametroPolitica(v.nombre, "cambiar", desde=ss[f"esc_p{i}_desde"], hacia=ss[f"esc_p{i}_hacia"],
                                  cobertura=ss[f"esc_p{i}_cob"] / 100)
        else:
            lo, hi, paso = _limites(v, op)
            actual = ss.get(f"esc_p{i}_valor")
            if isinstance(paso, int) and not isinstance(actual, int):
                ss[f"esc_p{i}_valor"] = int(round(float(actual if actual is not None else 0)))
            elif isinstance(paso, float) and not isinstance(actual, float):
                ss[f"esc_p{i}_valor"] = float(actual if actual is not None else 0)
            ss[f"esc_p{i}_valor"] = min(max(ss[f"esc_p{i}_valor"], lo), hi)
            etiqueta = {"multiplicar": "Factor (1,10 = +10 %)", "sumar": "Cuánto suma (negativo resta)",
                        "fijar_minimo": "Mínimo", "fijar_maximo": "Máximo"}[op]
            c3.number_input(etiqueta, min_value=lo, max_value=hi, step=paso, key=f"esc_p{i}_valor",
                            format="%.2f" if isinstance(paso, float) else "%d")
            p = ParametroPolitica(v.nombre, op, valor=float(ss[f"esc_p{i}_valor"]), cobertura=ss[f"esc_p{i}_cob"] / 100)
        c4.slider("Llega al (% de los elegibles)", 0, 100, step=5, key=f"esc_p{i}_cob",
                  help="Proporción de los estudiantes elegibles del segmento que recibe el cambio.")
        palancas.append(p)
        # Valor actual, rango válido y fuente (sección 7.2)
        x = base.loc[seg, v.nombre]
        if n_seg:
            if v.es_ordenable:
                actual_txt = (f"media {v.formatear(x.mean()) if v.es_numerica else ui.num(x.mean(), 1)} "
                              f"(de {v.formatear(x.min())} a {v.formatear(x.max())})")
            else:
                dist = v.distribucion(x)
                actual_txt = ", ".join(f"{e} {ui.pct(q, 0)}" for e, q in zip(v.valores, dist))
        else:
            actual_txt = "—"
        n_eleg = int(elegibles(base, p, seg).sum())
        st.caption(
            f"**Valor actual en el segmento:** {actual_txt} · **Rango válido:** {v.describir_valores()} · "
            f"**Elegibles:** {ui.num(n_eleg)}; reciben el cambio ≈ {ui.num(round(p.cobertura * n_eleg))} · "
            f"**Fuente:** {v.fuente_referencia}"
        )
    variables_usadas = [p.variable for p in palancas]
    errores = []
    if len(set(variables_usadas)) < len(variables_usadas):
        errores.append("Cada palanca debe cambiar una variable distinta.")
    for p in palancas:
        if p.operacion == "cambiar" and p.desde == p.hacia:
            errores.append(f"En «{cat[p.variable].etiqueta}», la categoría de origen y la de destino son la misma.")
    for e in errores:
        st.error(e, icon=":material/error:")

# 4. Modo
with st.container(border=True):
    st.markdown("##### 4 · ¿Cómo se aplica?")
    ui.proposito("elegir cómo se construye la población del escenario y cuántas veces se repite. Las réplicas sirven "
                 "para saber si un efecto es real o se debe al azar.")
    m1, m2 = st.columns([3, 2])
    m1.radio("Modo de aplicación", ["ajuste", "regeneracion"], key="esc_modo", horizontal=True,
             format_func=lambda m: "Ajuste directo" if m == "ajuste" else "Regeneración (simulada)")
    if ss["esc_modo"] == "ajuste":
        m1.caption("**Ajuste directo:** se cambia el valor de la variable con una regla. Instantáneo, gratis y fácil "
                   "de explicar; las demás variables no cambian, aunque en la realidad irían juntas.")
    else:
        m1.caption("**Regeneración:** el LLM vuelve a generar el segmento con el prompt modificado; las variables "
                   "quedan coherentes entre sí. Tarda, cuesta y el LLM puede exagerar las relaciones. "
                   "En el prototipo lo hace el generador simulado.")
    m2.slider("Réplicas", 1, 10, key="esc_replicas", help="Se repite el escenario para medir el ruido.")
    m2.number_input("Semilla", min_value=0, max_value=999_999, step=1, key="esc_semilla",
                    help="Con la misma semilla, el mismo escenario da el mismo resultado.")
    st.toggle("Anotar qué efecto espero antes de ejecutar (opcional)", key="esc_esperado_on",
              help="Idea de Graf et al.: comparar la intuición con el resultado.")
    if ss["esc_esperado_on"]:
        st.number_input("Cambio que espero en los desertores esperados (%)", min_value=-100.0, max_value=100.0,
                        step=1.0, key="esc_esperado", format="%.0f")

escenario = Escenario(
    nombre=ss["esc_nombre"].strip() or "Escenario sin nombre",
    politica=ss["esc_politica"],
    descripcion=POLITICAS[ss["esc_politica"]]["descripcion"],
    segmento=segmento,
    palancas=palancas,
    modo=ss["esc_modo"],
    replicas=int(ss["esc_replicas"]),
    semilla=int(ss["esc_semilla"]),
    efecto_esperado=float(ss["esc_esperado"]) if ss["esc_esperado_on"] else None,
)

# 5. Estimación y ejecución
estimacion = estimar_costo(escenario, base, params)
prompt = r.plantilla.escenario(escenario, base, r.generador, params, params["llm_referencia"]["estudiantes_por_llamada"])
tokens_llamada = estimar_tokens(prompt)
regenera = escenario.modo == "regeneracion"
with st.container(border=True):
    st.markdown("##### 5 · Antes de ejecutar")
    ui.proposito("ver cuánto costaría y tardaría con el modelo de lenguaje antes de gastar; es la base del análisis de "
                 "costos del proyecto. El prompt es exactamente lo que se le enviaría.")
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Reciben el cambio", f"≈ {ui.num(estimacion['reciben_cambio'])}", border=True,
              help="Estudiantes del segmento a los que llega la política (suma de las palancas).")
    e2.metric("Se generan con el LLM", ui.num(estimacion["regenerados"]) if regenera else "0", border=True,
              help="En regeneración: todo el segmento, una vez por réplica. En ajuste directo no se llama al LLM.")
    e3.metric("Tiempo con el LLM", ui.minutos(estimacion["minutos"]) if regenera else "0 min",
              border=True, help="Con lo medido en la prueba de generación: unos 60 estudiantes por minuto, una llamada a la vez.")
    e4.metric("Costo estimado", ui.usd(estimacion["usd"]), border=True,
              help=f"Unos US$0,16 por cada 1000 estudiantes con {params['llm_referencia']['modelo']}. "
                   "En el prototipo no se gasta nada.")
    st.markdown("**La política:** " + "; ".join(p.describir(cat[p.variable]) for p in palancas) +
                f". **Segmento:** {segmento.describir(cat)}.")
    with st.expander(f"Ver el prompt que se enviaría al LLM (≈ {ui.num(tokens_llamada)} tokens por llamada)",
                     icon=":material/description:"):
        st.caption(f"Versión {r.plantilla.version}. El coordinador no edita el prompt: lo llena la herramienta. "
                   "Solo lleva porcentajes agregados y reglas, ninguna fila de estudiantes."
                   + ("" if regenera else " En ajuste directo no se envía: se muestra para comparar."))
        st.code(prompt, language="markdown", wrap_lines=True)

    puede = n_seg > 0 and not errores
    if st.button("Ejecutar escenario", type="primary", icon=":material/play_arrow:", disabled=not puede):
        version_sim = hashlib.sha1(json.dumps(params["simulacion_llm"], sort_keys=True).encode()).hexdigest()[:6]
        clave = escenario.clave(pob.version, modelo.version, r.generador.version, r.plantilla.version, version_sim)
        previo = repo.buscar_por_clave(clave)
        fecha = estado.ahora()
        hash_prompt = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10]
        if previo is not None:
            ej = previo["ejecucion"]
            ss["res_escenario"] = ej["id"]
            repo.registrar({**ej, "fecha": fecha, "escenario": escenario.nombre, "politica": escenario.politica,
                            "segmento": segmento.describir(cat), "estudiantes_segmento": n_seg,
                            "estudiantes_cambiados": previo["replicas"][0]["cambiados"],
                            "costo_estimado_usd": 0.0, "llamadas_estimadas": 0, "tokens_entrada_estimados": 0,
                            "tiempo_estimado_min": 0.0, "duracion_s": 0.0, "reutilizada": "Sí", "replicas": escenario.replicas,
                            "modo": escenario.modo})
            st.info("Este escenario ya se había ejecutado con la misma línea base, el mismo modelo y el mismo prompt: "
                    "se reutiliza el resultado guardado, así no se paga dos veces.", icon=":material/cached:")
        else:
            inicio = time.time()
            with st.status("Ejecutando el escenario…", expanded=True) as estado_ejec:
                barra = st.progress(0.0, text="Preparando…")
                resumen, riesgos, poblacion_r1 = ejecutar(
                    escenario, base, riesgo, r.generador, modelo, cat, params,
                    al_avanzar=lambda f, texto: barra.progress(f, text=texto))
                estado_ejec.update(label="Escenario ejecutado", state="complete", expanded=False)
            duracion = time.time() - inicio
            id_ej = f"{dt.datetime.now():%Y%m%d-%H%M%S}-{clave[:6]}"
            ejecucion = Ejecucion(
                id=id_ej, clave=clave, escenario=escenario.a_dict(), fecha=fecha, duracion_s=round(duracion, 2),
                reutilizada=False, generador=r.generador.nombre,
                modelo_llm=f"ninguno (simulado; costo estimado con {params['llm_referencia']['modelo']})" if regenera else "ninguno",
                version_prompt=r.plantilla.version if regenera else "—", hash_prompt=hash_prompt if regenera else "—",
                tokens_entrada_estimados=tokens_llamada * estimacion["llamadas"], llamadas_estimadas=estimacion["llamadas"],
                estudiantes_regenerados=estimacion["regenerados"], tiempo_estimado_min=round(estimacion["minutos"], 2),
                costo_estimado_usd=round(estimacion["usd"], 4), linea_base=pob.version, version_modelo=modelo.version,
            )
            repo.guardar_resultado(ejecucion, resumen, riesgos, poblacion_r1)
            fila = {**ejecucion.__dict__, "escenario": escenario.nombre, "politica": escenario.politica,
                    "modo": escenario.modo, "replicas": escenario.replicas, "segmento": segmento.describir(cat),
                    "estudiantes_segmento": n_seg, "estudiantes_cambiados": resumen["replicas"][0]["cambiados"],
                    "reutilizada": "No"}
            repo.registrar(fila)
            ss["res_escenario"] = id_ej
            st.success(f"Listo en {ui.num(duracion, 1)} s. Con el LLM habría tardado "
                       f"{ui.minutos(estimacion['minutos']) if regenera else 'lo mismo: el ajuste directo no lo usa'}.",
                       icon=":material/check_circle:")
        st.page_link("interfaz/resultados.py", label="Ver los resultados", icon=":material/arrow_forward:")
    if not puede:
        st.caption("Corrija lo marcado arriba para poder ejecutar.")
