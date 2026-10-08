import streamlit as st
import asyncio
import os
import json
import dotenv
from google import genai
from google.genai import types
from audio_recorder_streamlit import audio_recorder

import interview_service
import vision_service
import voice_service
import metabolic_engine

# Cargar variables de entorno
dotenv.load_dotenv()

# Sincronizar st.secrets con os.environ si existen
try:
    for key, value in st.secrets.items():
        os.environ[key] = str(value)
except Exception:
    pass

st.set_page_config(page_title="Fit Engine Coach", layout="centered")

st.title("🍏 Fit Engine Coach")

voz_seleccionada = st.sidebar.radio(
    "🎙️ Voz del Coach",
    options=["Dalia (Femenina)", "Jorge (Masculino)"],
    index=0
)
st.session_state.voz_id = "dalia" if "Dalia" in voz_seleccionada else "jorge"

st.sidebar.markdown("---")
st.sidebar.caption("⚖️ **Descargo Médico:** Fit Engine es una guía de hábitos y estilo de vida. No constituye diagnóstico ni tratamiento médico.")

# Inicializar estado
if "nombre" not in st.session_state:
    st.session_state.nombre = "amigo"

if "historial" not in st.session_state:
    welcome_msg = "¡Hola! Bienvenido. Estoy aquí para acompañarte a ganar un día a la vez. Para empezar a conocernos, ¿cuál es tu nombre y cómo prefieres que te llame?"
    try:
        audio_bytes = asyncio.run(voice_service.sintetizar_voz(welcome_msg, voz_id=st.session_state.voz_id))
    except Exception:
        audio_bytes = None
    st.session_state.historial = [{"role": "model", "content": welcome_msg, "audio": audio_bytes}]
        
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None
    
if "played_initial_audio" not in st.session_state:
    st.session_state.played_initial_audio = False

def procesar_respuesta(bot_reply):
    try:
        audio_bytes = asyncio.run(voice_service.sintetizar_voz(bot_reply, voz_id=st.session_state.voz_id))
    except Exception as e:
        st.error("Error reproduciendo voz.")
        audio_bytes = None
        
    st.session_state.historial.append({"role": "model", "content": bot_reply, "audio": audio_bytes})
    
    with st.chat_message("assistant"):
        st.write(bot_reply)
        if audio_bytes:
            st.audio(audio_bytes, format="audio/mpeg", autoplay=True)

tab_chat, tab_actividad = st.tabs(["💬 Coach & Visión", "👟 Mi Actividad"])

with tab_chat:
    st.header("Entrevista Nutricional")
    
    # Mostrar historial
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
            
    # Entrada de audio
    col1, col2 = st.columns([0.8, 0.2])
    with col2:
        audio_bytes = audio_recorder(text="Voz", icon_size="2x", key="audio_mic")
        
    # Procesar entrada de texto
    if prompt := st.chat_input("Escribe tu mensaje aquí..."):
        st.session_state.historial.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
            
        try:
            resultado = interview_service.continuar_entrevista(st.session_state.historial[:-1], prompt)
            bot_reply = resultado.get("respuesta", "")
            procesar_respuesta(bot_reply)
        except Exception as e:
            st.error(f"Error procesando chat: {e}")
            
    # Procesar entrada de audio
    if audio_bytes and audio_bytes != st.session_state.last_audio:
        st.session_state.last_audio = audio_bytes
        try:
            with st.spinner("Escuchando..."):
                # Transcribir con Gemini 2.5 Flash directamente
                client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                        "Transcribe de manera exacta lo que dice este audio en español, sin agregar ningún otro comentario ni formato markdown. Si está vacío o no se entiende, responde '[ININTELIGIBLE]'."
                    ]
                )
                transcripcion = response.text.strip()
                
                st.session_state.historial.append({"role": "user", "content": transcripcion})
                
                with st.chat_message("user"):
                    st.write(f"🎤 *{transcripcion}*")
                    
                resultado = interview_service.continuar_entrevista(st.session_state.historial[:-1], transcripcion)
                bot_reply = resultado.get("respuesta", "")
                procesar_respuesta(bot_reply)
                
                st.rerun()
        except Exception as e:
            st.error(f"Error procesando audio: {e}")
            
    if st.button("Finalizar y Extraer Perfil"):
        with st.spinner("Extrayendo perfil y calculando métricas..."):
            try:
                perfil = interview_service.extraer_perfil_desde_chat(st.session_state.historial)
                metricas = metabolic_engine.calcular_metricas(perfil)
                
                st.session_state.nombre = perfil.nombre
                
                st.success(f"¡Bienvenido al camino, {st.session_state.nombre}! Vamos a ganar un día a la vez.")
                st.json({
                    "perfil": perfil.model_dump(),
                    "metricas": metricas.model_dump()
                })
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()
    
    st.header("Escáner de Comida")
    uploaded_file = st.file_uploader("Sube una foto de tu plato", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Plato a analizar")
        
        if st.button("Analizar Plato"):
            with st.spinner("Analizando con Gemini Vision..."):
                try:
                    analisis = vision_service.analizar_imagen_comida(uploaded_file.getvalue(), nombre_usuario=st.session_state.nombre)
                    
                    st.info(f"**Mensaje del Coach:**\n\n{analisis.mensaje_coach}")
                    
                    st.write("### Desglose Nutricional")
                    st.write(f"**Calorías Totales:** {analisis.calorias_totales} kcal")
                    st.json([ing.model_dump() for ing in analisis.ingredientes])
                except Exception as e:
                    st.error(f"Error procesando imagen: {e}")

with tab_actividad:
    st.header("Registro de Actividad Física")
    
    with st.form("form_actividad"):
        fecha = st.date_input("Fecha")
        pasos = st.number_input("Pasos registrados en el día", min_value=0, step=500, value=0)
        mins_ejercicio = st.number_input("Minutos de ejercicio", min_value=0, step=15, value=0)
        tipo = st.text_input("Tipo de ejercicio", value="Caminata / Cardio")
        
        submitted = st.form_submit_button("Guardar Registro")
        
        if submitted:
            st.success(f"Se registraron {pasos} pasos y {mins_ejercicio} mins de {tipo} para el {fecha}.")
            st.info("¡Sigue así, construyendo tu identidad saludable, 1% mejor cada día!")
