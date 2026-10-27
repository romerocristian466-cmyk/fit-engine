"""
Fit Engine v2.0 — app.py
Coach de Salud IA | 100% texto | Sin audio ni dependencias de voz.
Streamlit Cloud ready.
"""
import streamlit as st
import os

import dotenv
import plotly.graph_objects as go
import pandas as pd
from fpdf import FPDF
from google import genai

import vision_service
import metabolic_engine
import db
import db_supabase

# ──────────────────────────────────────────────────────────────────────────────
# Arranque
# ──────────────────────────────────────────────────────────────────────────────
dotenv.load_dotenv()

# Sincronizar st.secrets → os.environ (Streamlit Cloud)
try:
    for key, value in st.secrets.items():
        os.environ[key] = str(value)
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# Configuración de página y sidebar
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Fit Engine Coach", layout="centered")
st.title("🍏 Fit Engine Coach")

# ──────────────────────────────────────────────────────────────────────────────
# Acceso: modo local (SQLite, sin login) o nube (Supabase + login por usuario)
# ──────────────────────────────────────────────────────────────────────────────
# El MODO LOCAL existe solo para desarrollar en tu computadora y se activa con
# FIT_ENGINE_MODO_LOCAL=1. Sin esa variable la app EXIGE Supabase y login, así nunca
# cae por accidente en una base de datos compartida entre todos los visitantes.
MODO_LOCAL = os.getenv("FIT_ENGINE_MODO_LOCAL") == "1"


def _repo():
    """Repositorio de datos de ESTA sesión (nunca compartido entre usuarios)."""
    return db if MODO_LOCAL else st.session_state["sb_repo"]


def _cerrar_sesion() -> None:
    db_supabase.cerrar_sesion(st.session_state.get("sb_cliente"))
    # Se borra TODO el estado (chat, nombre, peso, formularios): nada pasa al siguiente usuario
    st.session_state.clear()


def _guardar_perfil_cb() -> None:
    """Callback: guarda nombre y meta de peso cuando el usuario los cambia."""
    nombre = (st.session_state.get("nombre") or "").strip()[:60] or None
    meta = float(st.session_state.get("meta_peso_sidebar") or 0.0)
    _repo().guardar_perfil(nombre, meta)


def _acceder(url: str, key: str, accion: str, email: str, clave: str) -> None:
    """Intenta iniciar sesión o crear la cuenta; si funciona, entra a la app."""
    cliente = db_supabase.crear_cliente(url, key)   # un cliente nuevo por sesión
    try:
        if accion == "entrar":
            db_supabase.iniciar_sesion(cliente, email, clave)
        elif not db_supabase.registrar(cliente, email, clave):
            st.success("Cuenta creada ✅ Revisa tu correo para confirmarla y luego inicia sesión.")
            return
    except db_supabase.ErrorAcceso as e:
        st.error(str(e))
        return
    sesion = db_supabase.sesion_actual(cliente)
    if sesion is None:
        st.error("No se pudo iniciar la sesión. Inténtalo de nuevo.")
        return
    st.session_state["sb_cliente"] = cliente
    st.session_state["sb_repo"] = db_supabase.RepoSupabase(cliente, sesion.user.id)
    st.rerun()


def _pantalla_acceso(url: str, key: str) -> None:
    st.subheader("Bienvenido 👋")
    st.caption("Inicia sesión o crea tu cuenta para guardar tu progreso. Solo tú ves tus datos.")
    tab_entrar, tab_crear = st.tabs(["Iniciar sesión", "Crear cuenta"])

    with tab_entrar:
        with st.form("form_login"):
            email = st.text_input("Correo", key="login_email")
            clave = st.text_input("Contraseña", type="password", key="login_clave")
            enviar = st.form_submit_button("Entrar", key="btn_entrar")
        if enviar:
            _acceder(url, key, "entrar", email, clave)

    with tab_crear:
        with st.form("form_registro"):
            email_r = st.text_input("Correo", key="reg_email")
            clave_r = st.text_input("Contraseña (mínimo 8 caracteres)", type="password", key="reg_clave")
            clave_r2 = st.text_input("Repite la contraseña", type="password", key="reg_clave2")
            enviar_r = st.form_submit_button("Crear cuenta", key="btn_crear")
        if enviar_r:
            if clave_r != clave_r2:
                st.error("Las contraseñas no coinciden.")
            else:
                _acceder(url, key, "crear", email_r, clave_r)

    st.caption(
        "Al usar el coach y el escáner de comida, tus mensajes y fotos se envían a "
        "Google Gemini para generar las respuestas."
    )


if MODO_LOCAL:
    db.init_db()
    email_sesion = None
else:
    _url, _key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")
    if not _url or not _key:
        st.error(
            "Falta configurar Supabase: agrega SUPABASE_URL y SUPABASE_KEY en los "
            "Secrets de la app."
        )
        st.stop()
    _sesion = db_supabase.sesion_actual(st.session_state.get("sb_cliente"))
    if _sesion is None:
        if "sb_cliente" in st.session_state:
            st.session_state.clear()   # la sesión venció o se cerró: no se arrastra nada
        _pantalla_acceso(_url, _key)
        st.stop()
    email_sesion = _sesion.user.email

# Perfil guardado (nombre y meta de peso): se carga una sola vez por sesión
if "_perfil_cargado" not in st.session_state:
    _perfil = _repo().obtener_perfil()
    st.session_state["nombre"] = _perfil.get("nombre") or ""
    st.session_state["meta_peso_sidebar"] = min(
        max(float(_perfil.get("meta_peso_kg") or 0.0), 0.0), 200.0
    )
    st.session_state["_perfil_cargado"] = True

if not MODO_LOCAL:
    st.sidebar.caption(f"Sesión: **{email_sesion}**")
    if st.sidebar.button("Cerrar sesión", key="btn_cerrar_sesion"):
        _cerrar_sesion()
        st.rerun()
    st.sidebar.markdown("---")

st.sidebar.subheader("👤 Tu perfil")
st.sidebar.text_input(
    "Tu nombre", key="nombre", placeholder="¿Cómo te llamas?",
    max_chars=60, on_change=_guardar_perfil_cb,
)
nombre_usuario = (st.session_state.get("nombre") or "").strip() or "amigo"

st.sidebar.markdown("---")
st.sidebar.subheader("⚖️ Tu perfil de lastre")
lastre_munecas_lb_sidebar = st.sidebar.number_input(
    "Pesas de muñecas (lb por mano)",
    min_value=0.0, max_value=10.0, value=0.5, step=0.5,
    help="Se usará para calcular el gasto calórico real con lastre.",
    key="lastre_munecas_sidebar",
)
lastre_tobillos_lb_sidebar = st.sidebar.number_input(
    "Pesas de tobillos (lb por pie)",
    min_value=0.0, max_value=10.0, value=0.5, step=0.5,
    help="Los tobillos tienen mayor impacto biomecánico (×1.5).",
    key="lastre_tobillos_sidebar",
)
# El valor inicial se fija una sola vez en la sesión (sin `value=`), porque el
# formulario de peso lo vuelve a modificar desde un callback.
if "peso_usuario_sidebar" not in st.session_state:
    _ultimo_peso = _repo().obtener_ultimo_peso()
    st.session_state["peso_usuario_sidebar"] = (
        min(max(_ultimo_peso, 30.0), 200.0) if _ultimo_peso else 70.0
    )
peso_usuario_kg_sidebar = st.sidebar.number_input(
    "Tu peso corporal (kg)",
    min_value=30.0, max_value=200.0, step=0.5,
    help="Por defecto es tu último peso registrado.",
    key="peso_usuario_sidebar",
)
meta_peso_kg = st.sidebar.number_input(
    "Meta de peso (kg)",
    min_value=0.0, max_value=200.0, step=0.5,
    help="Opcional. Si la pones, aparece como línea en la gráfica de peso. 0 = sin meta.",
    key="meta_peso_sidebar",
    on_change=_guardar_perfil_cb,
)

st.sidebar.markdown("---")
st.sidebar.caption(
    "⚖️ **Descargo Médico:** Fit Engine es una guía de hábitos y estilo de vida. "
    "No constituye diagnóstico ni tratamiento médico."
)

# ──────────────────────────────────────────────────────────────────────────────
# Estado de sesión
# ──────────────────────────────────────────────────────────────────────────────
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = [
        {
            "role": "assistant",
            "content": (
                "¡Hola! Bienvenido a Fit Engine 🍏. Soy tu coach de salud. "
                "Para conocernos, ¿cuál es tu objetivo principal "
                "(perder grasa, mantener peso o ganar músculo)? "
                "Si quieres, escribe tu nombre en la barra lateral."
            ),
        }
    ]

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_COACH = """Eres un coach de salud y nutrición empático llamado Fit Engine.
Tu filosofía se basa en:
- "Solo por hoy" (Alcohólicos Anónimos): enfocarse en ganar las próximas 24 horas.
- Hábitos Atómicos (James Clear): mejoras del 1% diario, sin culpa por el pasado.

Tu rol es orientar al usuario en nutrición, actividad física y hábitos saludables mediante
conversación de texto. Haz máximo 1-2 preguntas por turno. Sé cálido, sin juzgar.

REGLA DE SEGURIDAD: si el usuario menciona un trastorno alimenticio (anorexia, bulimia,
atracones), una restricción extrema de comida, ser menor de edad o estar embarazada/en
lactancia, NO des cifras de calorías, ayuno ni planes de pérdida de peso. Responde con
empatía y recomiéndale hablar con un profesional de salud (médico o nutricionista).

DESCARGO MÉDICO: Fit Engine es una herramienta de acompañamiento de hábitos. No proporciona
diagnósticos médicos ni reemplaza la evaluación de un profesional de salud."""


MAX_MENSAJES_CONTEXTO = 12


def obtener_respuesta_coach(historial: list[dict]) -> str:
    """Llama a Gemini con los últimos mensajes y retorna la respuesta del coach."""
    try:
        recientes = historial[-MAX_MENSAJES_CONTEXTO:]
        # Si se recortó el historial, asegurar que arranque con un mensaje del usuario
        if len(historial) > MAX_MENSAJES_CONTEXTO:
            while recientes and recientes[0]["role"] != "user":
                recientes = recientes[1:]

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        # Construir el contenido para Gemini
        contents = []
        for msg in recientes:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config={"system_instruction": SYSTEM_PROMPT_COACH},
        )
        return response.text.strip()
    except Exception as e:
        # El detalle técnico solo va al log del servidor, no a la pantalla del usuario
        print(f"[coach] Error al llamar a Gemini: {type(e).__name__}: {e}")
        return "⚠️ No pude conectar con el coach, intenta de nuevo."


def _cuota_ia(tipo: str) -> tuple[bool, str]:
    """Descuenta un uso diario de IA. Devuelve (puede_continuar, mensaje_para_el_usuario).

    Si no se puede verificar el límite, NO se llama a Gemini (falla cerrado)."""
    try:
        permitido, usados, limite = _repo().consumir_cuota(tipo)
    except Exception:
        return False, "⚠️ No pude verificar tu límite diario. Inténtalo de nuevo en un momento."
    nombre = "mensajes al coach" if tipo == "chat" else "fotos analizadas"
    if not permitido:
        return False, (f"Llegaste al límite de hoy ({limite} {nombre}). "
                       "Se reinicia mañana. ¡Gracias por entender! 🙏")
    return True, f"Hoy llevas {usados} de {limite} {nombre}."


def calcular_compliance(pasos: int, meta: int, minutos: int, protocol_rest: bool) -> float:
    """Score 0-100 basado en cumplimiento de pasos, ejercicio y descanso."""
    score_pasos     = min(pasos / meta, 1.0) * 50.0
    score_ejercicio = min(minutos / 30.0, 1.0) * 30.0
    score_descanso  = 20.0 if protocol_rest else 0.0
    return round(score_pasos + score_ejercicio + score_descanso, 1)


def _racha(df: "pd.DataFrame") -> int:
    """Calcula la racha de días consecutivos con compliance ≥ 80%."""
    try:
        cumplidos = set(df.loc[df["compliance_score"] >= 80, "fecha"].dt.normalize())
        dia = pd.Timestamp(db.hoy())
        if dia not in cumplidos:
            dia -= pd.Timedelta(days=1)  # hoy todavía puede no estar registrado
        racha = 0
        while dia in cumplidos:
            racha += 1
            dia -= pd.Timedelta(days=1)
        return racha
    except Exception:
        return 0


def _tendencia_lineal(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Recta de mínimos cuadrados y = m·x + b. Requiere al menos 2 valores de x distintos."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    m = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return m, my - m * mx


def _guardar_peso_cb() -> None:
    """Callback del formulario de peso: guarda y sincroniza el peso del sidebar."""
    fecha_p = st.session_state["peso_form_fecha"]
    peso_p = float(st.session_state["peso_form_kg"])
    _repo().guardar_peso(fecha_p, peso_p)
    ultimo = _repo().obtener_ultimo_peso()
    if ultimo is not None:
        # Un callback corre antes de redibujar, por eso sí puede cambiar el widget del sidebar
        st.session_state["peso_usuario_sidebar"] = min(max(ultimo, 30.0), 200.0)
    st.session_state["_peso_guardado_msg"] = (fecha_p, peso_p)


# ──────────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────────
tab_chat, tab_actividad, tab_dashboard, tab_reporte = st.tabs([
    "💬 Coach IA",
    "👟 Mi Actividad",
    "📊 Dashboard",
    "📄 Reporte Clínico",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Coach IA (chat de texto puro, sin audio)
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.header("💬 Coach de Salud IA")
    st.caption("Chatea con tu coach para recibir orientación personalizada en nutrición y hábitos.")

    # ── Mostrar historial ────────────────────────────────────────────────────
    for msg in st.session_state.historial_chat:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    # ── Entrada de texto ─────────────────────────────────────────────────────
    if prompt := st.chat_input("Escribe tu mensaje aquí..."):
        # Guardar y mostrar mensaje del usuario
        st.session_state.historial_chat.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.write(prompt)

        # Obtener y mostrar respuesta del coach (respetando el límite diario)
        puede, aviso_cuota = _cuota_ia("chat")
        if puede:
            with st.spinner("El coach está pensando..."):
                respuesta = obtener_respuesta_coach(st.session_state.historial_chat)
        else:
            respuesta = aviso_cuota

        st.session_state.historial_chat.append({"role": "assistant", "content": respuesta})
        with st.chat_message("assistant"):
            st.write(respuesta)
        if puede:
            st.caption(aviso_cuota)

    # ── Botón para limpiar el chat ───────────────────────────────────────────
    if len(st.session_state.historial_chat) > 1:
        if st.button("🔄 Iniciar nueva conversación"):
            st.session_state.historial_chat = [
                {
                    "role": "assistant",
                    "content": (
                        f"¡Hola de nuevo, {nombre_usuario}! 🍏 "
                        "¿En qué te puedo ayudar hoy?"
                    ),
                }
            ]
            st.rerun()

    st.divider()

    # ── Escáner de Comida con Gemini Vision ──────────────────────────────────
    st.header("🍽️ Escáner de Comida")
    st.caption("Sube una foto de tu plato y el coach analizará su contenido nutricional.")
    uploaded_file = st.file_uploader(
        "Sube una foto de tu plato", type=["jpg", "jpeg", "png"]
    )
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Plato a analizar", width="stretch")
        if st.button("🔍 Analizar Plato"):
            puede_foto, aviso_foto = _cuota_ia("foto")
            if not puede_foto:
                st.warning(aviso_foto)
            else:
                st.caption(aviso_foto)
                with st.spinner("Analizando con Gemini Vision..."):
                    try:
                        analisis = vision_service.analizar_imagen_comida(
                            uploaded_file.getvalue(),
                            nombre_usuario=nombre_usuario,
                        )
                        st.info(f"**Mensaje del Coach:**\n\n{analisis.mensaje_coach}")
                        st.write("### Desglose Nutricional")
                        st.write(f"**Calorías Totales:** {analisis.calorias_totales} kcal")
                        st.json([ing.model_dump() for ing in analisis.ingredientes])
                    except Exception as e:
                        # El detalle técnico solo va al log del servidor
                        print(f"[vision] Error: {type(e).__name__}: {e}")
                        st.error("No pude analizar la imagen. Inténtalo de nuevo con otra foto.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Mi Actividad (ajuste metabólico proactivo + persistencia SQLite)
# ══════════════════════════════════════════════════════════════════════════════
with tab_actividad:
    st.header("👟 Registro de Actividad Física")

    # ── Ajuste Metabólico Proactivo ──────────────────────────────────────────
    modo_recuperacion   = _repo().necesita_ajuste_recuperacion()
    META_PASOS_DEFAULT  = 8000

    if modo_recuperacion:
        META_PASOS_SUGERIDA = 7000
        LASTRE_MUNECAS_SUGERIDO_LB  = 1.0
        LASTRE_TOBILLOS_SUGERIDO_LB = 1.0
        st.warning(
            "⚠️ **Modo Recuperación Activado** — Los últimos 2 días registrados "
            "no incluyeron descanso (`protocol_rest = 0`). "
            "Para proteger tu recuperación muscular, la meta de pasos se ha reducido "
            f"a **{META_PASOS_SUGERIDA:,} pasos** y se recomienda bajar el lastre a "
            f"**{LASTRE_MUNECAS_SUGERIDO_LB} lb por extremidad**."
        )
    else:
        META_PASOS_SUGERIDA = META_PASOS_DEFAULT
        LASTRE_MUNECAS_SUGERIDO_LB  = lastre_munecas_lb_sidebar
        LASTRE_TOBILLOS_SUGERIDO_LB = lastre_tobillos_lb_sidebar

    st.info(
        f"🎯 Meta recomendada hoy: **{META_PASOS_SUGERIDA:,} pasos** · "
        f"Lastre sugerido: **{LASTRE_MUNECAS_SUGERIDO_LB} lb** muñecas · "
        f"**{LASTRE_TOBILLOS_SUGERIDO_LB} lb** tobillos"
    )

    # ── Formulario de registro ───────────────────────────────────────────────
    with st.form("form_actividad"):
        fecha          = st.date_input("Fecha", value=db.hoy())
        pasos          = st.number_input(
            "Pasos registrados en el día", min_value=0, max_value=200000, step=500, value=0
        )
        mins_ejercicio = st.number_input(
            "Minutos de ejercicio", min_value=0, max_value=1440, step=15, value=0
        )
        tipo           = st.text_input(
            "Tipo de ejercicio", value="Caminata / Cardio", max_chars=100
        )

        col_a, col_b = st.columns(2)
        with col_a:
            lastre_munecas = st.number_input(
                "Lastre muñecas (lb por mano)",
                min_value=0.0, max_value=10.0,
                value=float(LASTRE_MUNECAS_SUGERIDO_LB), step=0.5,
            )
        with col_b:
            lastre_tobillos = st.number_input(
                "Lastre tobillos (lb por pie)",
                min_value=0.0, max_value=10.0,
                value=float(LASTRE_TOBILLOS_SUGERIDO_LB), step=0.5,
            )

        protocol_rest = st.checkbox(
            "✅ Hoy completé mi protocolo de descanso / recuperación",
            value=False,
        )
        notas = st.text_area(
            "Notas opcionales", height=80, placeholder="¿Cómo te sentiste hoy?",
            max_chars=2000,
        )

        submitted = st.form_submit_button("💾 Guardar Registro")

    if submitted:
        compliance = calcular_compliance(
            pasos, META_PASOS_SUGERIDA, mins_ejercicio, protocol_rest
        )
        kcal = db.calcular_calorias_con_lastre(
            pasos=pasos,
            peso_usuario_kg=peso_usuario_kg_sidebar,
            lastre_munecas_lb=lastre_munecas,
            lastre_tobillos_lb=lastre_tobillos,
            mins_ejercicio=mins_ejercicio,
        )
        _repo().guardar_registro(
            fecha=fecha,
            pasos=pasos,
            minutos_ejercicio=mins_ejercicio,
            tipo_ejercicio=tipo,
            lastre_munecas_lb=lastre_munecas,
            lastre_tobillos_lb=lastre_tobillos,
            protocol_rest=protocol_rest,
            compliance_score=compliance,
            notas=notas,
        )
        st.success(
            f"✅ Registro guardado — {pasos:,} pasos · {mins_ejercicio} min · "
            f"~**{kcal} kcal** con lastre · Score: **{compliance}/100**"
        )
        if compliance >= 80:
            st.balloons()
            st.info("🏆 ¡Día de élite! Sigue construyendo tu identidad, 1% mejor cada día.")
        elif compliance >= 50:
            st.info("💪 ¡Buen esfuerzo! Mañana puedes superarlo.")
        else:
            st.warning("📉 Día difícil. El movimiento consistente gana la batalla, no la perfección.")

    # ── Historial reciente ───────────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Últimos 7 días")
    registros = _repo().obtener_ultimos_registros(7)
    if registros:
        st.dataframe(
            registros,
            column_config={
                "fecha":              st.column_config.DateColumn("Fecha"),
                "pasos":              st.column_config.NumberColumn("Pasos", format="%d"),
                "compliance_score":   st.column_config.ProgressColumn("Score %", min_value=0, max_value=100),
                "lastre_munecas_lb":  st.column_config.NumberColumn("Lastre M. (lb)"),
                "lastre_tobillos_lb": st.column_config.NumberColumn("Lastre T. (lb)"),
                "protocol_rest":      st.column_config.CheckboxColumn("Descanso"),
            },
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Aún no hay registros. ¡Guarda tu primer día!")

    # ── Peso corporal ────────────────────────────────────────────────────────
    st.divider()
    st.subheader("⚖️ Peso corporal")
    with st.form("form_peso"):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.date_input("Fecha", value=db.hoy(), max_value=db.hoy(), key="peso_form_fecha")
        with col_p2:
            st.number_input(
                "Peso (kg)", min_value=30.0, max_value=200.0,
                value=float(peso_usuario_kg_sidebar), step=0.1, key="peso_form_kg",
            )
        st.form_submit_button(
            "💾 Guardar peso", on_click=_guardar_peso_cb, key="btn_guardar_peso"
        )
    st.caption("Si registras una fecha que ya existe, se reemplaza el peso de ese día.")
    _msg_peso = st.session_state.pop("_peso_guardado_msg", None)
    if _msg_peso:
        st.success(f"✅ Peso guardado — **{_msg_peso[1]:.1f} kg** ({_msg_peso[0]})")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Dashboard con Mapa de Calor de Cumplimiento
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.header("📊 Dashboard de Progreso")

    registros_90 = _repo().obtener_rango(dias=90)

    if not registros_90:
        st.info("Aún no hay registros. Empieza a registrar en la pestaña 👟.")
    else:
        df = pd.DataFrame(registros_90)
        df["fecha"]      = pd.to_datetime(df["fecha"])
        df["semana"]     = df["fecha"].dt.isocalendar().week.astype(int)
        df["dia_semana"] = df["fecha"].dt.day_of_week   # 0=Lun … 6=Dom

        # ── KPIs rápidos ──────────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📅 Días registrados", len(df))
        col2.metric("👟 Pasos promedio", f"{int(df['pasos'].mean()):,}")
        col3.metric("🏆 Score promedio", f"{df['compliance_score'].mean():.1f}/100")
        col4.metric("🔥 Racha actual", f"{_racha(df)} días")

        st.divider()

        # ── Mapa de Calor de Cumplimiento ──────────────────────────────────
        st.subheader("🗓️ Mapa de Calor — Cumplimiento Diario")
        st.caption("🟢 Verde ≥ 80%  ·  🟠 Naranja 50-79%  ·  🔴 Rojo < 50%")

        dias_labels = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        pivot = df.pivot_table(
            index="dia_semana", columns="semana",
            values="compliance_score", aggfunc="mean",
        ).reindex(range(7))

        z_values  = pivot.values.tolist()
        text_vals = [
            [f"{v:.0f}%" if v == v else "—" for v in row]   # NaN → "—"
            for row in z_values
        ]

        fig_heat = go.Figure(go.Heatmap(
            z=z_values,
            x=[f"Sem {s}" for s in pivot.columns],
            y=dias_labels,
            text=text_vals,
            texttemplate="%{text}",
            textfont={"size": 11, "color": "white"},
            colorscale=[
                [0.0,  "#c0392b"],
                [0.79, "#e67e22"],
                [0.80, "#27ae60"],
                [1.0,  "#1abc9c"],
            ],
            zmin=0, zmax=100,
            showscale=True,
            colorbar=dict(title="Score %", ticksuffix="%"),
        ))
        fig_heat.update_layout(
            height=320,
            margin=dict(l=60, r=20, t=30, b=30),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            xaxis=dict(side="top"),
        )
        st.plotly_chart(fig_heat, width="stretch")

        st.divider()

        # ── Línea de pasos ─────────────────────────────────────────────────
        st.subheader("👟 Pasos diarios")
        fig_pasos = go.Figure()
        fig_pasos.add_trace(go.Scatter(
            x=df["fecha"], y=df["pasos"],
            mode="lines+markers",
            line=dict(color="#3498db", width=2),
            marker=dict(size=6),
            name="Pasos",
        ))
        fig_pasos.add_hline(
            y=8000, line_dash="dash", line_color="#27ae60", opacity=0.6,
            annotation_text="Meta 8,000", annotation_position="bottom right",
        )
        fig_pasos.update_layout(
            height=280, showlegend=False,
            margin=dict(l=20, r=20, t=20, b=30),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
        )
        st.plotly_chart(fig_pasos, width="stretch")

        st.divider()

        # ── Gasto calórico con lastre ───────────────────────────────────────
        st.subheader("🔥 Gasto calórico estimado con lastre")
        kcal_lista = [
            db.calcular_calorias_con_lastre(
                pasos=r["pasos"],
                peso_usuario_kg=peso_usuario_kg_sidebar,
                lastre_munecas_lb=r["lastre_munecas_lb"],
                lastre_tobillos_lb=r["lastre_tobillos_lb"],
                mins_ejercicio=r["minutos_ejercicio"],
            )
            for r in registros_90
        ]
        fig_kcal = go.Figure(go.Bar(
            x=df["fecha"], y=kcal_lista,
            marker_color=["#e74c3c" if k < 300 else "#2ecc71" for k in kcal_lista],
        ))
        fig_kcal.update_layout(
            height=260, showlegend=False,
            margin=dict(l=20, r=20, t=20, b=30),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
        )
        st.plotly_chart(fig_kcal, width="stretch")

    # ── Peso corporal: tendencia y meta ──────────────────────────────────────
    st.divider()
    st.subheader("⚖️ Peso corporal")
    pesos = _repo().obtener_pesos(dias=180)
    if not pesos:
        st.info("Aún no hay pesos registrados. Agrégalos en la pestaña 👟, sección Peso corporal.")
    else:
        df_peso = pd.DataFrame(pesos)
        df_peso["fecha"] = pd.to_datetime(df_peso["fecha"])
        primera, ultima = df_peso["fecha"].iloc[0], df_peso["fecha"].iloc[-1]
        peso_primero = float(df_peso["peso_kg"].iloc[0])
        peso_actual  = float(df_peso["peso_kg"].iloc[-1])

        fig_peso = go.Figure()
        fig_peso.add_trace(go.Scatter(
            x=df_peso["fecha"], y=df_peso["peso_kg"],
            mode="lines+markers",
            line=dict(color="#9b59b6", width=2),
            marker=dict(size=7),
            name="Peso",
        ))

        pendiente_semana = None
        if len(df_peso) >= 3:
            xs = [float(d) for d in (df_peso["fecha"] - primera).dt.days]
            ys = [float(p) for p in df_peso["peso_kg"]]
            m, b = _tendencia_lineal(xs, ys)
            fig_peso.add_trace(go.Scatter(
                x=[primera, ultima], y=[b, m * xs[-1] + b],
                mode="lines",
                line=dict(color="#f1c40f", width=2, dash="dot"),
                name="Tendencia",
            ))
            if xs[-1] >= 7:   # con menos de una semana de datos, el ritmo semanal engaña
                pendiente_semana = m * 7

        if meta_peso_kg > 0:
            # Como línea (no add_hline) para que el eje Y siempre incluya la meta
            fig_peso.add_trace(go.Scatter(
                x=[primera, ultima], y=[meta_peso_kg, meta_peso_kg],
                mode="lines",
                line=dict(color="#27ae60", width=2, dash="dash"),
                name=f"Meta {meta_peso_kg:g} kg",
            ))

        fig_peso.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=30, b=30),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
            yaxis=dict(title="kg"),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig_peso, width="stretch")

        resumen = [
            f"Peso actual: **{peso_actual:.1f} kg**",
            f"Cambio desde el primer registro: **{peso_actual - peso_primero:+.1f} kg**",
        ]
        if pendiente_semana is not None:
            resumen.append(f"Tendencia: **{pendiente_semana:+.2f} kg/semana**")
        if meta_peso_kg > 0:
            resumen.append(f"Faltan **{abs(peso_actual - meta_peso_kg):.1f} kg** para tu meta")
        st.markdown(" · ".join(resumen))


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Reporte Clínico PDF
# ══════════════════════════════════════════════════════════════════════════════
def generar_pdf_reporte(nombre: str, registros: list[dict], peso_kg: float) -> bytes:
    """Genera un PDF clínico con el resumen semanal usando fpdf2."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Encabezado
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(39, 174, 96)
    pdf.cell(0, 12, "Fit Engine Coach", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, "Reporte Clinico Semanal", ln=True, align="C")
    pdf.cell(0, 6, f"Generado el: {db.hoy().strftime('%d/%m/%Y')}", ln=True, align="C")
    pdf.cell(0, 6, f"Paciente / Usuario: {nombre}", ln=True, align="C")
    pdf.ln(8)
    pdf.set_draw_color(39, 174, 96)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Métricas agregadas
    pasos_totales     = sum(r["pasos"] for r in registros)
    dias_descanso     = sum(1 for r in registros if r["protocol_rest"])
    compliance_prom   = sum(r["compliance_score"] for r in registros) / len(registros)
    kcal_total        = sum(
        db.calcular_calorias_con_lastre(
            pasos=r["pasos"], peso_usuario_kg=peso_kg,
            lastre_munecas_lb=r["lastre_munecas_lb"],
            lastre_tobillos_lb=r["lastre_tobillos_lb"],
            mins_ejercicio=r["minutos_ejercicio"],
        )
        for r in registros
    )
    dias_elite = sum(1 for r in registros if r["compliance_score"] >= 80)

    # Resumen ejecutivo
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Resumen Ejecutivo (ultimos 7 dias)", ln=True)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    for label, valor in [
        ("Pasos totales de la semana",         f"{pasos_totales:,}"),
        ("Gasto calorico estimado con lastre", f"{kcal_total:,.0f} kcal"),
        ("Promedio de cumplimiento (Score)",   f"{compliance_prom:.1f} / 100"),
        ("Dias de elite (score >= 80%)",       f"{dias_elite} de {len(registros)}"),
        ("Dias con protocolo de descanso",     f"{dias_descanso} de {len(registros)}"),
    ]:
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(120, 8, label, border=0, fill=True)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(70, 8, valor, border=0, fill=True, ln=True)
        pdf.set_font("Helvetica", "", 11)
    pdf.ln(6)

    # Tabla diaria
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Detalle Diario", ln=True)
    pdf.ln(2)
    headers = ["Fecha", "Pasos", "Min.", "Lastre M.", "Lastre T.", "Desc.", "Score"]
    widths  = [30, 28, 18, 24, 24, 18, 28]
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(39, 174, 96)
    pdf.set_text_color(255, 255, 255)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()
    pdf.set_font("Helvetica", "", 9)
    for i, r in enumerate(reversed(registros)):
        fill = i % 2 == 0
        pdf.set_fill_color(250, 250, 250) if fill else pdf.set_fill_color(240, 240, 240)
        score = r["compliance_score"]
        pdf.set_text_color(39, 174, 96) if score >= 80 else pdf.set_text_color(192, 57, 43)
        for val, w in zip([
            r["fecha"], f"{r['pasos']:,}", str(r["minutos_ejercicio"]),
            f"{r['lastre_munecas_lb']} lb", f"{r['lastre_tobillos_lb']} lb",
            "Si" if r["protocol_rest"] else "No", f"{score:.0f}%",
        ], widths):
            pdf.cell(w, 6, val, border=1, fill=fill, align="C")
        pdf.ln()
    pdf.ln(8)

    # Descargo médico
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(
        0, 5,
        "DESCARGO: Fit Engine es una herramienta de acompanamiento de habitos, actividad "
        "y estilo de vida. No proporciona diagnosticos medicos, no prescribe tratamientos "
        "farmacologicos ni reemplaza la evaluacion de un profesional de la salud colegiado.",
    )
    return bytes(pdf.output())


with tab_reporte:
    st.header("📄 Reporte Clínico Semanal")
    st.markdown(
        "Genera un **PDF descargable** con el resumen de tu última semana: "
        "pasos totales, gasto calórico con lastre y cumplimiento de protocolos."
    )
    nombre_reporte = st.text_input(
        "Tu nombre (para el reporte)", value=nombre_usuario
    )
    if st.button("⚙️ Generar PDF"):
        registros_sem = _repo().obtener_ultimos_registros(7)
        if not registros_sem:
            st.warning("No hay registros en los últimos 7 días.")
        else:
            with st.spinner("Generando PDF..."):
                pdf_bytes = generar_pdf_reporte(
                    nombre=nombre_reporte,
                    registros=registros_sem,
                    peso_kg=peso_usuario_kg_sidebar,
                )
            st.download_button(
                label="📥 Descargar Reporte PDF",
                data=pdf_bytes,
                file_name=f"fit_engine_reporte_{db.hoy()}.pdf",
                mime="application/pdf",
            )
            st.success("✅ PDF listo. Haz clic arriba para descargarlo.")
