# 🍏 Fit Engine Coach

Coach de salud con IA para el control de peso y hábitos. Chatea con un coach (Gemini), analiza fotos de tu comida, registra tu actividad diaria con pesas de lastre y genera un reporte semanal en PDF.

> ⚠️ **Descargo médico:** Fit Engine es una guía de hábitos y estilo de vida. No constituye diagnóstico ni tratamiento médico ni reemplaza a un profesional de la salud. Las calorías son estimaciones.

## Qué hace (las 4 pestañas)

| Pestaña | Para qué sirve |
|---|---|
| 💬 **Coach IA** | Chat de texto con un coach basado en "Solo por hoy" y Hábitos Atómicos. Incluye el **Escáner de Comida**: subes una foto del plato y Gemini estima ingredientes, gramos y calorías. |
| 👟 **Mi Actividad** | Registro diario de pasos, minutos de ejercicio, lastre (muñecas y tobillos) y protocolo de descanso. Calcula un *score de cumplimiento* (0-100) y activa el **Modo Recuperación** si pasas 2 días seguidos sin descansar. |
| 📊 **Dashboard** | Mapa de calor de cumplimiento, pasos diarios, gasto calórico estimado con lastre y racha de días consecutivos con score ≥ 80. |
| 📄 **Reporte Clínico** | Genera un PDF descargable con el resumen de tus últimos 7 días. |

En la barra lateral pones tu nombre, tu peso y tus pesas de lastre.

## Cómo correrla en tu computadora

Necesitas **Python 3.11 o superior** (probado con 3.13) y una llave de Gemini (gratis en [Google AI Studio](https://aistudio.google.com/apikey)).

```bash
# 1. Clonar el repositorio
git clone https://github.com/romerocristian466-cmyk/fit-engine.git
cd fit-engine

# 2. Crear un entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configurar tu llave de Gemini
cp .env.example .env            # En Windows: copy .env.example .env
# Abre .env y escribe tu llave en GEMINI_API_KEY=...

# 4. Arrancar la app
streamlit run app.py
```

Se abre en <http://localhost:8501>.

## Despliegue en Streamlit Cloud

1. Sube el repo a GitHub.
2. En [share.streamlit.io](https://share.streamlit.io) crea una app apuntando a `app.py`.
3. En **Settings → Secrets** agrega:
   ```toml
   GEMINI_API_KEY = "tu_llave_aqui"
   ```

## Privacidad y seguridad

- **Nunca subas tu llave al repositorio.** `.env` y `.streamlit/secrets.toml` están en `.gitignore`.
- Los registros se guardan en un archivo local `fit_engine.db` (también ignorado por git). **En Streamlit Cloud ese archivo se borra cuando la app se reinicia**, y todos los visitantes comparten la misma base de datos. Por ahora la app es apta para uso personal o pruebas, no para uso público con varios usuarios.

## Estructura

| Archivo | Función |
|---|---|
| `app.py` | Interfaz de Streamlit (las 4 pestañas) |
| `db.py` | Base de datos SQLite, zona horaria y cálculo de calorías con lastre |
| `vision_service.py` | Análisis de fotos de comida con Gemini |
| `metabolic_engine.py` | Cálculo de TMB, calorías y macros (Mifflin-St Jeor) |
| `schemas.py` | Modelos de datos (Pydantic) |

## Licencia

Pendiente de definir.
