"""
sesion_cookie.py — Mantiene la sesión al recargar la página (F5), sin librerías extra.

Cómo funciona:
  * Al iniciar sesión, el navegador guarda en una cookie SOLO el "refresh token" de
    Supabase (nunca la contraseña ni el correo).
  * Al recargar, Streamlit lee esa cookie (st.context.cookies) y pide a Supabase una
    sesión nueva con ella. Supabase rota el token en cada uso, así que la cookie se
    vuelve a escribir con el nuevo.
  * Al cerrar sesión, la cookie se borra y el token se revoca en Supabase.

Seguridad:
  * La cookie dura 14 días, es SameSite=Lax y Secure cuando la página es https.
  * Si el valor de la cookie no tiene forma de token, se ignora.
  * Si algo falla, no pasa nada grave: el usuario simplemente inicia sesión otra vez.
"""
import json
import re

import streamlit as st
import streamlit.components.v1 as components

NOMBRE = "fe_rt"
DIAS = 14
_TOKEN_VALIDO = re.compile(r"[A-Za-z0-9_\-.]{6,512}")


def token_valido(token) -> bool:
    return isinstance(token, str) and _TOKEN_VALIDO.fullmatch(token) is not None


def leer():
    """Token guardado en el navegador, o None si no hay o no es válido."""
    try:
        token = st.context.cookies.get(NOMBRE)
    except Exception:
        return None
    return token if token_valido(token) else None


def _emitir(valor: str, segundos: int) -> None:
    js = (
        "(function(){"
        f"var n={json.dumps(NOMBRE)},v={json.dumps(valor)},s={int(segundos)},seguro=false;"
        "try{seguro=window.parent.location.protocol==='https:';}catch(e){}"
        "document.cookie=n+'='+v+'; Max-Age='+s+'; Path=/; SameSite=Lax'+(seguro?'; Secure':'');"
        "})();"
    )
    components.html(f"<script>{js}</script>", height=0)


def guardar(token: str) -> None:
    if token_valido(token):
        _emitir(token, DIAS * 24 * 3600)


def borrar() -> None:
    _emitir("", 0)
