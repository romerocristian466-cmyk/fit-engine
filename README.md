# 🍏 Fit Engine Coach

Coach de salud con IA para el control de peso y hábitos. Chatea con un coach (Gemini), analiza fotos de tu comida, registra tu actividad diaria con pesas de lastre y genera un reporte semanal en PDF.

> ⚠️ **Descargo médico:** Fit Engine es una guía de hábitos y estilo de vida. No constituye diagnóstico ni tratamiento médico ni reemplaza a un profesional de la salud. Las calorías son estimaciones.

## Qué hace (las 4 pestañas)

| Pestaña | Para qué sirve |
|---|---|
| 💬 **Coach IA** | Chat de texto con un coach basado en "Solo por hoy" y Hábitos Atómicos. Incluye el **Escáner de Comida**: subes una foto del plato y Gemini estima ingredientes, gramos y calorías. |
| 👟 **Mi Actividad** | Registro diario de pasos, minutos de ejercicio, lastre (muñecas y tobillos) y protocolo de descanso. Calcula un *score de cumplimiento* (0-100) y activa el **Modo Recuperación** si pasas 2 días seguidos sin descansar. También registras tu **peso corporal**. |
| 📊 **Dashboard** | Mapa de calor de cumplimiento, pasos diarios, gasto calórico estimado con lastre, racha de días consecutivos con score ≥ 80 y **gráfica de peso con línea de tendencia y meta**. |
| 📄 **Reporte Clínico** | Genera un PDF descargable con el resumen de tus últimos 7 días. |

En la barra lateral pones tu nombre, tu peso (por defecto, el último que registraste), tu meta de peso y tus pesas de lastre.

## Dos modos de uso

| Modo | Para qué | Datos | Login |
|---|---|---|---|
| **Nube** (por defecto) | App publicada para varias personas | Supabase (Postgres), separados por usuario | Sí (correo y contraseña) |
| **Local** (`FIT_ENGINE_MODO_LOCAL=1`) | Desarrollar y probar en tu computadora | Archivo SQLite `fit_engine.db` | No |

Sin `FIT_ENGINE_MODO_LOCAL=1`, la app **exige** Supabase y login: nunca cae por accidente en una base de datos compartida entre todos los visitantes.

## Cómo correrla en tu computadora (modo local)

Necesitas **Python 3.11 o superior** (probado con 3.13) y una llave de Gemini (gratis en [Google AI Studio](https://aistudio.google.com/apikey)).

```bash
# 1. Clonar el repositorio
git clone https://github.com/romerocristian466-cmyk/fit-engine.git
cd fit-engine

# 2. Crear un entorno virtual e instalar dependencias
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configurar tu llave de Gemini y activar el modo local
cp .env.example .env            # En Windows: copy .env.example .env
# Abre .env, escribe tu llave en GEMINI_API_KEY=... y descomenta FIT_ENGINE_MODO_LOCAL=1

# 4. Arrancar la app
streamlit run app.py
```

Se abre en <http://localhost:8501>.

## Despliegue en Streamlit Cloud (modo nube con Supabase)

**1. Crea el proyecto en Supabase** ([supabase.com](https://supabase.com)).
   Al crearlo deja marcado *Enable Data API*, y marca *Enable automatic RLS*.

**2. Crea las tablas.** En Supabase → **SQL Editor → New query**, pega todo el contenido de [`supabase_schema.sql`](supabase_schema.sql) y pulsa **Run**. Se puede correr más de una vez sin borrar datos.

**3. Configura el acceso.** En **Authentication → Sign In / Providers → Email**:
   - Para una beta, desactiva **Confirm email** (no necesitas servidor de correo).
   - Para uso público, déjalo activado y configura un servidor SMTP propio: el correo que trae Supabase de fábrica solo envía a miembros de tu equipo y con un límite muy bajo ([documentación](https://supabase.com/docs/guides/auth/auth-smtp)).

**4. Copia tus llaves.** En **Project Settings → API Keys** copia la **Project URL** y la llave **pública** (*anon* o *publishable*).
   ⚠️ **Nunca uses ni compartas la llave `secret` / `service_role`.** Esa llave se salta toda la seguridad.

**5. Crea la app en [share.streamlit.io](https://share.streamlit.io)** apuntando a `app.py` y, en **Settings → Secrets**, agrega:
   ```toml
   GEMINI_API_KEY = "tu_llave_de_gemini"
   SUPABASE_URL   = "https://tu-proyecto.supabase.co"
   SUPABASE_KEY   = "tu_llave_publica"
   ```

**Actualizar una base que ya tenías:** si ya habías corrido `supabase_schema.sql` antes, vuelve a pegarlo y ejecutarlo completo (es seguro, no borra datos). Agrega el límite diario de IA.

Notas:
- **Límite diario de IA por usuario:** 30 mensajes al coach y 5 fotos analizadas al día (hora de El Salvador). Para cambiarlo, edita los números en la función `consumir_cuota` de `supabase_schema.sql` (y `LIMITES_DIARIOS` en `db.py` para el modo local) y vuelve a ejecutar el SQL.
- El plan gratis de Supabase puede **pausar** proyectos con poca actividad durante 7 días; se reactivan desde su panel.
- **La sesión sobrevive a recargar la página** (14 días): el navegador guarda una cookie con el token de renovación de Supabase (nunca la contraseña). Al cerrar sesión se borra y el token se revoca en todos tus dispositivos. Ver `sesion_cookie.py`.

## Privacidad y seguridad

- **Nunca subas tus llaves al repositorio.** `.env` y `.streamlit/secrets.toml` están en `.gitignore`.
- **Cada usuario solo ve sus propios datos.** Lo garantiza la propia base de datos con *Row Level Security* (ver `supabase_schema.sql`), no solo la app. La app usa únicamente la llave pública más la sesión de cada usuario.
- **El coach y el escáner usan Google Gemini:** los mensajes y fotos que el usuario envía se mandan a Google para generar la respuesta.
- Si publicas la app para otras personas, necesitas un aviso de privacidad y su consentimiento para tratar datos de salud; consúltalo con un abogado.

## Estructura

| Archivo | Función |
|---|---|
| `app.py` | Interfaz de Streamlit (las 4 pestañas) |
| `db.py` | Modo local: base SQLite (actividad, peso y perfil). También la zona horaria y el cálculo de calorías con lastre |
| `db_supabase.py` | Modo nube: login y acceso a Supabase, un cliente por sesión |
| `sesion_cookie.py` | Mantiene la sesión al recargar la página (cookie con el token de renovación) |
| `supabase_schema.sql` | Tablas y reglas de seguridad (RLS) para pegar en Supabase |
| `vision_service.py` | Análisis de fotos de comida con Gemini |
| `metabolic_engine.py` | Cálculo de TMB, calorías y macros (Mifflin-St Jeor) |
| `schemas.py` | Modelos de datos (Pydantic) |

## Licencia

Pendiente de definir.
