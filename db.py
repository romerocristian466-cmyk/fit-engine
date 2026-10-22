"""
db.py — Capa de persistencia SQLite para Fit Engine v2.0
Maneja los registros de actividad diaria con soporte para lastre (pesas de muñecas/tobillos)
y puntuación de cumplimiento de protocolos.
"""
import sqlite3
import os
from datetime import date, datetime, timedelta
from typing import Optional

DB_PATH = os.getenv("FIT_ENGINE_DB", "fit_engine.db")


# ──────────────────────────────────────────────────────────────────────────────
# Inicialización
# ──────────────────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Crea las tablas si no existen."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS actividad (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha               TEXT    NOT NULL UNIQUE,
                pasos               INTEGER NOT NULL DEFAULT 0,
                minutos_ejercicio   INTEGER NOT NULL DEFAULT 0,
                tipo_ejercicio      TEXT    NOT NULL DEFAULT 'Caminata / Cardio',
                lastre_munecas_lb   REAL    NOT NULL DEFAULT 0.0,
                lastre_tobillos_lb  REAL    NOT NULL DEFAULT 0.0,
                protocol_rest       INTEGER NOT NULL DEFAULT 0,   -- 1 = descansó / 0 = no descansó
                compliance_score    REAL    NOT NULL DEFAULT 0.0, -- 0-100
                notas               TEXT
            )
        """)
        conn.commit()


# ──────────────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────────────

def guardar_registro(
    fecha: date,
    pasos: int,
    minutos_ejercicio: int,
    tipo_ejercicio: str,
    lastre_munecas_lb: float,
    lastre_tobillos_lb: float,
    protocol_rest: bool,
    compliance_score: float,
    notas: str = "",
) -> None:
    """Inserta o actualiza el registro del día."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO actividad
                (fecha, pasos, minutos_ejercicio, tipo_ejercicio,
                 lastre_munecas_lb, lastre_tobillos_lb,
                 protocol_rest, compliance_score, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fecha) DO UPDATE SET
                pasos              = excluded.pasos,
                minutos_ejercicio  = excluded.minutos_ejercicio,
                tipo_ejercicio     = excluded.tipo_ejercicio,
                lastre_munecas_lb  = excluded.lastre_munecas_lb,
                lastre_tobillos_lb = excluded.lastre_tobillos_lb,
                protocol_rest      = excluded.protocol_rest,
                compliance_score   = excluded.compliance_score,
                notas              = excluded.notas
        """, (
            str(fecha), pasos, minutos_ejercicio, tipo_ejercicio,
            lastre_munecas_lb, lastre_tobillos_lb,
            int(protocol_rest), compliance_score, notas,
        ))
        conn.commit()


def obtener_ultimos_registros(n: int = 7) -> list[dict]:
    """Devuelve los últimos `n` registros ordenados por fecha DESC."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM actividad ORDER BY fecha DESC LIMIT ?", (n,)
        ).fetchall()
    return [dict(r) for r in rows]


def obtener_rango(dias: int = 30) -> list[dict]:
    """Devuelve registros de los últimos `dias` días."""
    desde = str(date.today() - timedelta(days=dias))
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM actividad WHERE fecha >= ? ORDER BY fecha ASC", (desde,)
        ).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Lógica de Ajuste Metabólico Proactivo
# ──────────────────────────────────────────────────────────────────────────────

def necesita_ajuste_recuperacion() -> bool:
    """
    Retorna True si los últimos 2 registros tienen protocol_rest == 0
    (el usuario no ha descansado en los últimos 2 días registrados).
    """
    registros = obtener_ultimos_registros(n=2)
    if len(registros) < 2:
        return False
    return all(r["protocol_rest"] == 0 for r in registros)


# ──────────────────────────────────────────────────────────────────────────────
# Cálculo de gasto calórico con lastre
# ──────────────────────────────────────────────────────────────────────────────

def calcular_calorias_con_lastre(
    pasos: int,
    peso_usuario_kg: float,
    lastre_munecas_lb: float,
    lastre_tobillos_lb: float,
    mins_ejercicio: int,
) -> float:
    """
    Estima el gasto calórico total de la sesión considerando el lastre.

    Fórmula base: 0.04 kcal por paso por kg de peso corporal (caminata moderada).
    El lastre de tobillos penaliza más (mayor esfuerzo biomecánico) que el de muñecas.
    Referencia: aumento ~5% de VO2 por cada 1 kg de lastre en extremidades.
    """
    lastre_munecas_kg  = lastre_munecas_lb  * 0.4536
    lastre_tobillos_kg = lastre_tobillos_lb * 0.4536

    # Peso efectivo: tobillos suman ~1.5x por el costo biomecánico
    peso_efectivo = peso_usuario_kg + lastre_munecas_kg + (lastre_tobillos_kg * 1.5)

    kcal_pasos    = pasos * 0.04 * (peso_efectivo / 70.0)
    kcal_ejercicio = mins_ejercicio * 5.0 * (peso_efectivo / 70.0)

    return round(kcal_pasos + kcal_ejercicio, 1)
