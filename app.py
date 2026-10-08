import streamlit as st
import requests
import json
from audio_recorder_streamlit import audio_recorder

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Fit Engine Coach", layout="centered")

st.title("🍏 Fit Engine Coach")

voz_seleccionada = st.sidebar.radio(
    "🎙️ Voz del Coach",
    options=["Dalia (Femenina)", "Jorge (Masculino)"],
    index=0
)
st.session_state.voz_id = "dalia" if "Dalia" in voz_seleccionada else "jorge"

# Inicializar estado
if "nombre" not in st.session_state:
    st.session_state.nombre = "amigo"
if "historial" not in st.session_state:
    welcome_msg = "¡Hola! Bienvenido. Estoy aquí para acompañarte a ganar un día a la vez. Para empezar a conocernos, ¿cuál es tu nombre y cómo prefieres que te llame?"
    st.session_state.historial = [{"role": "model", "content": welcome_msg}]
    try:
        tts_resp = requests.post(f"{BACKEND_URL}/api/voz/tts", json={"texto": welcome_msg, "voz": st.session_state.voz_id})
        if tts_resp.status_code == 200:
            st.session_state.initial_audio = tts_resp.content
    except Exception:
        st.session_state.initial_audio = None
        
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None
    
if "played_initial_audio" not in st.session_state:
    st.session_state.played_initial_audio = False

def procesar_respuesta(bot_reply):
    st.session_state.historial.append({"role": "model", "content": bot_reply})
    with st.chat_message("assistant"):
        st.write(bot_reply)
        # Generar y reproducir TTS
        try:
            tts_resp = requests.post(f"{BACKEND_URL}/api/voz/tts", json={"texto": bot_reply, "voz": st.session_state.voz_id})
            if tts_resp.status_code == 200:
                st.audio(tts_resp.content, format="audio/mpeg", autoplay=True)
        except Exception as e:
            st.error("Error reproduciendo voz.")

tab1, tab2 = st.tabs(["Entrevista", "Visión (Escáner de Comida)"])

with tab1:
    st.header("Entrevista Nutricional")
    
    # Mostrar historial
    for i, msg in enumerate(st.session_state.historial):
        role = "Usuario" if msg["role"] == "user" else "Coach"
        with st.chat_message("user" if role == "Usuario" else "assistant"):
            st.write(msg["content"])
            
            # Mostrar audio inicial si existe
            if i == 0 and role == "Coach" and st.session_state.get("initial_audio"):
                if not st.session_state.played_initial_audio:
                    st.audio(st.session_state.initial_audio, format="audio/mpeg", autoplay=True)
                    st.session_state.played_initial_audio = True
                else:
                    st.audio(st.session_state.initial_audio, format="audio/mpeg")
            
    # Entrada de audio
    col1, col2 = st.columns([0.8, 0.2])
    with col2:
        audio_bytes = audio_recorder(text="Voz", icon_size="2x", key="audio_mic")
        
    # Procesar entrada de texto
    if prompt := st.chat_input("Escribe tu mensaje aquí..."):
        st.session_state.historial.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
            
        # Llamar al backend
        try:
            resp = requests.post(f"{BACKEND_URL}/api/entrevista/chat", json={
                "historial": st.session_state.historial[:-1],
                "mensaje": prompt
            })
            if resp.status_code == 200:
                data = resp.json()
                bot_reply = data.get("respuesta", "")
                procesar_respuesta(bot_reply)
            else:
                st.error("Error en la respuesta del backend.")
        except Exception as e:
            st.error(f"Error conectando al backend: {e}")
            
    # Procesar entrada de audio
    if audio_bytes and audio_bytes != st.session_state.last_audio:
        st.session_state.last_audio = audio_bytes
        try:
            with st.spinner("Escuchando..."):
                files = {"file": ("audio.wav", audio_bytes, "audio/wav")}
                data = {
                    "historial": json.dumps(st.session_state.historial),
                    "voz": st.session_state.voz_id
                }
                
                resp = requests.post(f"{BACKEND_URL}/api/entrevista/voz", files=files, data=data)
                
                if resp.status_code == 200:
                    resultado = resp.json()
                    transcripcion = resultado.get("transcripcion_usuario", "")
                    
                    st.session_state.historial.append({"role": "user", "content": transcripcion})
                    # Mostrar la transcripción
                    with st.chat_message("user"):
                        st.write(f"🎤 *{transcripcion}*")
                        
                    bot_reply = resultado.get("respuesta", "")
                    procesar_respuesta(bot_reply)
                    
                    # Forzar recarga para mostrar el chat ordenado
                    st.rerun()
                else:
                    st.error("Error procesando el audio.")
        except Exception as e:
            st.error(f"Error enviando audio: {e}")
            
    if st.button("Finalizar y Extraer Perfil"):
        with st.spinner("Extrayendo perfil..."):
            try:
                resp = requests.post(f"{BACKEND_URL}/api/entrevista/finalizar", json={
                    "historial": st.session_state.historial
                })
                if resp.status_code == 200:
                    data = resp.json()
                    perfil = data.get("perfil", {})
                    # Actualizar nombre en session state
                    st.session_state.nombre = perfil.get("nombre", "amigo")
                    
                    st.success(f"¡Bienvenido al camino, {st.session_state.nombre}! Vamos a ganar un día a la vez.")
                    st.json(data)
                else:
                    st.error("Error al extraer el perfil.")
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.header("Escáner de Comida")
    uploaded_file = st.file_uploader("Sube una foto de tu plato", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        st.image(uploaded_file, caption="Plato a analizar")
        
        if st.button("Analizar Plato"):
            with st.spinner("Analizando con Gemini Vision..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                    data = {"nombre": st.session_state.nombre}
                    
                    resp = requests.post(f"{BACKEND_URL}/api/comidas/analizar-foto", files=files, data=data)
                    
                    if resp.status_code == 200:
                        analisis = resp.json()
                        
                        # Mostrar el mensaje del coach destacado
                        st.info(f"**Mensaje del Coach:**\n\n{analisis.get('mensaje_coach', '')}")
                        
                        st.write("### Desglose Nutricional")
                        st.write(f"**Calorías Totales:** {analisis.get('calorias_totales')} kcal")
                        st.json(analisis.get("ingredientes", []))
                    else:
                        st.error("Error en el análisis de la imagen.")
                except Exception as e:
                    st.error(f"Error conectando al backend: {e}")
