from llm_clients import ResilientChatClient
from schemas import PerfilUsuario, MetricasMetabolicas, PlanSemanal
import protocolos_clinicos

client = ResilientChatClient()

def generar_plan_semanal(perfil: PerfilUsuario, metricas: MetricasMetabolicas) -> PlanSemanal:
    """
    Genera un plan semanal estructurado (Lunes a Domingo) utilizando Gemini 2.5 Flash.
    """
    
    contexto_clinico = protocolos_clinicos.obtener_contexto_clinico(perfil.condiciones_medicas)
    
    system_prompt = f"""
    Eres un planificador nutricional experto. Tu tarea es generar un menú semanal completo (Lunes a Domingo) estrictamente basado en las siguientes métricas y restricciones.

    MÉTRICAS OBJETIVO DIARIAS:
    - Calorías: {metricas.calorias_objetivo} kcal (Margen de error máximo: ±50 kcal por día)
    - Proteínas: {metricas.proteinas_g} g
    - Grasas: {metricas.grasas_g} g
    - Carbohidratos: {metricas.carbohidratos_g} g
    
    PERFIL DEL USUARIO:
    - Objetivo: {perfil.objetivo}
    - Número de comidas al día: {perfil.comidas_por_dia}
    - Restricciones/Alergias: {perfil.alergias_restricciones or 'Ninguna'}
    - Condiciones Médicas: {', '.join(perfil.condiciones_medicas) if perfil.condiciones_medicas else 'Ninguna'}
    
    DIRECTRICES CLÍNICAS A APLICAR:
    {contexto_clinico}
    
    REGLAS ESTRICTAS:
    1. Debes generar exactamente un menú para los 7 días de la semana.
    2. Cada día debe sumar los totales calóricos y de macronutrientes solicitados.
    3. Distribuye de manera lógica las comidas del día.
    4. Proporciona una lista de compras consolidada de todos los ingredientes necesarios para la semana.
    """
    
    mensaje = [{"role": "user", "content": "Genera el plan semanal completo y la lista de compras basado en mi perfil y métricas."}]
    
    plan = client.structured_completion(
        messages=mensaje,
        response_schema=PlanSemanal,
        system_prompt=system_prompt
    )
    
    return plan
