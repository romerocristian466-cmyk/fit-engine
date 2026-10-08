from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Response
import json
from google import genai
from google.genai import types
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import dotenv

# Cargar variables de entorno
dotenv.load_dotenv()

from schemas import PerfilUsuario, MetricasMetabolicas, PlanSemanal, AnalisisComida
import interview_service
import metabolic_engine
import planner_service
import vision_service
import voice_service

app = FastAPI(title="Fit Engine API", description="Backend para Asistente de Nutrición Inteligente")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    historial: List[Dict[str, Any]]
    mensaje: str

class FinalizarRequest(BaseModel):
    historial: List[Dict[str, Any]]

class PlanRequest(BaseModel):
    perfil: PerfilUsuario
    metricas: MetricasMetabolicas

class TTSRequest(BaseModel):
    texto: str
    voz: str = "dalia"

@app.post("/api/entrevista/chat")
async def entrevista_chat(req: ChatRequest):
    try:
        resultado = interview_service.continuar_entrevista(req.historial, req.mensaje)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/entrevista/finalizar")
async def entrevista_finalizar(req: FinalizarRequest):
    try:
        # Extraer el perfil estructurado usando LLM
        perfil = interview_service.extraer_perfil_desde_chat(req.historial)
        
        # Calcular las métricas basadas en las reglas de negocio puras
        metricas = metabolic_engine.calcular_metricas(perfil)
        
        return {
            "perfil": perfil.model_dump(),
            "metricas": metricas.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/plan/generar", response_model=PlanSemanal)
async def generar_plan(req: PlanRequest):
    try:
        plan = planner_service.generar_plan_semanal(req.perfil, req.metricas)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/comidas/analizar-foto", response_model=AnalisisComida)
async def analizar_foto(nombre: str = Form(default="amigo"), file: UploadFile = File(...)):
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Archivo vacío.")
            
        analisis = vision_service.analizar_imagen_comida(contents, nombre_usuario=nombre)
        return analisis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voz/tts")
async def tts(req: TTSRequest):
    try:
        audio_bytes = await voice_service.sintetizar_voz(req.texto, voz_id=req.voz)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/entrevista/voz")
async def entrevista_voz(historial: str = Form(...), voz: str = Form(default="dalia"), file: UploadFile = File(...)):
    try:
        historial_list = json.loads(historial)
        audio_bytes = await file.read()
        
        # Transcribir con Gemini 2.5 Flash
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        mime_type = file.content_type if file.content_type else "audio/wav"
        
        # Streamlit audio_recorder a veces envía audio/wav
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                "Transcribe de manera exacta lo que dice este audio en español, sin agregar ningún otro comentario ni formato markdown. Si está vacío o no se entiende, responde '[ININTELIGIBLE]'."
            ]
        )
        transcripcion = response.text.strip()
        
        # Interactuar con la entrevista
        resultado = interview_service.continuar_entrevista(historial_list, transcripcion)
        resultado["transcripcion_usuario"] = transcripcion
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
