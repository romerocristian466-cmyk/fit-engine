"""
Reglas clínicas basadas en directrices internacionales:
- Diabetes Mellitus: American Diabetes Association (ADA)
- Hipertensión Arterial: Dietary Approaches to Stop Hypertension (DASH / AHA)
"""

DIRECTRICES_CLINICAS = {
    "diabetes": {
        "fuente": "American Diabetes Association (ADA)",
        "principios": [
            "Priorizar carbohidratos complejos de bajo índice y baja carga glucémica.",
            "Restricción estricta de azúcares libres y refinados.",
            "Distribuir los carbohidratos de forma regular a lo largo del día para evitar picos posprandiales.",
            "Alertar sobre el riesgo de hipoglucemia si se realiza ejercicio en ayunas bajo tratamiento farmacológico."
        ]
    },
    "hipertension": {
        "fuente": "Dieta DASH / American Heart Association (AHA)",
        "principios": [
            "Límite de sodio estricto (< 2,000 mg diarios).",
            "Priorizar alimentos ricos en potasio, magnesio y calcio.",
            "Evitar alimentos ultraprocesados, conservas y embutidos con exceso de sodio.",
            "Promover actividad aeróbica regular de intensidad moderada."
        ]
    }
}

DESCARGO_MEDICO = (
    "Fit Engine es una herramienta de acompañamiento de hábitos, actividad y estilo de vida. "
    "No proporciona diagnósticos médicos, no prescribe tratamientos farmacológicos ni reemplaza "
    "la evaluación de un profesional de la salud colegiado."
)

def obtener_contexto_clinico(condiciones: list[str]) -> str:
    """Devuelve las directrices a inyectar en los prompts del LLM según el perfil."""
    reglas = []
    for cond in condiciones:
        c = cond.lower()
        if "diabet" in c:
            reglas.append(f"Directrices ADA (Diabetes): {'; '.join(DIRECTRICES_CLINICAS['diabetes']['principios'])}")
        if "hipertens" in c or "presion" in c:
            reglas.append(f"Directrices DASH (Hipertensión): {'; '.join(DIRECTRICES_CLINICAS['hipertension']['principios'])}")
    return "\n".join(reglas) if reglas else "Pautas generales de estilo de vida saludable."
