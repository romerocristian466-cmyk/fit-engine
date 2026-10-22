"""
Fit Engine v2.0 — app.py
Coach de Salud IA con persistencia SQLite, reportes PDF, ajuste metabólico
proactivo y mapa de calor de cumplimiento.
"""
import streamlit as st
import asyncio
import os
import io
import json
from datetime import date, timedelta

import dotenv
from google import genai
from google.genai import types
from audio_recorder_streamlit import audio_recorder
import plotly.graph_objects as go
from fpdf import FPDF

import interview_service
import vision_service
import voice_service
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

voz_seleccionada = st.sidebar.radio(
    "🎙️ Voz del Coach",
    options=["Dalia (Femenina)", "Jorge (Masculino)"],
    index=0,
)
st.session_state.voz_id = "dalia" if "Dalia" in voz_seleccionada else "jorge"

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
if "nombre" not in st.session_state:
    st.session_state.nombre = "amigo"

if "historial" not in st.session_state:
    welcome_msg = (
        "¡Hola! Bienvenido. Estoy aquí para acompañarte a ganar un día a la vez. "
        "Para empezar a conocernos, ¿cuál es tu nombre y cómo prefieres que te llame?"
    )
    try:
        audio_bytes = asyncio.run(
            voice_service.sintetizar_voz(welcome_msg, voz_id=st.session_state.voz_id)
        )
    except Exception:
        audio_bytes = None
    st.session_state.historial = [
        {"role": "model", "content": welcome_msg, "audio": audio_bytes}
    ]

if "last_audio" not in st.session_state:
    st.session_state.last_audio = None

if "played_initial_audio" not in st.session_state:
    st.session_state.played_initial_audio = False


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def procesar_respuesta(bot_reply: str) -> None:
    try:
        audio_bytes = asyncio.run(
            voice_service.sintetizar_voz(bot_reply, voz_id=st.session_state.voz_id)
        )
    except Exception:
        audio_bytes = None

    st.session_state.historial.append(
        {"role": "model", "content": bot_reply, "audio": audio_bytes}
    )
    with st.chat_message("assistant"):
        st.write(bot_reply)
        if audio_bytes:
            st.audio(audio_bytes, format="audio/mpeg", autoplay=True)


def calcular_compliance(pasos: int, meta: int, minutos: int, protocol_rest: bool) -> float:
    """Score 0-100 basado en cumplimiento de pasos, ejercicio y descanso."""
    score_pasos    = min(pasos / meta, 1.0) * 50.0
    score_ejercicio = min(minutos / 30.0, 1.0) * 30.0
    score_descanso  = 20.0 if protocol_rest else 0.0
    return round(score_pasos + score_ejercicio + score_descanso, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────────────────────────────────────
tab_chat, tab_actividad, tab_dashboard, tab_reporte = st.tabs([
    "💬 Coach & Visión",
    "👟 Mi Actividad",
    "📊 Dashboard",
    "📄 Reporte Clínico",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Coach & Visión
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.header("Entrevista Nutricional")

    for i, msg in enumerate(st.session_state.historial):
        role = "Usuario" if msg["role"] == "user" else "Coach"
        with st.chat_message("user" if role == "Usuario" else "assistant"):
            st.write(msg["content"])
            if msg.get("audio"):
                if i == 0 and not st.session_state.played_initial_audio:
                    st.audio(msg["audio"], format="audio/mpeg", autoplay=True)
                    st.session_state.played_initial_audio = True
                else:
                    st.audio(msg["audio"], format="audio/mpeg")

    col1, col2 = st.columns([0.8, 0.2])
    with col2:
        audio_bytes = audio_recorder(text="Voz", icon_size="2x", key="audio_mic")

    if prompt := st.chat_input("Escribe tu mensaje aquí..."):
        st.session_state.historial.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        try:
            resultado = interview_service.continuar_entrevista(
                st.session_state.historial[:-1], prompt
            )
            procesar_respuesta(resultado.get("respuesta", ""))
        except Exception as e:
            st.error(f"Error procesando chat: {e}")

    if audio_bytes and audio_bytes != st.session_state.last_audio:
        st.session_state.last_audio = audio_bytes
        try:
            with st.spinner("Escuchando..."):
                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                        (
                            "Transcribe de manera exacta lo que dice este audio en español, "
                            "sin agregar ningún otro comentario ni formato markdown. "
                            "Si está vacío o no se entiende, responde '[ININTELIGIBLE]'."
                        ),
                    ],
                )
                transcripcion = response.text.strip()
                st.session_state.historial.append(
                    {"role": "user", "content": transcripcion}
                )
                with st.chat_message("user"):
                    st.write(f"🎤 *{transcripcion}*")
                resultado = interview_service.continuar_entrevista(
                    st.session_state.historial[:-1], transcripcion
                )
                procesar_respuesta(resultado.get("respuesta", ""))
                st.rerun()
        except Exception as e:
            st.error(f"Error procesando audio: {e}")

    if st.button("Finalizar y Extraer Perfil"):
        with st.spinner("Extrayendo perfil y calculando métricas..."):
            try:
                perfil = interview_service.extraer_perfil_desde_chat(
                    st.session_state.historial
                )
                metricas = metabolic_engine.calcular_metricas(perfil)
                st.session_state.nombre = perfil.nombre
                st.success(
                    f"¡Bienvenido al camino, {st.session_state.nombre}! "
                    "Vamos a ganar un día a la vez."
                )
                st.json({"perfil": perfil.model_dump(), "metricas": metricas.model_dump()})
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    st.header("Escáner de Comida")
    uploaded_file = st.file_uploader(
        "Sube una foto de tu plato", type=["jpg", "jpeg", "png"]
    )
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Plato a analizar")
        if st.button("Analizar Plato"):
            with st.spinner("Analizando con Gemini Vision..."):
                try:
                    analisis = vision_service.analizar_imagen_comida(
                        uploaded_file.getvalue(),
                        nombre_usuario=st.session_state.nombre,
                    )
                    st.info(f"**Mensaje del Coach:**\n\n{analisis.mensaje_coach}")
                    st.write("### Desglose Nutricional")
                    st.write(f"**Calorías Totales:** {analisis.calorias_totales} kcal")
                    st.json([ing.model_dump() for ing in analisis.ingredientes])
                except Exception as e:
                    st.error(f"Error procesando imagen: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Mi Actividad (con ajuste metabólico proactivo y persistencia SQLite)
# ══════════════════════════════════════════════════════════════════════════════
with tab_actividad:
    st.header("👟 Registro de Actividad Física")

    # ── Ajuste Metabólico Proactivo ──────────────────────────────────────────
    modo_recuperacion = db.necesita_ajuste_recuperacion()
    META_PASOS_DEFAULT = 8000

    if modo_recuperacion:
        META_PASOS_SUGERIDA = 7000
        LASTRE_SUGERIDO_LB  = 1.0
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

    st.info(
        f"🎯 Meta recomendada hoy: **{META_PASOS_SUGERIDA:,} pasos** · "
        f"Lastre sugerido: **{LASTRE_SUGERIDO_LB} lb/extremidad**"
    )

    # ── Formulario de registro ───────────────────────────────────────────────
    with st.form("form_actividad"):
        fecha           = st.date_input("Fecha", value=date.today())
        pasos           = st.number_input(
            "Pasos registrados en el día", min_value=0, step=500, value=0
        )
        mins_ejercicio  = st.number_input(
            "Minutos de ejercicio", min_value=0, step=15, value=0
        )
        tipo            = st.text_input("Tipo de ejercicio", value="Caminata / Cardio")

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
                value=float(LASTRE_SUGERIDO_LB), step=0.5,
            )

        protocol_rest = st.checkbox(
            "✅ Hoy completé mi protocolo de descanso / recuperación",
            value=False,
        )
        notas = st.text_area("Notas opcionales", height=80, placeholder="¿Cómo te sentiste hoy?")

        submitted = st.form_submit_button("💾 Guardar Registro")

    if submitted:
        compliance = calcular_compliance(pasos, META_PASOS_SUGERIDA, mins_ejercicio, protocol_rest)
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
            f"~**{kcal} kcal** quemadas con lastre · Score: **{compliance}/100**"
        )
        if compliance >= 80:
            st.balloons()
            st.info("🏆 ¡Día de élite! Sigue construyendo tu identidad saludable, 1% mejor cada día.")
        elif compliance >= 50:
            st.info("💪 ¡Buen esfuerzo! Mañana puedes superarlo.")
        else:
            st.warning("📉 Día difícil. Recuerda: el movimiento consistente gana la batalla, no la perfección.")

    # ── Historial reciente ───────────────────────────────────────────────────
    st.divider()
    st.subheader("📋 Últimos 7 días")
    registros = db.obtener_ultimos_registros(7)
    if registros:
        st.dataframe(
            registros,
            column_config={
                "fecha":               st.column_config.DateColumn("Fecha"),
                "pasos":               st.column_config.NumberColumn("Pasos", format="%d"),
                "compliance_score":    st.column_config.ProgressColumn("Score %", min_value=0, max_value=100),
                "lastre_munecas_lb":   st.column_config.NumberColumn("Lastre M. (lb)"),
                "lastre_tobillos_lb":  st.column_config.NumberColumn("Lastre T. (lb)"),
                "protocol_rest":       st.column_config.CheckboxColumn("Descanso"),
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

    registros_30 = db.obtener_rango(dias=90)

    if not registros_30:
        st.info("Aún no hay registros. Empieza a registrar tu actividad en la pestaña 👟.")
    else:
        import pandas as pd

        df = pd.DataFrame(registros_30)
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["semana"] = df["fecha"].dt.isocalendar().week.astype(int)
        df["dia_semana"] = df["fecha"].dt.dayofweek   # 0=Lun … 6=Dom
        df["dia_nombre"] = df["fecha"].dt.strftime("%a %d/%m")

        # ── KPIs rápidos ──────────────────────────────────────────────────
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📅 Días registrados", len(df))
        col2.metric("👟 Pasos promedio", f"{int(df['pasos'].mean()):,}")
        col3.metric("🏆 Score promedio", f"{df['compliance_score'].mean():.1f}/100")
        col4.metric(
            "🔥 Racha actual",
            f"{_racha(df)} días",
            help="Días consecutivos con compliance_score ≥ 80%",
        )

        st.divider()

        # ── Mapa de Calor de Cumplimiento ──────────────────────────────────
        st.subheader("🗓️ Mapa de Calor — Cumplimiento Diario")
        st.caption("🟢 Verde ≥ 80% · 🔴 Rojo < 80%")

        # Construir matriz semana × día
        semanas_unicas = sorted(df["semana"].unique())
        dias_labels    = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

        # Pivotear: eje X = semana, eje Y = día de semana
        pivot = df.pivot_table(
            index="dia_semana", columns="semana",
            values="compliance_score", aggfunc="mean"
        ).reindex(range(7))

        z_values = pivot.values.tolist()
        # Anotar con el score o "-" si no hay dato
        text_vals = [
            [
                f"{v:.0f}%" if v == v else "—"   # NaN check
                for v in row
            ]
            for row in z_values
        ]

        fig_heat = go.Figure(
            go.Heatmap(
                z=z_values,
                x=[f"Sem {s}" for s in pivot.columns],
                y=dias_labels,
                text=text_vals,
                texttemplate="%{text}",
                textfont={"size": 11, "color": "white"},
                colorscale=[
                    [0.0,  "#c0392b"],   # rojo — 0%
                    [0.79, "#e67e22"],   # naranja — 79%
                    [0.80, "#27ae60"],   # verde — 80%+
                    [1.0,  "#1abc9c"],   # verde claro — 100%
                ],
                zmin=0, zmax=100,
                showscale=True,
                colorbar=dict(title="Score %", ticksuffix="%"),
            )
        )
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
            y=8000, line_dash="dash",
            line_color="#27ae60", opacity=0.6,
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

        # ── Gasto calórico con lastre (barras) ─────────────────────────────
        st.subheader("🔥 Gasto calórico estimado con lastre")
        kcal_lista = [
            db.calcular_calorias_con_lastre(
                pasos=r["pasos"],
                peso_usuario_kg=peso_usuario_kg_sidebar,
                lastre_munecas_lb=r["lastre_munecas_lb"],
                lastre_tobillos_lb=r["lastre_tobillos_lb"],
                mins_ejercicio=r["minutos_ejercicio"],
            )
            for r in registros_30
        ]
        fig_kcal = go.Figure(go.Bar(
            x=df["fecha"], y=kcal_lista,
            marker_color=["#e74c3c" if k < 300 else "#2ecc71" for k in kcal_lista],
            name="kcal",
        ))
        fig_kcal.update_layout(
            height=260, showlegend=False,
            margin=dict(l=20, r=20, t=20, b=30),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e0e0e0"),
        )
        st.plotly_chart(fig_kcal, use_container_width=True)


def _racha(df) -> int:
    """Calcula la racha de días consecutivos con compliance ≥ 80%."""
    try:
        import pandas as pd
        df_sorted = df.sort_values("fecha", ascending=False)
        racha = 0
        hoy = pd.Timestamp(date.today())
        for _, row in df_sorted.iterrows():
            if row["compliance_score"] >= 80 and (hoy - row["fecha"]).days <= racha + 1:
                racha += 1
                hoy = row["fecha"]
            else:
                break
        return racha
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Reporte Clínico PDF
# ══════════════════════════════════════════════════════════════════════════════
with tab_reporte:
    st.header("📄 Reporte Clínico Semanal")
    st.markdown(
        "Genera un PDF descargable con el resumen de tu última semana: "
        "pasos totales, gasto calórico con lastre y cumplimiento de protocolos."
    )

    nombre_reporte = st.text_input(
        "Tu nombre (para el reporte)", value=st.session_state.nombre.capitalize()
    )

    if st.button("⚙️ Generar PDF"):
        registros_sem = db.obtener_ultimos_registros(7)

        if not registros_sem:
            st.warning("No hay registros en los últimos 7 días para generar el reporte.")
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
                    file_name=f"fit_engine_reporte_{date.today()}.pdf",
                    mime="application/pdf",
                )
                st.success("✅ Reporte generado. Haz clic en el botón para descargarlo.")


def generar_pdf_reporte(nombre: str, registros: list[dict], peso_kg: float) -> bytes:
    """
    Genera un PDF clínico con el resumen semanal usando fpdf2.
    Retorna los bytes del PDF listo para descarga.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ── Encabezado ────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(39, 174, 96)      # verde
    pdf.cell(0, 12, "Fit Engine Coach", ln=True, align="C")

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, "Reporte Clinico Semanal", ln=True, align="C")
    pdf.cell(0, 6, f"Generado el: {date.today().strftime('%d/%m/%Y')}", ln=True, align="C")
    pdf.cell(0, 6, f"Paciente / Usuario: {nombre}", ln=True, align="C")
    pdf.ln(8)

    # ── Línea separadora ─────────────────────────────────────────────────────
    pdf.set_draw_color(39, 174, 96)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # ── Calcular métricas agregadas ───────────────────────────────────────────
    pasos_totales   = sum(r["pasos"] for r in registros)
    dias_con_descanso = sum(1 for r in registros if r["protocol_rest"])
    compliance_prom = sum(r["compliance_score"] for r in registros) / len(registros)
    kcal_total      = sum(
        db.calcular_calorias_con_lastre(
            pasos=r["pasos"],
            peso_usuario_kg=peso_kg,
            lastre_munecas_lb=r["lastre_munecas_lb"],
            lastre_tobillos_lb=r["lastre_tobillos_lb"],
            mins_ejercicio=r["minutos_ejercicio"],
        )
        for r in registros
    )
    dias_elite = sum(1 for r in registros if r["compliance_score"] >= 80)

    # ── Resumen Ejecutivo ─────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Resumen Ejecutivo (ultimos 7 dias)", ln=True)
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 11)
    metricas = [
        ("Pasos totales de la semana",          f"{pasos_totales:,}"),
        ("Gasto calorico estimado con lastre",  f"{kcal_total:,.0f} kcal"),
        ("Promedio de cumplimiento (Score)",    f"{compliance_prom:.1f} / 100"),
        ("Dias de elite (score >= 80%)",        f"{dias_elite} de {len(registros)}"),
        ("Dias con protocolo de descanso",      f"{dias_con_descanso} de {len(registros)}"),
    ]
    for label, valor in metricas:
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(120, 8, label, border=0, fill=True)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(70, 8, valor, border=0, fill=True, ln=True)
        pdf.set_font("Helvetica", "", 11)
    pdf.ln(6)

    # ── Tabla diaria ──────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 8, "Detalle Diario", ln=True)
    pdf.ln(2)

    # Encabezados tabla
    headers = ["Fecha", "Pasos", "Min.", "Lastre M.", "Lastre T.", "Desc.", "Score"]
    widths  = [30,       28,      18,     24,          24,          18,      28]
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
        valores = [
            r["fecha"],
            f"{r['pasos']:,}",
            str(r["minutos_ejercicio"]),
            f"{r['lastre_munecas_lb']} lb",
            f"{r['lastre_tobillos_lb']} lb",
            "Si" if r["protocol_rest"] else "No",
            f"{score:.0f}%",
        ]
        for val, w in zip(valores, widths):
            pdf.cell(w, 6, val, border=1, fill=fill, align="C")
        pdf.ln()

    pdf.ln(8)

    # ── Nota clínica de descargo ──────────────────────────────────────────────
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(
        0, 5,
        "DESCARGO: Fit Engine es una herramienta de acompanamiento de habitos, actividad "
        "y estilo de vida. No proporciona diagnosticos medicos, no prescribe tratamientos "
        "farmacologicos ni reemplaza la evaluacion de un profesional de la salud colegiado.",
    )

    # Retornar bytes
    return bytes(pdf.output())
