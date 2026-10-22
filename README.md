# Fit Engine Coach 🍏

Fit Engine Coach es una aplicación de salud y bienestar con IA basada en texto. Te ayuda a mejorar tus hábitos, registrar tu actividad física y analizar tus comidas mediante un coach conversacional y un panel de seguimiento personal.

## ¿Qué hace la app?
La aplicación proporciona un acompañamiento personalizado mediante IA, donde un "Coach" empático te orienta en temas de nutrición y ejercicio físico. También te permite llevar un registro de pasos, estimar el gasto calórico utilizando pesas de muñecas y tobillos, y verificar el cumplimiento de tus hábitos diarios, manteniendo rachas de días consecutivos.

## Cómo correrla localmente

1. **Instalar las dependencias:**
   Ejecuta el siguiente comando para instalar las librerías necesarias:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar las variables de entorno:**
   Crea un archivo llamado `.env` en la raíz del proyecto y añade tu API key de Gemini:
   ```env
   GEMINI_API_KEY=tu_api_key_aqui
   ```

3. **Iniciar la aplicación:**
   Ejecuta Streamlit:
   ```bash
   streamlit run app.py
   ```

## Las 4 pestañas de la aplicación

- **💬 Coach IA:** Conversa con el coach para recibir orientación personalizada. Incluye un escáner de comida que utiliza Gemini Vision para analizar las fotos de tus platos y darte un desglose nutricional.
- **👟 Mi Actividad:** Registra diariamente tus pasos, minutos de ejercicio y uso de lastres (muñecas/tobillos). También evalúa tu protocolo de descanso.
- **📊 Dashboard:** Muestra un panel interactivo con tu progreso, visualizando el mapa de calor de tu cumplimiento diario, tu racha actual y tu gasto calórico estimado.
- **📄 Reporte Clínico:** Genera y descarga un reporte en PDF que resume tu actividad y cumplimiento de la última semana.
