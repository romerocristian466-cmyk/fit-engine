import os
import io
import json
from PIL import Image
from google import genai
from google.genai import types
from schemas import AnalisisComida

def analizar_imagen_comida(imagen_bytes: bytes, nombre_usuario: str = "amigo") -> AnalisisComida:
    """
    Analiza una imagen de comida, redimensiona si es necesario y extrae un desglose
    nutricional usando Gemini 2.5 Flash con salida estructurada.
    """
    # 1. Cargar y redimensionar la imagen si la dimensión mayor excede los 1280 px
    img = Image.open(io.BytesIO(imagen_bytes))
    
    max_dim = 1280
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim))
        
    # 2. Configurar cliente Gemini
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise Exception("GEMINI_API_KEY no configurada.")
        
    client = genai.Client(api_key=gemini_api_key)
    
    system_prompt = f"""
    Eres un analista experto en nutrición y visión artificial. 
    Analiza la fotografía del plato de comida proporcionada. 
    Realiza una estimación volumétrica, identifica cada ingrediente, estima los gramos 
    y haz asunciones lógicas sobre las grasas de cocción (ej. frito, al horno).
    
    Además, debes generar un `mensaje_coach` dirigiéndote al usuario como "{nombre_usuario}".
    - Si la comida es nutritiva/balanceada: Refuerza su identidad saludable ("Este plato es un voto por la persona que estás construyendo hoy, 1% mejor cada día").
    - Si la comida es calórica, rápida o procesada: Cero culpas ni reproches ("Disfruta tu comida; la meta es la consistencia, no la perfección. Solo por hoy, este fue un gusto; recuerda la regla de oro: nunca falles dos veces seguidas. En la siguiente comida retomamos el rumbo").
    - Haz que el texto se sienta auténtico, fresco y contextualizado a los ingredientes exactos del plato analizado.
    """
    
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=AnalisisComida,
        system_instruction=system_prompt,
        temperature=0.2
    )
    
    # 3. Llamada Multimodal a Gemini
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=["Analiza este plato de comida y proporciona el desglose nutricional detallado.", img],
        config=config,
    )
    
    # 4. Parsear y retornar el modelo
    data = json.loads(response.text)
    return AnalisisComida.model_validate(data)
