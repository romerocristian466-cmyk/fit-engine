from schemas import PerfilUsuario, MetricasMetabolicas

def calcular_metricas(perfil: PerfilUsuario) -> MetricasMetabolicas:
    """
    Calcula la TMB, calorías objetivo y distribución de macronutrientes 
    basado en la ecuación de Mifflin-St Jeor y el objetivo del usuario.
    Ningún cálculo aritmético de calorías o macros debe ser resuelto por un prompt.
    """
    # 1. Calcular TMB (Mifflin-St Jeor)
    if perfil.sexo == "M":
        tmb = (10 * perfil.peso_kg) + (6.25 * perfil.altura_cm) - (5 * perfil.edad) + 5
    else:
        tmb = (10 * perfil.peso_kg) + (6.25 * perfil.altura_cm) - (5 * perfil.edad) - 161
        
    # 2. Multiplicador de Actividad
    multiplicadores = {
        "sedentario": 1.2,
        "ligero": 1.375,
        "moderado": 1.55,
        "activo": 1.725,
        "muy_activo": 1.9
    }
    tdee = tmb * multiplicadores.get(perfil.nivel_actividad, 1.2)
    
    # 3. Calcular Calorías Objetivo y Proteína (g/kg)
    calorias_objetivo = tdee
    proteina_g_kg = 1.6
    
    if perfil.objetivo == "perder_grasa":
        calorias_objetivo = tdee - 500
        # Piso calórico mínimo
        piso = 1500 if perfil.sexo == "M" else 1200
        calorias_objetivo = max(calorias_objetivo, piso)
        proteina_g_kg = 2.0
    elif perfil.objetivo == "ganar_musculo":
        calorias_objetivo = tdee + 350
        proteina_g_kg = 1.8
    elif perfil.objetivo == "mantener":
        calorias_objetivo = tdee
        proteina_g_kg = 1.6
        
    # 4. Distribución de Macronutrientes
    # Proteínas (4 kcal por gramo)
    proteinas_g = perfil.peso_kg * proteina_g_kg
    calorias_proteinas = proteinas_g * 4.0
    
    # Grasas (25% de calorías objetivo, 9 kcal por gramo)
    calorias_grasas = calorias_objetivo * 0.25
    grasas_g = calorias_grasas / 9.0
    
    # Carbohidratos (El remanente calórico, 4 kcal por gramo)
    calorias_carbohidratos = calorias_objetivo - (calorias_proteinas + calorias_grasas)
    # Evitar carbohidratos negativos si el peso es muy alto y el piso calórico se activa
    calorias_carbohidratos = max(calorias_carbohidratos, 0)
    carbohidratos_g = calorias_carbohidratos / 4.0
    
    # Ajustar objetivo si los carbohidratos dieron 0 (poco común, pero por seguridad)
    calorias_objetivo_reales = calorias_proteinas + calorias_grasas + (carbohidratos_g * 4.0)
    
    return MetricasMetabolicas(
        tmb=round(tmb, 2),
        calorias_objetivo=round(calorias_objetivo_reales, 2),
        proteinas_g=round(proteinas_g, 2),
        grasas_g=round(grasas_g, 2),
        carbohidratos_g=round(carbohidratos_g, 2)
    )
