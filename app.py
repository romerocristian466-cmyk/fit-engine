"""
Fit Engine v2.0 — app.py
Coach de Salud IA | 100% texto | Sin audio ni dependencias de voz.
Streamlit Cloud ready.
"""
import streamlit as st
import os
from datetime import date, datetime
from zoneinfo import ZoneInfo

import dotenv
import plotly.graph_objects as go
import pandas as pd
from fpdf import FPDF
from google import genai

import vision_service
import metabolic_engine
import db

# ──────────────────────────────────────────────────────────────────────────────
# Arranque
# ──────────────────────────────────────────────────────────────────────────────
dotenv.load_dotenv()
db.init_db()

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

st.sidebar.subheader("👤 Tu perfil")
nombre_sidebar = st.sidebar.text_input("Tu nombre", key="nombre_sidebar", value="amigo")

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
peso_usuario_kg_sidebar = st.sidebar.number_input(
    "Tu peso corporal (kg)",
    min_value=30.0, max_value=200.0, value=70.0, step=0.5,
    key="peso_usuario_sidebar",
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
                "Para conocernos, ¿cuál es tu nombre y cuál es tu objetivo principal "
                "(perder grasa, mantener peso o ganar músculo)?"
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

Reglas:
- Si el usuario menciona trastorno alimenticio, restricción extrema, ser menor de edad o embarazo, no dar cifras de calorías y recomendar hablar con un profesional de salud.

DESCARGO MÉDICO: Fit Engine es una herramienta de acompañamiento de hábitos. No proporciona
diagnósticos médicos ni reemplaza la evaluación de un profesional de salud."""


def obtener_respuesta_coach(historial: list[dict]) -> str:
    """Llama a Gemini con los últimos 12 mensajes del historial y retorna la respuesta del coach."""
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        # Construir el contenido para Gemini solo con los últimos 12 mensajes
        contents = []
        for msg in historial[-12:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config={"system_instruction": SYSTEM_PROMPT_COACH},
        )
        return response.text.strip()
    except Exception:
        return "No pude conectar con el coach, intenta de nuevo"


def calcular_compliance(pasos: int, meta: int, minutos: int, protocol_rest: bool) -> float:
    """Score 0-100 basado en cumplimiento de pasos, ejercicio y descanso."""
    score_pasos     = min(pasos / meta, 1.0) * 50.0
    score_ejercicio = min(minutos / 30.0, 1.0) * 30.0
    score_descanso  = 20.0 if protocol_rest else 0.0
    return round(score_pasos + score_ejercicio + score_descanso, 1)


def _racha(df: "pd.DataFrame") -> int:
    """Calcula la racha de días consecutivos con compliance ≥ 80%."""
    try:
        df_sorted = df.sort_values("fecha", ascending=False)
        racha = 0
        hoy = pd.Timestamp(datetime.now(ZoneInfo("America/El_Salvador")).date())
        for _, row in df_sorted.iterrows():
            if row["compliance_score"] >= 80:
                diff = (hoy - row["fecha"]).days
                if diff == 0 or diff == 1:
                    racha += 1
                    hoy = row["fecha"]
                else:
                    break
            else:
                break
        return racha
    except Exception:
        return 0


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

        # Obtener y mostrar respuesta del coach
        with st.spinner("El coach está pensando..."):
            respuesta = obtener_respuesta_coach(st.session_state.historial_chat)

        st.session_state.historial_chat.append({"role": "assistant", "content": respuesta})
        with st.chat_message("assistant"):
            st.write(respuesta)

    # ── Botón para limpiar el chat ───────────────────────────────────────────
    if len(st.session_state.historial_chat) > 1:
        if st.button("🔄 Iniciar nueva conversación"):
            st.session_state.historial_chat = [
                {
                    "role": "assistant",
                    "content": (
                        f"¡Hola de nuevo, {st.session_state.nombre_sidebar}! 🍏 "
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
        st.image(uploaded_file, caption="Plato a analizar", use_container_width=True)
        if st.button("🔍 Analizar Plato"):
            with st.spinner("Analizando con Gemini Vision..."):
                try:
                    analisis = vision_service.analizar_imagen_comida(
                        uploaded_file.getvalue(),
                        nombre_usuario=st.session_state.nombre_sidebar,
                    )
                    st.info(f"**Mensaje del Coach:**\n\n{analisis.mensaje_coach}")
                    st.write("### Desglose Nutricional")
                    st.write(f"**Calorías Totales:** {analisis.calorias_totales} kcal")
                    st.json([ing.model_dump() for ing in analisis.ingredientes])
                except Exception as e:
                    st.error(f"Error procesando imagen: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Mi Actividad (ajuste metabólico proactivo + persistencia SQLite)
# ══════════════════════════════════════════════════════════════════════════════
with tab_actividad:
    st.header("👟 Registro de Actividad Física")

    # ── Ajuste Metabólico Proactivo ──────────────────────────────────────────
    modo_recuperacion   = db.necesita_ajuste_recuperacion()
    META_PASOS_DEFAULT  = 8000

    if modo_recuperacion:
        META_PASOS_SUGERIDA = 7000
        LASTRE_SUGERIDO_LB  = 1.0
        LASTRE_SUGERIDO_TOBILLOS_LB = 1.0
        st.warning(
            "⚠️ **Modo Recuperación Activado** — Los últimos 2 días registrados "
            "no incluyeron descanso (`protocol_rest = 0`). "
            "Para proteger tu recuperación muscular, la meta de pasos se ha reducido "
            f"a **{META_PASOS_SUGERIDA:,} pasos** y se recomienda bajar el lastre a "
            f"**{LASTRE_SUGERIDO_LB} lb por extremidad**."
        )
    else:
        META_PASOS_SUGERIDA = META_PASOS_DEFAULT
        LASTRE_SUGERIDO_LB  = lastre_munecas_lb_sidebar
        LASTRE_SUGERIDO_TOBILLOS_LB = lastre_tobillos_lb_sidebar

    st.info(
        f"🎯 Meta recomendada hoy: **{META_PASOS_SUGERIDA:,} pasos** · "
        f"Lastre sugerido: **{LASTRE_SUGERIDO_LB} lb muñecas / {LASTRE_SUGERIDO_TOBILLOS_LB} lb tobillos**"
    )

    # ── Formulario de registro ───────────────────────────────────────────────
    with st.form("form_actividad"):
        fecha          = st.date_input("Fecha", value=datetime.now(ZoneInfo("America/El_Salvador")).date())
        pasos          = st.number_input(
            "Pasos registrados en el día", min_value=0, step=500, value=0
        )
        mins_ejercicio = st.number_input(
            "Minutos de ejercicio", min_value=0, step=15, value=0
        )
        tipo           = st.text_input("Tipo de ejercicio", value="Caminata / Cardio")

        col_a, col_b = st.columns(2)
        with col_a:
            lastre_munecas = st.number_input(
                "Lastre muñecas (lb por mano)",
                min_value=0.0, max_value=10.0,
                value=float(LASTRE_SUGERIDO_LB), step=0.5,
            )
        with col_b:
            lastre_tobillos = st.number_input(
                "Lastre tobillos (lb por pie)",
                min_value=0.0, max_value=10.0,
                value=float(LASTRE_SUGERIDO_TOBILLOS_LB), step=0.5,
            )

        protocol_rest = st.checkbox(
            "✅ Hoy completé mi protocolo de descanso / recuperación",
            value=False,
        )
        notas = st.text_area(
            "Notas opcionales", height=80, placeholder="¿Cómo te sentiste hoy?"
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
        db.guardar_registro(
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
    registros = db.obtener_ultimos_registros(7)
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
            use_container_width=True,
        )
    else:
        st.info("Aún no hay registros. ¡Guarda tu primer día!")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Dashboard con Mapa de Calor de Cumplimiento
# ══════════════════════════════════════════════════════════════════════════════
with tab_dashboard:
    st.header("📊 Dashboard de Progreso")

    registros_90 = db.obtener_rango(dias=90)

    if not registros_90:
        st.info("Aún no hay registros. Empieza a registrar en la pestaña 👟.")
    else:
        df = pd.DataFrame(registros_90)
        df["fecha"]      = pd.to_datetime(df["fecha"])
        df["semana"]     = df["fecha"].dt.isocalendar().week.astype(int)
        df["dia_semana"] = df["fecha"].dt.dayofweek   # 0=Lun … 6=Dom

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
        st.plotly_chart(fig_heat, use_container_width=True)

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
        st.plotly_chart(fig_pasos, use_container_width=True)

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
        st.plotly_chart(fig_kcal, use_container_width=True)


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
    pdf.cell(0, 6, f"Generado el: {datetime.now(ZoneInfo('America/El_Salvador')).date().strftime('%d/%m/%Y')}", ln=True, align="C")
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
        "Tu nombre (para el reporte)", value=st.session_state.nombre_sidebar.capitalize()
    )
    if st.button("⚙️ Generar PDF"):
        registros_sem = db.obtener_ultimos_registros(7)
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
                file_name=f"fit_engine_reporte_{datetime.now(ZoneInfo('America/El_Salvador')).date()}.pdf",
                mime="application/pdf",
            )
            st.success("✅ PDF listo. Haz clic arriba para descargarlo.")
