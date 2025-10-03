
"""
# server_mcp.py
Servidor MCP (Model Context Protocol) para gestión de aviones.

Expone herramientas MCP que consultan una base de datos PostgreSQL usando asyncpg.
Herramientas disponibles: conteo total, obtener por id, filtrar por estado/aerolínea/fecha,
crear, actualizar y eliminar aviones. Este servidor se comunica por stdio con el cliente MCP.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Dict, Any
from datetime import datetime

import asyncpg
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP, Context

# --- 1. Modelo de Datos (Pydantic) para Aviones ---

class Avion(BaseModel):
    """Modelo de salida para registros de la tabla public.aviones."""

    id: int
    modelo: str
    capacidad: int
    aerolinea: str
    estado: str
    fecha_fabricacion: Optional[datetime] = None

# --- 2. Contexto y Ciclo de Vida del Servidor con PostgreSQL ---
# Esto gestiona el "pool" de conexiones a la base de datos.
@dataclass
class AppContext:
    """Contexto de aplicación compartido por todas las herramientas (pool de DB)."""

    db_pool: asyncpg.Pool

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Crea y cierra el pool de conexiones a PostgreSQL durante el ciclo de vida del server."""
    print("Conectando a la base de datos PostgreSQL...")
    try:
        pool = await asyncpg.create_pool(
            user= os.getenv("POSTGRES_USER"),
            password= os.getenv("POSTGRES_PASSWORD"),
            database= os.getenv("POSTGRES_DB"),
            host= os.getenv("POSTGRES_HOST"),
    
        )
        print("Pool de conexiones a PostgreSQL creado.")
        yield AppContext(db_pool=pool)
    finally:
        if 'pool' in locals() and pool:
            await pool.close()
            print("🔌 Pool de conexiones a PostgreSQL cerrado.")

# --- 3. Creación del Servidor MCP ---
# Le pasamos el nuevo gestor de ciclo de vida y configuración de puerto
port = int(os.getenv("PORT", "3001"))
mcp = FastMCP("AvionesServer", lifespan=app_lifespan, host="0.0.0.0", port=port)

# --- 4. Herramientas MCP para Aviones ---

@mcp.tool()
async def get_total_avion_count(ctx: Context) -> Dict[str, Any]:
    """Devuelve el número total de aviones registrados."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM aviones")
    return {"total_aviones": count}

@mcp.tool()
async def get_avion_by_id(avion_id: int, ctx: Context) -> Optional[Avion]:
    """Obtiene un avión por su ID."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, modelo, capacidad, aerolinea, estado, fecha_fabricacion FROM aviones WHERE id = $1", avion_id)
        return Avion(**row) if row else None

@mcp.tool()
async def get_aviones_by_estado(estado: str, ctx: Context) -> List[Avion]:
    """Lista aviones por estado (disponible, mantenimiento, fuera_de_servicio)."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, modelo, capacidad, aerolinea, estado, fecha_fabricacion FROM aviones WHERE estado = $1 ORDER BY id DESC",
            estado,
        )
        return [Avion(**row) for row in rows]

@mcp.tool()
async def get_aviones_by_aerolinea(aerolinea: str, ctx: Context) -> List[Avion]:
    """Lista aviones por aerolínea."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, modelo, capacidad, aerolinea, estado, fecha_fabricacion FROM aviones WHERE aerolinea = $1 ORDER BY id DESC",
            aerolinea,
        )
        return [Avion(**row) for row in rows]

@mcp.tool()
async def get_aviones_by_fecha_fabricacion(fecha_fabricacion: datetime, ctx: Context) -> List[Avion]:
    """Lista aviones por fecha de fabricación exacta (usar ISO YYYY-MM-DD)."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        # Comparación por fecha (sin hora) para conveniencia
        rows = await conn.fetch(
            """
            SELECT id, modelo, capacidad, aerolinea, estado, fecha_fabricacion
            FROM aviones
            WHERE DATE(fecha_fabricacion) = DATE($1)
            ORDER BY id DESC
            """,
            fecha_fabricacion,
        )
        return [Avion(**row) for row in rows]

@mcp.tool()
async def create_avion(
    modelo: str,
    capacidad: int,
    aerolinea: str,
    estado: Optional[str] = None,
    fecha_fabricacion: Optional[datetime] = None,
    ctx: Context = None,
) -> Avion:
    """Crea un avión y devuelve el registro creado."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO aviones (modelo, capacidad, aerolinea, estado, fecha_fabricacion)
            VALUES ($1, $2, $3, COALESCE($4, 'disponible'), $5)
            RETURNING id, modelo, capacidad, aerolinea, estado, fecha_fabricacion
            """,
            modelo,
            capacidad,
            aerolinea,
            estado,
            fecha_fabricacion,
        )
        return Avion(**row)

@mcp.tool()
async def update_avion(
    avion_id: int,
    modelo: Optional[str] = None,
    capacidad: Optional[int] = None,
    aerolinea: Optional[str] = None,
    estado: Optional[str] = None,
    fecha_fabricacion: Optional[datetime] = None,
    ctx: Context = None,
) -> Optional[Avion]:
    """Actualiza campos parciales de un avión y devuelve el resultado."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE aviones SET
                modelo = COALESCE($2, modelo),
                capacidad = COALESCE($3, capacidad),
                aerolinea = COALESCE($4, aerolinea),
                estado = COALESCE($5, estado),
                fecha_fabricacion = COALESCE($6, fecha_fabricacion)
            WHERE id = $1
            RETURNING id, modelo, capacidad, aerolinea, estado, fecha_fabricacion
            """,
            avion_id,
            modelo,
            capacidad,
            aerolinea,
            estado,
            fecha_fabricacion,
        )
        return Avion(**row) if row else None

@mcp.tool()
async def delete_avion(avion_id: int, ctx: Context) -> Optional[Avion]:
    """Elimina un avión por ID y devuelve el registro eliminado."""
    pool: asyncpg.Pool = ctx.request_context.lifespan_context.db_pool
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM aviones WHERE id = $1 RETURNING id, modelo, capacidad, aerolinea, estado, fecha_fabricacion",
            avion_id,
        )
        return Avion(**row) if row else None


# --- 5. Ejecución del Servidor ---
if __name__ == "__main__":
    import sys
    
    # Verificar si se debe ejecutar en modo HTTP
    if "--http" in sys.argv:
        print(f"🚀 Iniciando servidor MCP en modo SSE en puerto {port}")
        # FastMCP SSE transport - funciona con la versión actual
        mcp.run(transport="sse")
    else:
        # Modo stdio por defecto
        print("🚀 Iniciando servidor MCP en modo stdio")
        mcp.run()