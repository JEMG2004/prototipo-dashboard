"""Clave de acceso para cuando el tablero está publicado.

Render no trae control de acceso: cualquiera con la dirección podría entrar. Si existe la variable de entorno
CLAVE_ACCESO (en Render) o el secreto CLAVE_ACCESO (en Streamlit Community Cloud), el tablero pide esa clave antes de
mostrar las pantallas. En el computador, sin ninguna de las dos, no pide nada.
Es una clave compartida para mostrar el prototipo, no un sistema de usuarios.
"""
from __future__ import annotations

import hmac
import os

import streamlit as st


def _clave() -> str:
    clave = os.environ.get("CLAVE_ACCESO", "")
    if not clave:
        try:
            clave = str(st.secrets.get("CLAVE_ACCESO", ""))
        except Exception:  # noqa: BLE001 - sin archivo de secretos no hay clave
            clave = ""
    return clave.strip()


def acceso_permitido() -> bool:
    clave = _clave()
    if not clave or st.session_state.get("acceso_ok"):
        return True

    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        st.title("Simulador de permanencia")
        st.caption("Prototipo con datos simulados. Escriba la clave de acceso.")
        with st.form("acceso"):
            intento = st.text_input("Clave de acceso", type="password")
            entrar = st.form_submit_button("Entrar", type="primary")
        if entrar:
            if hmac.compare_digest(intento.strip().encode("utf-8"), clave.encode("utf-8")):
                st.session_state["acceso_ok"] = True
                st.rerun()
            st.error("Esa no es la clave.", icon=":material/lock:")
    return False
