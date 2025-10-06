
"""
# server_mcp.py
Servidor MCP (Model Context Protocol) para gestión de aviones.

Expone herramientas MCP que consumen microservicios vía API Gateway HTTP.
Herramientas disponibles: consultar y crear aviones. Este servidor se comunica por stdio con el cliente MCP.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Dict, Any
from datetime import datetime

import os
from dotenv import load_dotenv
import httpx
import asyncio

# Cargar variables de entorno
load_dotenv()

from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP, Context

# --- 1. Modelo de Datos (Pydantic) para Aviones ---

class Avion(BaseModel):
    """Modelo de salida para registros de la entidad Avion."""

    id: int
    modelo: str
    capacidad: int
    aerolinea: str
    estado: str
    fecha_fabricacion: Optional[datetime] = None

class AvionCreate(BaseModel):
    """Payload de creación de aviones."""

    modelo: str
    capacidad: int
    aerolinea: str
    estado: Optional[str] = Field(default="disponible")
    fecha_fabricacion: Optional[datetime] = None

class AvionCount(BaseModel):
    total_aviones: int

# Modelos Pydantic para otros microservicios
from pydantic import ConfigDict

class Pago(BaseModel):
    id: int
    monto: float
    fecha: datetime
    estado: str
    moneda: str
    metodo_pago: Optional[str] = None
    reserva: str

class PagoCreate(BaseModel):
    monto: float
    fecha: datetime
    estado: str
    moneda: str
    metodo_pago: Optional[str] = None
    reserva: str

class Reserva(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    usuario: str
    vuelo: str
    estado: str
    numasiento: str

class ReservaCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    usuario: str
    vuelo: str
    estado: str
    numasiento: str

class Mantenimiento(BaseModel):
    id: Optional[str] = None
    avion_id: str
    tipo: str
    descripcion: str
    fecha: datetime
    responsable: str
    costo: float
    estado: str

class MantenimientoCreate(BaseModel):
    avion_id: str
    tipo: str
    descripcion: str
    fecha: datetime
    responsable: str
    costo: float
    estado: str

# --- Modelos Pydantic para Microservicio de Usuarios ---
class Persona(BaseModel):
    id: int
    cedula: str
    nombre: str
    apellido: str
    telefono: str
    email: str
    rol: str
    contrasenia: str

class Usuario(Persona):
    direccion: str
    reservaId: Optional[int] = None

class Empleado(Persona):
    salario: float
    cargo: str

class Admin(Persona):
    nivelAcceso: str
    sueldo: float
    permiso: str

# Eliminado: UpdatePasswordRequest (no se permiten operaciones de actualización)






# --- 2. Contexto y Ciclo de Vida del Servidor HTTP ---
@dataclass
class AppContext:
    """Contexto de aplicación compartido por todas las herramientas (cliente HTTP)."""

    http_client: httpx.AsyncClient






@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Crea y cierra el cliente HTTP durante el ciclo de vida del server."""
    http_client = httpx.AsyncClient(timeout=10.0)
    try:
        yield AppContext(http_client=http_client)
    finally:
        await http_client.aclose()
        print("🔌 Cliente HTTP cerrado.")





# --- 3. Creación del Servidor MCP ---
# Le pasamos el nuevo gestor de ciclo de vida y configuración de puerto
port = int(os.getenv("PORT", "3001"))
mcp = FastMCP("AvionesServer", lifespan=app_lifespan, host="0.0.0.0", port=port)

# --- 4. Herramientas MCP para Aviones (HTTP vía API Gateway) ---

# Base URL del API Gateway para el microservicio de aviones
AVIONES_BASE_URL = os.getenv("AVIONES_BASE_URL", "http://localhost:8080/ServiceAvion")

@mcp.tool()
async def get_total_avion_count(ctx: Context) -> AvionCount:
    """Devuelve el número total de aviones registrados (suma por estados conocidos)."""
    estados = ["disponible", "mantenimiento", "fuera_de_servicio"]
    total = 0
    for estado in estados:
        url = f"{AVIONES_BASE_URL}/aviones"
        data = await _http_get(ctx, url)
        if isinstance(data, list):
            total += len(data)
        elif isinstance(data, dict) and data.get("status") == "error":
            raise RuntimeError(f"Error al contar aviones para estado '{estado}': {data}")
        else:
            items = data.get("items") if isinstance(data, dict) else None
            total += len(items) if isinstance(items, list) else 0
    return AvionCount(total_aviones=total)

@mcp.tool()
async def get_avion_by_id(avion_id: int, ctx: Context) -> Optional[Avion]:
    """Obtiene un avión por su ID usando API Gateway."""
    url = f"{AVIONES_BASE_URL}/{avion_id}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        return None
    try:
        return Avion.model_validate(data)
    except Exception:
        return None

@mcp.tool()
async def get_aviones_by_estado(estado: str, ctx: Context) -> List[Avion]:
    """Lista aviones por estado (disponible, mantenimiento, fuera_de_servicio) vía API Gateway."""
    url = f"{AVIONES_BASE_URL}/estado/{estado}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Avion.model_validate(item) for item in (data or [])]

@mcp.tool()
async def get_aviones_by_aerolinea(aerolinea: str, ctx: Context) -> List[Avion]:
    """Lista aviones por aerolínea vía API Gateway."""
    url = f"{AVIONES_BASE_URL}/aerolinea/{aerolinea}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Avion.model_validate(item) for item in (data or [])]

@mcp.tool()
async def get_aviones_by_fecha_fabricacion(fecha_fabricacion: datetime, ctx: Context) -> List[Avion]:
    """Lista aviones por fecha de fabricación exacta (usar ISO YYYY-MM-DD) vía API Gateway."""
    fecha_str = fecha_fabricacion.strftime("%Y-%m-%d")
    url = f"{AVIONES_BASE_URL}/fecha-fabricacion/{fecha_str}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Avion.model_validate(item) for item in (data or [])]

@mcp.tool()
async def create_avion(avion: AvionCreate, ctx: Context) -> Avion:
    """Crea un avión y devuelve el registro creado (vía API Gateway)."""
    url = f"{AVIONES_BASE_URL}/"
    payload = avion.model_dump(mode="json")
    data = await _http_post(ctx, url, json=payload)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return Avion.model_validate(data)





# --- 5. Herramientas MCP HTTP para otros microservicios ---
# Configuración de URLs base para microservicios (sobrescribibles por variables de entorno)
PAGO_BASE_URL = (os.getenv("PAGO_BASE_URL", "http://localhost:8080/ServicePago") or "").rstrip("/")
RESERVA_BASE_URL = (os.getenv("RESERVA_BASE_URL", "http://localhost:8080/ServiceReserva/api") or "").rstrip("/")
MANTENIMIENTO_BASE_URL = (os.getenv("MANTENIMIENTO_BASE_URL", "http://localhost:8080/ServiceMantenimiento") or "").rstrip("/")
USUARIOS_BASE_URL = (os.getenv("USUARIOS_BASE_URL", "http://localhost:8080/ServiceUsuario/api") or "").rstrip("/")




# Helper HTTP compartido
async def _http_request(ctx: Context, method: str, url: str, params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None):
    client: httpx.AsyncClient = ctx.request_context.lifespan_context.http_client
    max_retries = int(os.getenv("HTTP_MAX_RETRIES", "2"))
    backoff_ms = int(os.getenv("HTTP_RETRY_BACKOFF_MS", "200"))
    attempt = 0
    while True:
        try:
            resp = await client.request(method, url, params=params, json=json)
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return {"status": "ok", "result": resp.text}
        except httpx.HTTPStatusError as e:
            # No reintentar en errores HTTP (4xx/5xx)
            body_text = ""
            try:
                body_text = e.response.text
            except Exception:
                body_text = ""
            return {"status": "error", "code": e.response.status_code, "message": str(e), "url": str(e.request.url), "body": body_text}
        except httpx.RequestError as e:
            # Reintentos para errores de red/transitorios
            if attempt < max_retries:
                attempt += 1
                await asyncio.sleep(backoff_ms / 1000.0)
                continue
            return {"status": "error", "message": f"HTTP request failed: {e}", "url": getattr(e, 'request', None) and str(e.request.url)}



async def _http_get(ctx: Context, url: str, params: Optional[Dict[str, Any]] = None):
    return await _http_request(ctx, "GET", url, params=params)

async def _http_post(ctx: Context, url: str, json: Optional[Dict[str, Any]] = None):
    return await _http_request(ctx, "POST", url, json=json)






# Operaciones PUT/DELETE eliminadas: solo create y get

   
# --- Pagos ---
@mcp.tool()
async def pagos_get_all(ctx: Context) -> List[Pago]:
    """Obtiene todos los pagos (validados con Pydantic)."""
    url = f"{PAGO_BASE_URL}/get-all"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Pago.model_validate(item) for item in (data or [])]





@mcp.tool()
async def pagos_get_by_id(id: int, ctx: Context) -> Optional[Pago]:
    """Obtiene un pago por su ID (valida respuesta)."""
    url = f"{PAGO_BASE_URL}/get/{id}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        return None
    try:
        return Pago.model_validate(data)
    except Exception:
        return None





@mcp.tool()
async def pagos_buscar_por_estado(estado: str, ctx: Context) -> List[Pago]:
    """Busca pagos por estado: PENDIENTE, COMPLETADO o CANCELADO."""
    url = f"{PAGO_BASE_URL}/buscar/estado/{estado}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Pago.model_validate(item) for item in (data or [])]

@mcp.tool()
async def pagos_buscar_por_reserva(reserva_id: str, ctx: Context) -> Optional[Pago]:
    """Busca pago asociado a una reserva (ID de reserva como string)."""
    url = f"{PAGO_BASE_URL}/buscar/reserva/{reserva_id}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        return None
    try:
        return Pago.model_validate(data)
    except Exception:
        return None

@mcp.tool()
async def pagos_buscar_por_moneda(moneda: str, ctx: Context) -> List[Pago]:
    """Busca pagos por moneda."""
    url = f"{PAGO_BASE_URL}/buscar/moneda/{moneda}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Pago.model_validate(item) for item in (data or [])]

@mcp.tool()
async def pagos_buscar_por_monto(monto: float, ctx: Context) -> List[Pago]:
    """Busca pagos por monto."""
    url = f"{PAGO_BASE_URL}/buscar/monto/{monto}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Pago.model_validate(item) for item in (data or [])]

@mcp.tool()
async def pagos_buscar_por_fecha(fecha: str, ctx: Context) -> List[Pago]:
    """Busca pagos por fecha (YYYY-MM-DD)."""
    url = f"{PAGO_BASE_URL}/buscar/fecha/{fecha}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Pago.model_validate(item) for item in (data or [])]

@mcp.tool()
async def pagos_buscar_por_metodo(metodo: str, ctx: Context) -> List[Pago]:
    """Busca pagos por método de pago."""
    url = f"{PAGO_BASE_URL}/buscar/metodo/{metodo}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Pago.model_validate(item) for item in (data or [])]

@mcp.tool()
async def pagos_crear(pago: PagoCreate, ctx: Context) -> Pago:
    """Crea un pago (payload validado) y retorna el registro creado."""
    url = f"{PAGO_BASE_URL}/crear"
    payload = pago.model_dump(mode="json")
    data = await _http_post(ctx, url, json=payload)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return Pago.model_validate(data)

# Operaciones de actualización y borrado de pagos eliminadas (solo create/get)

# --- Reservas ---
@mcp.tool()
async def reservas_get_all(ctx: Context) -> List[Reserva]:
    """
    Obtiene todas las reservas (validadas).
    Devuelve una lista con todas las reservas existentes en el sistema.
    Usa este comando cuando el usuario diga cosas como:
    - "Muéstrame todas las reservas"
    - "Listar las reservas registradas"
    - "Ver todas las reservas actuales"
    
    """
    url = f"{RESERVA_BASE_URL}/reservas"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Reserva.model_validate(item) for item in (data or [])]

@mcp.tool()
async def reservas_get_by_id(id: int, ctx: Context) -> Optional[Reserva]:
    """Obtiene reserva por ID (valida respuesta)."""
    url = f"{RESERVA_BASE_URL}/reservas/{id}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        return None
    try:
        return Reserva.model_validate(data)
    except Exception:
        return None

@mcp.tool()
async def reservas_buscar_por_usuario(usuario: str, ctx: Context) -> List[Reserva]:
    """Busca reservas por usuario (query param usuario)."""
    url = f"{RESERVA_BASE_URL}/reservas/buscar/usuario"
    data = await _http_get(ctx, url, params={"usuario": usuario})
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Reserva.model_validate(item) for item in (data or [])]

@mcp.tool()
async def reservas_buscar_por_estado(estado: str, ctx: Context) -> List[Reserva]:
    """Busca reservas por estado (query param estado)."""
    url = f"{RESERVA_BASE_URL}/reservas/buscar/estado"
    data = await _http_get(ctx, url, params={"estado": estado})
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Reserva.model_validate(item) for item in (data or [])]

@mcp.tool()
async def reservas_buscar_por_vuelo(vuelo: str, ctx: Context) -> List[Reserva]:
    """Busca reservas por vuelo (query param vuelo)."""
    url = f"{RESERVA_BASE_URL}/reservas/buscar/vuelo"
    data = await _http_get(ctx, url, params={"vuelo": vuelo})
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Reserva.model_validate(item) for item in (data or [])]

@mcp.tool()
async def reservas_contar(ctx: Context) -> int:
    """Cuenta el total de reservas."""
    url = f"{RESERVA_BASE_URL}/reservas/contar"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    try:
        return int(data) if not isinstance(data, dict) else int(data.get("result", data.get("count", data.get("total", 0))))
    except Exception:
        raise RuntimeError(f"Respuesta inesperada: {data}")

@mcp.tool()
async def reservas_contar_por_estado(estado: str, ctx: Context) -> int:
    """Cuenta reservas por estado (query param estado)."""
    url = f"{RESERVA_BASE_URL}/reservas/contar/estado"
    data = await _http_get(ctx, url, params={"estado": estado})
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    try:
        return int(data) if not isinstance(data, dict) else int(data.get("result", data.get("count", data.get("total", 0))))
    except Exception:
        raise RuntimeError(f"Respuesta inesperada: {data}")

@mcp.tool()
async def reservas_crear(reserva: ReservaCreate, ctx: Context) -> Reserva:
    """Crea una reserva (payload validado) y retorna el registro creado."""
    url = f"{RESERVA_BASE_URL}/reservas"
    payload = reserva.model_dump(mode="json")
    print(f"[reservas_crear] POST {url} payload={payload}")
    data = await _http_post(ctx, url, json=payload)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return Reserva.model_validate(data)

# --- Mantenimiento ---
@mcp.tool()
async def mantenimientos_get_all(ctx: Context) -> List[Mantenimiento]:
    """Obtiene todos los mantenimientos (validados)."""
    url = f"{MANTENIMIENTO_BASE_URL}/mantenimientos"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Mantenimiento.model_validate(item) for item in (data or [])]

@mcp.tool()
async def mantenimientos_por_avion(avion_id: str, ctx: Context) -> List[Mantenimiento]:
    """Busca mantenimientos por ID de avión."""
    url = f"{MANTENIMIENTO_BASE_URL}/mantenimientos/avion/{avion_id}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Mantenimiento.model_validate(item) for item in (data or [])]

@mcp.tool()
async def mantenimientos_por_estado(estado: str, ctx: Context) -> List[Mantenimiento]:
    """Busca mantenimientos por estado."""
    url = f"{MANTENIMIENTO_BASE_URL}/mantenimientos/estado/{estado}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Mantenimiento.model_validate(item) for item in (data or [])]

@mcp.tool()
async def mantenimientos_get_by_id(id: str, ctx: Context) -> Optional[Mantenimiento]:
    """Obtiene un mantenimiento por ID."""
    url = f"{MANTENIMIENTO_BASE_URL}/mantenimientos/{id}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        return None
    try:
        return Mantenimiento.model_validate(data)
    except Exception:
        return None

@mcp.tool()
async def mantenimientos_crear(mantenimiento: MantenimientoCreate, ctx: Context) -> Mantenimiento:
    """
    Crea un mantenimiento (payload validado) y retorna el registro creado.
    Usa este comando cuando el usuario diga cosas como:
    - "Crear mantenimiento para el avión AV-456"
    - "Registrar mantenimiento preventivo con fecha 2025-10-10"
    - "Agregar revisión de sistemas hidráulicos"
    
    """
    url = f"{MANTENIMIENTO_BASE_URL}/mantenimientos"
    payload = mantenimiento.model_dump(mode="json")
    data = await _http_post(ctx, url, json=payload)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return Mantenimiento.model_validate(data)

# Operaciones de actualización de mantenimientos eliminadas (solo create/get)

# --- Usuarios ---
@mcp.tool()
async def usuarios_get_all(ctx: Context) -> List[Usuario]:
    """Obtiene todos los usuarios (validados con Pydantic)."""
    url = f"{USUARIOS_BASE_URL}/usuarios/all"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Usuario.model_validate(item) for item in (data or [])]

@mcp.tool()
async def usuario_get_by_id(id: int, ctx: Context) -> Optional[Usuario]:
    """Obtiene usuario por ID."""
    url = f"{USUARIOS_BASE_URL}/usuarios/{id}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return Usuario.model_validate(data) if data else None

@mcp.tool()
async def usuarios_count(ctx: Context) -> int:
    """Cuenta usuarios."""
    url = f"{USUARIOS_BASE_URL}/usuarios/count"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    if isinstance(data, dict) and "count" in data:
        return int(data["count"])
    return int(data or 0)

@mcp.tool()
async def usuarios_por_email(email: str, ctx: Context) -> Optional[Usuario]:
    """Busca usuario por email."""
    url = f"{USUARIOS_BASE_URL}/usuarios/email/{email}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return Usuario.model_validate(data) if data else None

@mcp.tool()
async def usuarios_por_cedula(cedula: str, ctx: Context) -> Optional[Usuario]:
    """Busca usuario por cédula."""
    url = f"{USUARIOS_BASE_URL}/usuarios/cedula/{cedula}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return Usuario.model_validate(data) if data else None

@mcp.tool()
async def admins_get_all(ctx: Context) -> List[Admin]:
    """Obtiene todos los administradores."""
    url = f"{USUARIOS_BASE_URL}/admins/all"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Admin.model_validate(item) for item in (data or [])]

@mcp.tool()
async def empleados_get_all(ctx: Context) -> List[Empleado]:
    """Obtiene todos los empleados."""
    url = f"{USUARIOS_BASE_URL}/empleados/all"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Empleado.model_validate(item) for item in (data or [])]

@mcp.tool()
async def empleados_por_cargo(cargo: str, ctx: Context) -> List[Empleado]:
    """Busca empleados por cargo."""
    url = f"{USUARIOS_BASE_URL}/empleados/cargo/{cargo}"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Empleado.model_validate(item) for item in (data or [])]

@mcp.tool()
async def personas_get_all(ctx: Context) -> List[Persona]:
    """Obtiene todas las personas."""
    url = f"{USUARIOS_BASE_URL}/personas/all"
    data = await _http_get(ctx, url)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(f"Error HTTP: {data}")
    return [Persona.model_validate(item) for item in (data or [])]





# --- 6. Ejecución del Servidor ---
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