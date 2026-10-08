from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import date

class RegistroActividad(BaseModel):
    fecha: date
    pasos: int = Field(ge=0, description="Pasos registrados en el día")
    minutos_ejercicio: int = Field(default=0, ge=0, description="Minutos de entrenamiento o caminata activa")
    tipo_ejercicio: Optional[str] = "Caminata / Cardio"

class PerfilUsuario(BaseModel):
    nombre: str = Field(..., description="Nombre de pila del usuario o cómo prefiere que le llamen")
    edad: int = Field(..., description="Edad del usuario en años")
    sexo: Literal["M", "F"] = Field(..., description="Sexo biológico del usuario (M para masculino, F para femenino)")
    peso_kg: float = Field(..., description="Peso actual en kilogramos")
    altura_cm: float = Field(..., description="Altura en centímetros")
    nivel_actividad: Literal["sedentario", "ligero", "moderado", "activo", "muy_activo"] = Field(..., description="Nivel de actividad física cotidiana")
    objetivo: Literal["perder_grasa", "mantener", "ganar_musculo"] = Field(..., description="Objetivo nutricional del usuario")
    comidas_por_dia: int = Field(..., description="Número de comidas que prefiere hacer al día")
    alergias_restricciones: Optional[str] = Field(None, description="Alergias o restricciones alimentarias (ej. vegano, sin gluten, alergia al maní)")
    condiciones_medicas: list[str] = Field(default_factory=list, description="Condiciones como diabetes, hipertensión, etc.")
    meta_pasos_diarios: int = Field(default=8000, description="Meta de pasos diarios")
    historial_actividad: List[RegistroActividad] = Field(default_factory=list, description="Registro histórico de actividad física")

class MetricasMetabolicas(BaseModel):
    tmb: float = Field(..., description="Tasa Metabólica Basal en kcal")
    calorias_objetivo: float = Field(..., description="Calorías objetivo diarias según el propósito")
    proteinas_g: float = Field(..., description="Gramos de proteína diarios recomendados")
    grasas_g: float = Field(..., description="Gramos de grasas diarios recomendados")
    carbohidratos_g: float = Field(..., description="Gramos de carbohidratos diarios recomendados")

class IngredienteAnalizado(BaseModel):
    nombre: str
    cantidad_g: float
    calorias: float
    proteinas_g: float
    grasas_g: float
    carbohidratos_g: float
    asunciones_coccion: Optional[str] = Field(None, description="Asunciones hechas sobre cómo fue cocinado (ej. frito en aceite, asado)")

class AnalisisComida(BaseModel):
    ingredientes: List[IngredienteAnalizado]
    calorias_totales: float
    proteinas_totales: float
    grasas_totales: float
    carbohidratos_totales: float
    mensaje_coach: str = Field(..., description="Mensaje motivacional y empático en tiempo real adaptado al plato, llamando al usuario por su nombre y aplicando la filosofía de 'Solo por hoy' y 'Hábitos Atómicos'.")

class IngredienteMenu(BaseModel):
    nombre: str
    cantidad_g: float

class Comida(BaseModel):
    tipo: str = Field(..., description="Tipo de comida (ej. Desayuno, Almuerzo, Cena, Snack)")
    nombre: str
    descripcion: str
    ingredientes: List[IngredienteMenu]
    calorias: float
    proteinas_g: float
    grasas_g: float
    carbohidratos_g: float

class DiaPlan(BaseModel):
    dia_semana: Literal["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    comidas: List[Comida]
    calorias_totales: float
    proteinas_totales: float
    grasas_totales: float
    carbohidratos_totales: float

class ArticuloCompra(BaseModel):
    nombre: str
    cantidad_total: float
    unidad: str = Field(..., description="Unidad de medida (ej. gramos, unidades, litros)")

class PlanSemanal(BaseModel):
    dias: List[DiaPlan]
    lista_compras: List[ArticuloCompra]
