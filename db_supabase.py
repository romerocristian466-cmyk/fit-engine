"""
db_supabase.py — Modo nube de Fit Engine: Supabase (Postgres + Auth).

Reglas de diseño (importantes para la seguridad):
  * Cada sesión de Streamlit crea SU PROPIO cliente de Supabase y SU PROPIO
    RepoSupabase. Nunca hay un cliente ni un usuario global compartido.
  * La app usa solo la llave PÚBLICA (anon/publishable) más el token del usuario.
    La llave secreta (service_role) NO se usa ni debe ponerse en la app.
  * Lo que impide que un usuario vea datos de otro es RLS en la base de datos
    (ver supabase_schema.sql). Este archivo solo manda user_id por claridad.
  * Los errores técnicos van al log del servidor; al usuario solo le llegan
    mensajes genéricos.
"""
from datetime import timedelta
from typing import Callable, Optional

from supabase import (
    AuthApiError,
    AuthInvalidCredentialsError,
    AuthRetryableError,
    AuthWeakPasswordError,
    ClientOptions,
    create_client,
)
from postgrest.types import ReturnMethod

import db


class ErrorAcceso(Exception):
    """Fallo de inicio de sesión o registro, con un mensaje seguro para mostrar."""


class ErrorDatos(Exception):
    """Fallo al leer o guardar datos, con un mensaje seguro para mostrar."""


# ──────────────────────────────────────────────────────────────────────────────
# Cliente y autenticación
# ──────────────────────────────────────────────────────────────────────────────

def crear_cliente(url: str, key: str):
    """
    Cliente NUEVO para una sesión de Streamlit.
    auto_refresh_token=False: si no, cada sesión abandonada dejaría un temporizador
    renovando el token para siempre en el servidor. En su lugar, sesion_actual()
    renueva el token cuando hace falta.
    """
    return create_client(url, key, options=ClientOptions(auto_refresh_token=False))


def _normalizar_email(email: Optional[str]) -> str:
    email = (email or "").strip().lower()
    dominio = email.split("@")[-1] if "@" in email else ""
    if not email or len(email) > 254 or "." not in dominio or email.count("@") != 1:
        raise ErrorAcceso("Escribe un correo válido.")
    return email


def _mensaje_por_error_auth(e: Exception, defecto: str) -> str:
    estado = getattr(e, "status", None)
    codigo = getattr(e, "code", None)
    if estado == 429 or codigo in ("over_request_rate_limit", "over_email_send_rate_limit"):
        return "Demasiados intentos. Espera unos minutos e inténtalo de nuevo."
    if codigo == "email_not_confirmed":
        return "Debes confirmar tu correo antes de entrar."
    return defecto


def iniciar_sesion(cliente, email: str, password: str) -> None:
    """Inicia sesión. Lanza ErrorAcceso con un mensaje seguro si falla."""
    email = _normalizar_email(email)
    if not password:
        raise ErrorAcceso("Escribe tu contraseña.")
    try:
        cliente.auth.sign_in_with_password({"email": email, "password": password})
    except (AuthInvalidCredentialsError, AuthApiError) as e:
        print(f"[auth] inicio de sesión rechazado: {type(e).__name__} status={getattr(e, 'status', None)}")
        # No se distingue "no existe" de "contraseña mala" (evita adivinar correos)
        raise ErrorAcceso(
            _mensaje_por_error_auth(e, "Correo o contraseña incorrectos.")
        ) from None
    except AuthRetryableError:
        raise ErrorAcceso("No se pudo conectar con el servidor. Inténtalo de nuevo.") from None
    except Exception as e:
        print(f"[auth] error inesperado al iniciar sesión: {type(e).__name__}")
        raise ErrorAcceso("No se pudo conectar con el servidor. Inténtalo de nuevo.") from None


def registrar(cliente, email: str, password: str) -> bool:
    """
    Crea la cuenta. Devuelve True si quedó con la sesión iniciada, o False si
    Supabase exige confirmar el correo antes (en ese caso no hay sesión todavía).
    """
    email = _normalizar_email(email)
    if len(password or "") < 8:
        raise ErrorAcceso("La contraseña debe tener al menos 8 caracteres.")
    try:
        respuesta = cliente.auth.sign_up({"email": email, "password": password})
    except AuthWeakPasswordError:
        raise ErrorAcceso(
            "La contraseña es demasiado débil. Mezcla letras, números y símbolos."
        ) from None
    except AuthApiError as e:
        print(f"[auth] registro rechazado: {type(e).__name__} status={getattr(e, 'status', None)}")
        raise ErrorAcceso(
            _mensaje_por_error_auth(e, "No se pudo crear la cuenta. Si ya tienes una, inicia sesión.")
        ) from None
    except AuthRetryableError:
        raise ErrorAcceso("No se pudo conectar con el servidor. Inténtalo de nuevo.") from None
    except Exception as e:
        print(f"[auth] error inesperado al registrar: {type(e).__name__}")
        raise ErrorAcceso("No se pudo conectar con el servidor. Inténtalo de nuevo.") from None
    return respuesta.session is not None


def sesion_actual(cliente):
    """Sesión vigente (renueva el token si ya venció) o None si no hay sesión válida."""
    if cliente is None:
        return None
    try:
        return cliente.auth.get_session()
    except Exception as e:
        print(f"[auth] no se pudo renovar la sesión: {type(e).__name__}")
        return None


def cerrar_sesion(cliente) -> None:
    if cliente is None:
        return
    try:
        cliente.auth.sign_out()
    except Exception as e:
        print(f"[auth] error al cerrar sesión: {type(e).__name__}")


# ──────────────────────────────────────────────────────────────────────────────
# Repositorio de datos del usuario
# ──────────────────────────────────────────────────────────────────────────────

_COLS_ACTIVIDAD = (
    "fecha,pasos,minutos_ejercicio,tipo_ejercicio,lastre_munecas_lb,"
    "lastre_tobillos_lb,protocol_rest,compliance_score,notas"
)


class RepoSupabase:
    """
    Mismas funciones que el módulo db (modo local), pero sobre Supabase y con el
    token del usuario de esta sesión. Una instancia por sesión; nunca compartida.
    """

    def __init__(self, cliente, user_id: str):
        self._c = cliente
        self._uid = str(user_id)

    def _ejecutar(self, accion: str, fn: Callable):
        try:
            return fn()
        except Exception as e:
            # Detalle técnico solo al log del servidor
            print(f"[datos] error al {accion}: {type(e).__name__}: {getattr(e, 'message', e)}")
            raise ErrorDatos(f"No se pudo {accion}. Inténtalo de nuevo.") from None

    def init_db(self) -> None:
        """El esquema se crea una vez con supabase_schema.sql; aquí no hay nada que hacer."""

    # ── Límite diario de IA ─────────────────────────────────────────────────
    def consumir_cuota(self, tipo: str) -> tuple[bool, int, int]:
        """Cuenta un uso de IA de hoy. Devuelve (permitido, usados, limite).

        La cuenta la lleva la base de datos (función atómica); si falla, se lanza
        ErrorDatos y la app NO llama a Gemini (falla cerrado)."""
        def _rpc():
            r = self._c.rpc("consumir_cuota", {"p_tipo": tipo}).execute().data
            fila = r[0] if isinstance(r, list) else r
            return bool(fila["permitido"]), int(fila["usados"]), int(fila["limite"])
        return self._ejecutar("verificar tu límite diario", _rpc)

    # ── Actividad ───────────────────────────────────────────────────────────
    def guardar_registro(
        self, fecha, pasos, minutos_ejercicio, tipo_ejercicio,
        lastre_munecas_lb, lastre_tobillos_lb, protocol_rest, compliance_score,
        notas: str = "",
    ) -> None:
        fila = {
            "user_id": self._uid,
            "fecha": str(fecha),
            "pasos": int(pasos),
            "minutos_ejercicio": int(minutos_ejercicio),
            "tipo_ejercicio": tipo_ejercicio,
            "lastre_munecas_lb": float(lastre_munecas_lb),
            "lastre_tobillos_lb": float(lastre_tobillos_lb),
            "protocol_rest": bool(protocol_rest),
            "compliance_score": float(compliance_score),
            "notas": notas,
        }
        self._ejecutar("guardar el registro", lambda: (
            self._c.table("actividad")
            .upsert(fila, on_conflict="user_id,fecha", returning=ReturnMethod.minimal)
            .execute()
        ))

    def obtener_ultimos_registros(self, n: int = 7) -> list[dict]:
        r = self._ejecutar("leer los registros", lambda: (
            self._c.table("actividad").select(_COLS_ACTIVIDAD)
            .order("fecha", desc=True).limit(n).execute()
        ))
        return list(r.data or [])

    def obtener_rango(self, dias: int = 30) -> list[dict]:
        desde = str(db.hoy() - timedelta(days=dias))
        r = self._ejecutar("leer los registros", lambda: (
            self._c.table("actividad").select(_COLS_ACTIVIDAD)
            .gte("fecha", desde).order("fecha").execute()
        ))
        return list(r.data or [])

    def necesita_ajuste_recuperacion(self) -> bool:
        return db.debe_recuperar(self.obtener_ultimos_registros(n=2))

    # ── Peso ────────────────────────────────────────────────────────────────
    def guardar_peso(self, fecha, peso_kg: float) -> None:
        fila = {"user_id": self._uid, "fecha": str(fecha), "peso_kg": float(peso_kg)}
        self._ejecutar("guardar el peso", lambda: (
            self._c.table("peso")
            .upsert(fila, on_conflict="user_id,fecha", returning=ReturnMethod.minimal)
            .execute()
        ))

    def obtener_pesos(self, dias: Optional[int] = None) -> list[dict]:
        def consulta():
            q = self._c.table("peso").select("fecha,peso_kg")
            if dias is not None:
                q = q.gte("fecha", str(db.hoy() - timedelta(days=dias)))
            return q.order("fecha").execute()
        return list(self._ejecutar("leer los pesos", consulta).data or [])

    def obtener_ultimo_peso(self) -> Optional[float]:
        r = self._ejecutar("leer el peso", lambda: (
            self._c.table("peso").select("peso_kg")
            .order("fecha", desc=True).limit(1).execute()
        ))
        return float(r.data[0]["peso_kg"]) if r.data else None

    # ── Perfil ──────────────────────────────────────────────────────────────
    def obtener_perfil(self) -> dict:
        r = self._ejecutar("leer el perfil", lambda: (
            self._c.table("perfil").select("nombre,meta_peso_kg").limit(1).execute()
        ))
        return dict(r.data[0]) if r.data else {}

    def guardar_perfil(self, nombre: Optional[str], meta_peso_kg: Optional[float]) -> None:
        fila = {
            "user_id": self._uid,
            "nombre": (nombre or "").strip()[:60] or None,
            "meta_peso_kg": None if meta_peso_kg is None else float(meta_peso_kg),
        }
        self._ejecutar("guardar el perfil", lambda: (
            self._c.table("perfil")
            .upsert(fila, on_conflict="user_id", returning=ReturnMethod.minimal)
            .execute()
        ))
