"""Piezas de la interfaz que se repiten: formatos en español, encabezados, barra lateral."""
from __future__ import annotations

import datetime as dt

import streamlit as st

from datos import repositorio as repo
from interfaz import estado

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


def num(x: float, dec: int = 0) -> str:
    texto = f"{x:,.{dec}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x: float, dec: int = 1) -> str:
    """x es una proporción (0,25 -> 25,0 %)."""
    return f"{num(100 * x, dec)} %"


def usd(x: float) -> str:
    return f"US${num(x, 2)}"


def con_signo(x: float, dec: int = 1, sufijo: str = "") -> str:
    """Con guion ASCII para que st.metric reconozca el signo."""
    return f"{'-' if x < 0 else '+'}{num(abs(x), dec)}{sufijo}"


def fecha(iso: str) -> str:
    try:
        d = dt.datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}, {d:%H:%M}"


def minutos(m: float) -> str:
    if m < 1:
        return "menos de 1 min"
    if m < 60:
        return f"{num(m, 0)} min"
    return f"{num(m // 60, 0)} h {num(m % 60, 0)} min"


def encabezado(titulo: str, subtitulo: str) -> None:
    st.title(titulo)
    st.caption(subtitulo)


def proposito(texto: str) -> None:
    """Para qué sirve una sección y por qué está en el tablero: una línea visible bajo su título."""
    st.caption(f":material/lightbulb: **Para qué sirve:** {texto}")


def explicacion(titulo: str, cuerpo: str, abierta: bool = False) -> None:
    """Una explicación más larga, plegada para no tapar los resultados."""
    with st.expander(titulo, expanded=abierta, icon=":material/help:"):
        st.markdown(cuerpo)


ICONOS = {"ruido": ":material/horizontal_rule:", "leve": ":material/trending_down:",
          "moderado": ":material/trending_down:", "importante": ":material/keyboard_double_arrow_down:"}


def insignia(clas: dict, prefijo: str = "") -> None:
    nivel, direccion = clas["nivel"], clas["direccion"]
    if nivel == "ruido":
        color, icono = "gray", ICONOS["ruido"]
    elif direccion == "mejora":
        color = "green" if nivel != "leve" else "blue"
        icono = ICONOS[nivel]
    else:
        color, icono = "red", ":material/trending_up:"
    st.badge(f"{prefijo}{clas['etiqueta']}", icon=icono, color=color)


def preservar_formularios(prefijos: tuple[str, ...] = ("esc_", "diag_", "res_", "lb_", "sup_")) -> None:
    """Streamlit borra el estado de los controles de una página al salir de ella; esto lo conserva.

    Los controles con estas claves no reciben valor por defecto en el código: se inicializan con
    inicial(), para no mezclar los dos mecanismos.
    """
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith(prefijos):
            st.session_state[k] = st.session_state[k]


def inicial(clave: str, valor) -> None:
    if clave not in st.session_state:
        st.session_state[clave] = valor


def barra_lateral() -> None:
    r = estado.recursos()
    pob = estado.linea_base()
    with st.sidebar:
        st.badge("Prototipo: datos simulados", icon=":material/science:", color="orange")
        st.caption(
            f"**Línea base:** {num(pob.n)} estudiantes sintéticos · semilla {pob.semilla}  \n"
            f"Generada el {fecha(pob.creada)}  \n"
            f"{pob.origen}"
        )
        if estado.linea_base_desactualizada():
            st.warning("El catálogo o las reglas cambiaron después de generar la línea base. Conviene regenerarla.",
                       icon=":material/sync_problem:")
        with st.expander("Regenerar la línea base"):
            pp = r.params["poblacion"]
            n = st.number_input("Estudiantes", min_value=200, max_value=5000, value=int(pp["n_linea_base"]), step=100,
                                key="lat_n")
            semilla = st.number_input("Semilla", min_value=0, max_value=999_999, value=int(pp["semilla_linea_base"]),
                                      step=1, key="lat_semilla")
            st.caption("Los resultados ya guardados siguen asociados a la línea base con que se ejecutaron.")
            if st.button("Generar de nuevo", icon=":material/autorenew:", width="stretch"):
                estado.crear_linea_base(int(n), int(semilla))
                st.toast("Línea base regenerada.", icon=":material/check_circle:")
                st.rerun()
        ejecuciones = len(repo.listar_resultados())
        st.caption(f"{ejecuciones} escenario{'s' if ejecuciones != 1 else ''} guardado{'s' if ejecuciones != 1 else ''}.")
