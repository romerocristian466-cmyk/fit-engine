import io
import json
import dotenv
from PIL import Image, ImageDraw
import sys

# Cargar variables de entorno antes de importar modulos que inicializan clientes LLM
dotenv.load_dotenv()

from schemas import PerfilUsuario
import metabolic_engine
import planner_service
import vision_service

def test_backend_pipeline():
    print("--- INICIANDO TEST E2E DEL BACKEND FIT ENGINE ---")
    
    # 1. Crear Perfil Mock
    print("\n1. Creando Perfil Mock...")
    perfil_mock = PerfilUsuario(
        edad=30,
        sexo="M",
        peso_kg=85.0,
        altura_cm=180.0,
        nivel_actividad="moderado",
        objetivo="perder_grasa",
        comidas_por_dia=4,
        alergias_restricciones="Intolerancia a la lactosa"
    )
    print(f"Perfil: {perfil_mock.model_dump_json(indent=2)}")
    
    # 2. Calcular Métricas Metabólicas
    print("\n2. Calculando Métricas Metabólicas (Motor Interno)...")
    try:
        metricas = metabolic_engine.calcular_metricas(perfil_mock)
        print(f"Métricas: {metricas.model_dump_json(indent=2)}")
    except Exception as e:
        print(f"[ERROR] Motor metabólico falló: {e}")
        sys.exit(1)
        
    # 3. Generar Plan Semanal (Gemini Structured Outputs)
    print("\n3. Generando Plan Semanal con IA...")
    try:
        plan = planner_service.generar_plan_semanal(perfil_mock, metricas)
        print(f"Días generados: {len(plan.dias)}")
        for dia in plan.dias:
            print(f" - {dia.dia_semana}: {dia.calorias_totales} kcal, {dia.proteinas_totales}g P, {dia.grasas_totales}g G, {dia.carbohidratos_totales}g C | {len(dia.comidas)} comidas")
        print(f"Artículos en lista de compras: {len(plan.lista_compras)}")
    except Exception as e:
        print(f"[ERROR] Planner service falló: {e}")
        sys.exit(1)
        
    # 4. Análisis de Imagen (Multimodal Gemini)
    print("\n4. Probando Análisis de Imagen Multimodal...")
    try:
        # Generar una imagen de prueba programáticamente
        img = Image.new('RGB', (400, 400), color=(255, 200, 200))
        d = ImageDraw.Draw(img)
        d.text((10,10), "Pollo asado con arroz y broccoli", fill=(0,0,0))
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_bytes = img_byte_arr.getvalue()
        
        print("Enviando imagen a Gemini Vision...")
        analisis = vision_service.analizar_imagen_comida(img_bytes)
        print(f"Análisis Exitoso. Calorías totales estimadas: {analisis.calorias_totales} kcal")
        for ing in analisis.ingredientes:
            print(f" - {ing.nombre}: {ing.cantidad_g}g ({ing.calorias} kcal)")
            
    except Exception as e:
        print(f"[ERROR] Vision service falló: {e}")
        sys.exit(1)
        
    print("\n--- TEST E2E COMPLETADO CON ÉXITO ---")

if __name__ == "__main__":
    test_backend_pipeline()
