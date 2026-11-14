"""Gráficos del tablero (Altair), con una sola paleta para el modo claro y el oscuro.

Reglas que se siguen en todos los gráficos:
- el color sigue a la entidad: azul = línea base, naranja = escenario, en todas las pantallas;
- barras delgadas (máximo 24 px) con el extremo de los datos redondeado;
- un solo eje de valores (nunca dos escalas);
- leyenda cuando hay dos series o más; etiquetas solo donde ayudan;
- el texto usa los colores de texto, nunca el de la serie;
- cada gráfico tiene su tabla ("Ver los datos") y sus etiquetas emergentes.
"""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

LINEA_BASE = "Línea base"
ESCENARIO = "Escenario"
FUENTE = "system-ui, -apple-system, 'Segoe UI', sans-serif"

CLARO = {
    "serie": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
    "superficie": "#f9f9f7",
    "tinta": "#0b0b0b",
    "tinta2": "#52514e",
    "tenue": "#898781",
    "rejilla": "#e1e0d9",
    "eje": "#c3c2b7",
}
OSCURO = {
    "serie": ["#3987e5", "#d95926", "#199e70", "#c98500"],
    "superficie": "#0d0d0d",
    "tinta": "#f0efec",
    "tinta2": "#c3c2b7",
    "tenue": "#898781",
    "rejilla": "#2c2c2a",
    "eje": "#383835",
}

LOCALE = alt.Locale(number=alt.NumberLocale(decimal=",", thousands=".", grouping=[3], currency=["US$", ""],
                                             percent="\u00a0%"))


def formato_tabla(df: pd.DataFrame) -> dict:
    """Números con el formato del navegador (coma decimal en español)."""
    return {c: st.column_config.NumberColumn(format="localized") for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])}


def tokens() -> dict:
    tipo = None
    try:
        tipo = st.context.theme.type
    except Exception:  # noqa: BLE001 - versiones sin st.context.theme
        tipo = None
    return OSCURO if tipo == "dark" else CLARO


def _config(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    t = tokens()
    return (
        chart.configure(background="transparent", font=FUENTE, locale=LOCALE,
                        padding={"left": 2, "right": 16, "top": 6, "bottom": 2})
        .configure_view(stroke=None)
        .configure_axis(
            domainColor=t["eje"], gridColor=t["rejilla"], gridWidth=1, tickColor=t["eje"],
            labelColor=t["tinta2"], titleColor=t["tinta2"], labelFontSize=12, titleFontSize=12,
            titleFontWeight="normal", labelFont=FUENTE, titleFont=FUENTE, titlePadding=8,
        )
        .configure_axisY(grid=False, ticks=False, domain=False, labelPadding=6)
        .configure_legend(labelColor=t["tinta2"], titleColor=t["tinta2"], labelFontSize=12, orient="top",
                          symbolSize=110, labelFont=FUENTE, padding=0, offset=6)
    )


def mostrar(chart, tabla: pd.DataFrame | None = None, column_config: dict | None = None, clave: str | None = None) -> None:
    """Dibuja el gráfico y debajo deja su tabla."""
    st.altair_chart(_config(chart), theme=None, width="stretch", key=clave)
    if tabla is not None:
        with st.expander("Ver los datos", icon=":material/table_view:"):
            st.dataframe(tabla, hide_index=True, column_config=column_config or formato_tabla(tabla), width="stretch")


def _eje_x(titulo: str, formato: str, dominio=None, cero: bool = True) -> alt.X:
    escala = alt.Scale(domain=dominio, zero=cero, nice=True) if dominio else alt.Scale(zero=cero, nice=True)
    return alt.X("valor:Q", title=titulo, scale=escala, axis=alt.Axis(format=formato, tickCount=5, grid=True))


def barras(df: pd.DataFrame, categoria: str, valor: str, titulo_x: str, formato: str = ",.1f", orden=None,
           serie: int = 0, dominio=None, referencia: float | None = None, texto_referencia: str = "",
           tooltip: list | None = None, formato_eje: str | None = None) -> alt.LayerChart:
    """Barras horizontales de una serie, con el valor en la punta."""
    t = tokens()
    datos = df.rename(columns={valor: "valor", categoria: "categoria"})
    base = alt.Chart(datos).encode(
        y=alt.Y("categoria:N", sort=orden or None, title=None, axis=alt.Axis(labelLimit=260)),
        x=_eje_x(titulo_x, formato_eje or formato, dominio),
        tooltip=tooltip or [alt.Tooltip("categoria:N", title="Grupo"), alt.Tooltip("valor:Q", title=titulo_x, format=formato)],
    )
    capas = [
        base.mark_bar(size=18, cornerRadiusEnd=4, color=t["serie"][serie]),
        base.transform_filter("datum.valor >= 0").mark_text(
            align="left", baseline="middle", dx=5, fontSize=12, color=t["tinta2"]).encode(
            text=alt.Text("valor:Q", format=formato)),
        base.transform_filter("datum.valor < 0").mark_text(
            align="right", baseline="middle", dx=-5, fontSize=12, color=t["tinta2"]).encode(
            text=alt.Text("valor:Q", format=formato)),
    ]
    if referencia is not None:
        ref = pd.DataFrame({"valor": [referencia], "texto": [texto_referencia]})
        regla = alt.Chart(ref).encode(x="valor:Q")
        capas.append(regla.mark_rule(color=t["tinta"], strokeWidth=1.5))
        capas.append(regla.mark_text(align="left", baseline="top", dx=4, dy=-2, y=0, fontSize=11, color=t["tinta2"])
                     .encode(text="texto:N"))
    return alt.layer(*capas).properties(height=alt.Step(30))


def barras_con_marca(df: pd.DataFrame, categoria: str, valor: str, marca: str, nombre_valor: str, nombre_marca: str,
                     titulo_x: str, formato: str = ",.1f", orden=None, serie: int = 0,
                     formato_eje: str | None = None) -> alt.LayerChart:
    """Barras (lo que hay) con una marca negra (la referencia o lo esperado)."""
    t = tokens()
    datos = df.rename(columns={categoria: "categoria"})
    escala = alt.Scale(domain=[nombre_valor, nombre_marca], range=[t["serie"][serie], t["tinta"]])
    tooltip = [
        alt.Tooltip("categoria:N", title="Grupo"),
        alt.Tooltip(f"{valor}:Q", title=nombre_valor, format=formato),
        alt.Tooltip(f"{marca}:Q", title=nombre_marca, format=formato),
    ]
    y = alt.Y("categoria:N", sort=orden or None, title=None, axis=alt.Axis(labelLimit=260))
    x_eje = alt.Axis(format=formato_eje or formato, tickCount=5, grid=True)
    barras_ = (alt.Chart(datos).mark_bar(size=16, cornerRadiusEnd=4)
               .transform_calculate(serie=f"'{nombre_valor}'")
               .encode(y=y, x=alt.X(f"{valor}:Q", title=titulo_x, axis=x_eje),
                       color=alt.Color("serie:N", scale=escala, legend=alt.Legend(title=None)), tooltip=tooltip))
    marcas = (alt.Chart(datos).mark_tick(thickness=2.5, size=26)
              .transform_calculate(serie=f"'{nombre_marca}'")
              .encode(y=y, x=alt.X(f"{marca}:Q"), color=alt.Color("serie:N", scale=escala), tooltip=tooltip))
    return alt.layer(barras_, marcas).properties(height=alt.Step(32))


def pesas(df: pd.DataFrame, categoria: str, col_base: str, col_esc: str, titulo_x: str, formato: str = ",.1f",
          orden=None, extra_tooltip: list | None = None, formato_eje: str | None = None) -> alt.LayerChart:
    """Línea base frente a escenario por grupo: un punto para cada uno, unidos por una línea."""
    t = tokens()
    datos = df.rename(columns={categoria: "categoria"})
    largo = datos.melt(id_vars=[c for c in datos.columns if c not in (col_base, col_esc)],
                       value_vars=[col_base, col_esc], var_name="serie", value_name="valor")
    largo["serie"] = largo["serie"].map({col_base: LINEA_BASE, col_esc: ESCENARIO})
    escala = alt.Scale(domain=[LINEA_BASE, ESCENARIO], range=[t["serie"][0], t["serie"][1]])
    y = alt.Y("categoria:N", sort=orden or None, title=None, axis=alt.Axis(labelLimit=260))
    tooltip = [alt.Tooltip("categoria:N", title="Grupo"),
               alt.Tooltip(f"{col_base}:Q", title=LINEA_BASE, format=formato),
               alt.Tooltip(f"{col_esc}:Q", title=ESCENARIO, format=formato)] + (extra_tooltip or [])
    union = alt.Chart(datos).mark_rule(color=t["tenue"], strokeWidth=2).encode(
        y=y, x=alt.X(f"{col_base}:Q", title=titulo_x, axis=alt.Axis(format=formato_eje or formato, tickCount=5, grid=True),
                     scale=alt.Scale(zero=False, nice=True)),
        x2=f"{col_esc}:Q", tooltip=tooltip)
    tooltip_punto = [alt.Tooltip("categoria:N", title="Grupo"), alt.Tooltip("serie:N", title="Serie"),
                     alt.Tooltip("valor:Q", title=titulo_x, format=formato)]
    color = alt.Color("serie:N", scale=escala, legend=alt.Legend(title=None))
    # La línea base va como anillo y el escenario como punto: si coinciden, se ven los dos.
    anillo = alt.Chart(largo).transform_filter(f"datum.serie == '{LINEA_BASE}'").mark_point(
        filled=False, size=150, opacity=1, strokeWidth=2.5).encode(y=y, x=alt.X("valor:Q"), color=color,
                                                                    tooltip=tooltip_punto)
    punto = alt.Chart(largo).transform_filter(f"datum.serie == '{ESCENARIO}'").mark_point(
        filled=True, size=70, opacity=1, stroke=t["superficie"], strokeWidth=2).encode(y=y, x=alt.X("valor:Q"),
                                                                                       color=color, tooltip=tooltip_punto)
    return alt.layer(union, anillo, punto).properties(height=alt.Step(32))


def rango_escenarios(df: pd.DataFrame, base: float, titulo_x: str, formato: str = ",.1f") -> alt.LayerChart:
    """Varios escenarios lado a lado: media de las réplicas y su rango, frente a la línea base."""
    t = tokens()
    filas = [{"nombre": LINEA_BASE, "media": base, "min": base, "max": base, "serie": LINEA_BASE, "delta": 0.0}]
    for _, f in df.iterrows():
        filas.append({"nombre": f["nombre"], "media": f["media"], "min": f["min"], "max": f["max"],
                      "serie": ESCENARIO, "delta": f["media"] - base})
    datos = pd.DataFrame(filas)
    orden = datos["nombre"].tolist()
    escala = alt.Scale(domain=[LINEA_BASE, ESCENARIO], range=[t["serie"][0], t["serie"][1]])
    y = alt.Y("nombre:N", sort=orden, title=None, axis=alt.Axis(labelLimit=300))
    x_eje = alt.Axis(format=formato, tickCount=5, grid=True)
    tooltip = [alt.Tooltip("nombre:N", title="Escenario"), alt.Tooltip("media:Q", title="Media", format=formato),
               alt.Tooltip("min:Q", title="Mínimo", format=formato), alt.Tooltip("max:Q", title="Máximo", format=formato),
               alt.Tooltip("delta:Q", title="Cambio", format="+" + formato.lstrip("+"))]
    guia = alt.Chart(pd.DataFrame({"x": [base]})).mark_rule(color=t["serie"][0], strokeWidth=1, opacity=0.6).encode(x="x:Q")
    rango = alt.Chart(datos).mark_rule(strokeWidth=2, color=t["serie"][1]).encode(
        y=y, x=alt.X("min:Q", title=titulo_x, axis=x_eje, scale=alt.Scale(zero=False, nice=True)), x2="max:Q",
        tooltip=tooltip)
    puntos = alt.Chart(datos).mark_point(filled=True, size=100, opacity=1, stroke=t["superficie"], strokeWidth=2).encode(
        y=y, x="media:Q", color=alt.Color("serie:N", scale=escala, legend=alt.Legend(title=None)), tooltip=tooltip)
    return alt.layer(guia, rango, puntos).properties(height=alt.Step(36))


def _linea_con_cruz(datos: pd.DataFrame, x: str, y: str, titulo_x: str, titulo_y: str, color: str,
                    formato_x: str, formato_y: str, tooltip: list) -> list:
    t = tokens()
    cerca = alt.selection_point(nearest=True, on="pointerover", fields=[x], empty=False, clear="pointerout")
    base = alt.Chart(datos).encode(
        x=alt.X(f"{x}:Q", title=titulo_x, axis=alt.Axis(format=formato_x, tickCount=6, grid=False)),
        y=alt.Y(f"{y}:Q", title=titulo_y, axis=alt.Axis(format=formato_y, tickCount=5, grid=True)),
    )
    return [
        base.mark_line(strokeWidth=2, color=color, strokeCap="round", strokeJoin="round"),
        base.mark_point(filled=True, size=70, opacity=1, color=color, stroke=t["superficie"], strokeWidth=2),
        alt.Chart(datos).mark_rule(color=t["eje"], strokeWidth=1).encode(x=f"{x}:Q").transform_filter(cerca),
        base.mark_point(size=900, opacity=0).encode(tooltip=tooltip).add_params(cerca),
        base.mark_point(filled=True, size=130, color=color, stroke=t["superficie"], strokeWidth=2).encode(
            opacity=alt.condition(cerca, alt.value(1), alt.value(0))),
    ]


def dosis(df: pd.DataFrame) -> alt.LayerChart:
    """Cambios grandes: efecto según la intensidad del cambio (en el código, «dosis»), con el rango de las réplicas."""
    t = tokens()
    c = t["serie"][1]
    tooltip = [alt.Tooltip("dosis:Q", title="Intensidad", format=",.2f"),
               alt.Tooltip("delta:Q", title="Cambio medio en desertores", format="+,.1f"),
               alt.Tooltip("delta_min:Q", title="Mínimo", format="+,.1f"),
               alt.Tooltip("delta_max:Q", title="Máximo", format="+,.1f")]
    banda = alt.Chart(df).mark_area(opacity=0.12, color=c).encode(
        x="dosis:Q", y="delta_min:Q", y2="delta_max:Q")
    cero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=t["eje"], strokeWidth=1).encode(y="y:Q")
    capas = [banda, cero] + _linea_con_cruz(df, "dosis", "delta", "Intensidad del cambio (1 = el definido; 0 = regenerar sin cambios)",
                                            "Cambio en desertores esperados", c, ",.2f", ",.0f", tooltip)
    return alt.layer(*capas).properties(height=280)


def calibracion(df: pd.DataFrame) -> alt.LayerChart:
    t = tokens()
    c = t["serie"][0]
    tooltip = [alt.Tooltip("predicho:Q", title="Riesgo estimado medio", format=".0%"),
               alt.Tooltip("observado:Q", title="Desertores observados", format=".0%")]
    diagonal = alt.Chart(pd.DataFrame({"x": [0, 1], "y": [0, 1]})).mark_line(color=t["tenue"], strokeWidth=1).encode(
        x="x:Q", y="y:Q")
    capas = [diagonal] + _linea_con_cruz(df, "predicho", "observado", "Riesgo estimado (promedio del grupo)",
                                         "Desertores en los datos de prueba", c, ".0%", ".0%", tooltip)
    return alt.layer(*capas).properties(height=300)


def histograma(riesgo: pd.Series, umbral: float) -> alt.LayerChart:
    t = tokens()
    datos = pd.DataFrame({"riesgo": riesgo})
    barras_ = alt.Chart(datos).mark_bar(color=t["serie"][0], cornerRadiusTopLeft=3, cornerRadiusTopRight=3,
                                        binSpacing=2).encode(
        x=alt.X("riesgo:Q", bin=alt.Bin(step=0.05, extent=[0, 1]), title="Riesgo estimado de desertar",
                axis=alt.Axis(format=".0%", tickCount=6, grid=False)),
        y=alt.Y("count():Q", title="Estudiantes", axis=alt.Axis(tickCount=5, grid=True)),
        tooltip=[alt.Tooltip("riesgo:Q", bin=alt.Bin(step=0.05, extent=[0, 1]), title="Riesgo", format=".0%"),
                 alt.Tooltip("count():Q", title="Estudiantes")],
    )
    regla = alt.Chart(pd.DataFrame({"x": [umbral], "texto": [f"Umbral de riesgo alto: {round(umbral * 100)} %"]}))
    capas = [barras_, regla.mark_rule(color=t["tinta"], strokeWidth=1.5).encode(x="x:Q"),
             regla.mark_text(align="left", dx=5, y=4, baseline="top", fontSize=11, color=t["tinta2"]).encode(
                 x="x:Q", text="texto:N")]
    return alt.layer(*capas).properties(height=260)
