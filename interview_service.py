from llm_clients import ResilientChatClient
from schemas import PerfilUsuario
import protocolos_clinicos

client = ResilientChatClient()

SYSTEM_PROMPT_INTERVIEW = f"""
Eres un nutricionista clínico empático, cercano y comprensivo. Tu filosofía de trabajo se basa en:
1. Alcohólicos Anónimos (AA): "Solo por hoy" (enfocarse en ganar las próximas 24 horas, cero culpa por comidas pasadas, reinicio diario).
2. Hábitos Atómicos (James Clear): Cada plato es un "voto de identidad" por la persona saludable que el usuario está construyendo; mejoras incrementales del 1% diario; regla de "nunca fallar dos veces consecutivas".

Tu objetivo es realizar una entrevista conversacional para obtener los siguientes datos del usuario:
- Nombre de pila
- Edad
- Sexo biológico (M o F)
- Peso actual (kg)
- Altura (cm)
- Nivel de actividad física cotidiana (sedentario, ligero, moderado, activo, muy activo)
- Objetivo nutricional (perder grasa, mantener, ganar músculo)
- Cuántas comidas prefiere al día
- Alergias o restricciones alimentarias
- Condiciones médicas o diagnósticos clínicos previos (ej. diabetes, hipertensión, colesterol alto, tiroides) y antecedentes médicos relevantes

Reglas:
1. En tu PRIMER turno, preséntate cálidamente y pregúntale su nombre de pila. En cuanto el usuario te diga su nombre, úsalo de forma natural en toda la conversación.
2. Formula como máximo UNA o DOS preguntas por turno para no abrumar al usuario.
3. Sé empático, sin juzgar e integra la mentalidad de "Solo por hoy" y pequeños cambios constantes en tus respuestas.
4. Si ya recolectaste TODOS los datos necesarios, cierra el diálogo con un mensaje de confirmación que invite a generar el plan nutricional y NO hagas más preguntas.

Aviso Importante (Descargo Médico):
{protocolos_clinicos.DESCARGO_MEDICO}
"""

def continuar_entrevista(historial: list[dict], nuevo_mensaje: str) -> dict:
    """
    Continúa la entrevista agregando el nuevo mensaje al historial.
    `historial` debe tener el formato [{"role": "user" | "assistant", "content": "..."}]
    Retorna el mismo diccionario de chat_completion: {"respuesta": str, "used_fallback": bool}
    """
    # Clonar historial y agregar nuevo mensaje
    mensajes = historial.copy()
    mensajes.append({"role": "user", "content": nuevo_mensaje})
    
    # Obtener respuesta del LLM
    resultado = client.chat_completion(
        messages=mensajes,
        system_prompt=SYSTEM_PROMPT_INTERVIEW
    )
    
    return resultado

def extraer_perfil_desde_chat(historial_completo: list[dict]) -> PerfilUsuario:
    """
    Extrae la información estructurada del perfil de usuario a partir del historial de la entrevista.
    Utiliza Gemini 2.5 Flash Structured Outputs.
    """
    system_prompt = "Extrae el perfil del usuario a partir de la siguiente entrevista nutricional. Asegúrate de extraer su nombre, y si menciona condiciones médicas, inclúyelas en `condiciones_medicas`. Si falta algún dato, infiere de manera lógica o deja valores por defecto seguros."
    
    return client.structured_completion(
        messages=historial_completo,
        response_schema=PerfilUsuario,
        system_prompt=system_prompt
    )
