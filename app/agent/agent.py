"""
# agent.py
Agente local que interpreta consultas y mapea a herramientas MCP de aviones.

Usa Mirascope con Ollama (modelo mistral) para transformar lenguaje natural
en una llamada de herramienta estructurada y luego ejecuta esa herramienta
contra el servidor MCP activo.
"""

import asyncio
import sys
import json
from typing import Dict, Any, Optional, List

from mirascope import llm, BaseTool
from pydantic import Field, ValidationError
from mcp import ClientSession
from mcp.client.sse import sse_client

# --- 1. Definición de Herramientas (Aviones, Pagos, Reservas, Mantenimientos, Usuarios) ---
class GetTotalAvionCountTool(BaseTool):
    """Devuelve el número total de aviones en el sistema."""
    def call(self) -> str: return "Herramienta 'GetTotalAvionCountTool' seleccionada."

class GetAvionByIdTool(BaseTool):
    """Obtiene un avión por su ID."""
    avion_id: int = Field(..., description="ID del avión")
    def call(self) -> str: return f"Herramienta 'GetAvionByIdTool' seleccionada para el avión {self.avion_id}."

class GetAvionesByEstadoTool(BaseTool):
    """Lista aviones por estado."""
    estado: str = Field(..., description="Estado: disponible|mantenimiento|fuera_de_servicio")
    def call(self) -> str: return f"Herramienta 'GetAvionesByEstadoTool' seleccionada para estado {self.estado}."

class GetAvionesByAerolineaTool(BaseTool):
    """Lista aviones por aerolínea."""
    aerolinea: str = Field(..., description="Nombre de la aerolínea")
    def call(self) -> str: return f"Herramienta 'GetAvionesByAerolineaTool' seleccionada para aerolínea {self.aerolinea}."

class GetAvionesByFechaFabricacionTool(BaseTool):
    """Lista aviones por fecha de fabricación (YYYY-MM-DD)."""
    fecha_fabricacion: str = Field(..., description="Fecha ISO YYYY-MM-DD")
    def call(self) -> str: return f"Herramienta 'GetAvionesByFechaFabricacionTool' seleccionada para fecha {self.fecha_fabricacion}."

class CreateAvionTool(BaseTool):
    """Crea un avión."""
    modelo: str
    capacidad: int
    aerolinea: str
    estado: Optional[str] = None
    fecha_fabricacion: Optional[str] = None
    def call(self) -> str: return "Herramienta 'CreateAvionTool' seleccionada."

# --- Herramientas: Pagos ---
class PagosGetAllTool(BaseTool):
    def call(self) -> str: return "Herramienta 'PagosGetAllTool' seleccionada."

class PagosGetByIdTool(BaseTool):
    id: int = Field(..., description="ID del pago")
    def call(self) -> str: return f"Herramienta 'PagosGetByIdTool' seleccionada para pago {self.id}."

class PagosBuscarPorEstadoTool(BaseTool):
    estado: str = Field(..., description="Estado del pago")
    def call(self) -> str: return f"Herramienta 'PagosBuscarPorEstadoTool' seleccionada para estado {self.estado}."

class PagosBuscarPorReservaTool(BaseTool):
    reserva_id: str = Field(..., description="ID de la reserva asociada")
    def call(self) -> str: return f"Herramienta 'PagosBuscarPorReservaTool' seleccionada para reserva {self.reserva_id}."

class PagosBuscarPorMonedaTool(BaseTool):
    moneda: str = Field(..., description="Moneda del pago")
    def call(self) -> str: return f"Herramienta 'PagosBuscarPorMonedaTool' seleccionada para moneda {self.moneda}."

class PagosBuscarPorMontoTool(BaseTool):
    monto: float = Field(..., description="Monto del pago")
    def call(self) -> str: return f"Herramienta 'PagosBuscarPorMontoTool' seleccionada para monto {self.monto}."

class PagosBuscarPorFechaTool(BaseTool):
    fecha: str = Field(..., description="Fecha (YYYY-MM-DD)")
    def call(self) -> str: return f"Herramienta 'PagosBuscarPorFechaTool' seleccionada para fecha {self.fecha}."

class PagosBuscarPorMetodoTool(BaseTool):
    metodo: str = Field(..., description="Método de pago")
    def call(self) -> str: return f"Herramienta 'PagosBuscarPorMetodoTool' seleccionada para método {self.metodo}."

class PagosCrearTool(BaseTool):
    pago: Dict[str, Any] = Field(..., description="Objeto PagoCreate")
    def call(self) -> str: return "Herramienta 'PagosCrearTool' seleccionada."

# --- Herramientas: Reservas ---
class ReservasGetAllTool(BaseTool):
    def call(self) -> str: return "Herramienta 'ReservasGetAllTool' seleccionada."

class ReservasGetByIdTool(BaseTool):
    id: int = Field(..., description="ID de la reserva")
    def call(self) -> str: return f"Herramienta 'ReservasGetByIdTool' seleccionada para reserva {self.id}."

class ReservasBuscarPorUsuarioTool(BaseTool):
    usuario: str = Field(..., description="Usuario")
    def call(self) -> str: return f"Herramienta 'ReservasBuscarPorUsuarioTool' seleccionada para usuario {self.usuario}."

class ReservasBuscarPorEstadoTool(BaseTool):
    estado: str = Field(..., description="Estado de la reserva")
    def call(self) -> str: return f"Herramienta 'ReservasBuscarPorEstadoTool' seleccionada para estado {self.estado}."

class ReservasBuscarPorVueloTool(BaseTool):
    vuelo: str = Field(..., description="Código del vuelo")
    def call(self) -> str: return f"Herramienta 'ReservasBuscarPorVueloTool' seleccionada para vuelo {self.vuelo}."

class ReservasContarTool(BaseTool):
    def call(self) -> str: return "Herramienta 'ReservasContarTool' seleccionada."

class ReservasContarPorEstadoTool(BaseTool):
    estado: str = Field(..., description="Estado de la reserva")
    def call(self) -> str: return f"Herramienta 'ReservasContarPorEstadoTool' seleccionada para estado {self.estado}."

class ReservasCrearTool(BaseTool):
    reserva: Dict[str, Any] = Field(..., description="Objeto ReservaCreate")
    def call(self) -> str: return "Herramienta 'ReservasCrearTool' seleccionada."

# --- Herramientas: Mantenimientos ---
class MantenimientosGetAllTool(BaseTool):
    def call(self) -> str: return "Herramienta 'MantenimientosGetAllTool' seleccionada."

class MantenimientosPorAvionTool(BaseTool):
    avion_id: str = Field(..., description="ID del avión (string)")
    def call(self) -> str: return f"Herramienta 'MantenimientosPorAvionTool' seleccionada para avión {self.avion_id}."

class MantenimientosPorEstadoTool(BaseTool):
    estado: str = Field(..., description="Estado del mantenimiento")
    def call(self) -> str: return f"Herramienta 'MantenimientosPorEstadoTool' seleccionada para estado {self.estado}."

class MantenimientosGetByIdTool(BaseTool):
    id: str = Field(..., description="ID del mantenimiento (string)")
    def call(self) -> str: return f"Herramienta 'MantenimientosGetByIdTool' seleccionada para mantenimiento {self.id}."

class MantenimientosCrearTool(BaseTool):
    mantenimiento: Dict[str, Any] = Field(..., description="Objeto MantenimientoCreate")
    def call(self) -> str: return "Herramienta 'MantenimientosCrearTool' seleccionada."

# --- Herramientas: Usuarios ---
class UsuariosGetAllTool(BaseTool):
    def call(self) -> str: return "Herramienta 'UsuariosGetAllTool' seleccionada."

class UsuarioGetByIdTool(BaseTool):
    id: int = Field(..., description="ID del usuario")
    def call(self) -> str: return f"Herramienta 'UsuarioGetByIdTool' seleccionada para usuario {self.id}."

class UsuariosCountTool(BaseTool):
    def call(self) -> str: return "Herramienta 'UsuariosCountTool' seleccionada."

class UsuariosPorEmailTool(BaseTool):
    email: str = Field(..., description="Email del usuario")
    def call(self) -> str: return f"Herramienta 'UsuariosPorEmailTool' seleccionada para email {self.email}."

class UsuariosPorCedulaTool(BaseTool):
    cedula: str = Field(..., description="Cédula del usuario")
    def call(self) -> str: return f"Herramienta 'UsuariosPorCedulaTool' seleccionada para cédula {self.cedula}."

class AdminsGetAllTool(BaseTool):
    def call(self) -> str: return "Herramienta 'AdminsGetAllTool' seleccionada."

class EmpleadosGetAllTool(BaseTool):
    def call(self) -> str: return "Herramienta 'EmpleadosGetAllTool' seleccionada."

class EmpleadosPorCargoTool(BaseTool):
    cargo: str = Field(..., description="Cargo del empleado")
    def call(self) -> str: return f"Herramienta 'EmpleadosPorCargoTool' seleccionada para cargo {self.cargo}."

class PersonasGetAllTool(BaseTool):
    def call(self) -> str: return "Herramienta 'PersonasGetAllTool' seleccionada."

# Sección de herramientas removida por mantenimiento

# --- 2. Mapeos de Herramientas ---
TOOL_MAP = {
    # Aviones
    GetTotalAvionCountTool: "get_total_avion_count",
    GetAvionByIdTool: "get_avion_by_id",
    GetAvionesByEstadoTool: "get_aviones_by_estado",
    GetAvionesByAerolineaTool: "get_aviones_by_aerolinea",
    GetAvionesByFechaFabricacionTool: "get_aviones_by_fecha_fabricacion",
    CreateAvionTool: "create_avion",
    # Pagos
    PagosGetAllTool: "pagos_get_all",
    PagosGetByIdTool: "pagos_get_by_id",
    PagosBuscarPorEstadoTool: "pagos_buscar_por_estado",
    PagosBuscarPorReservaTool: "pagos_buscar_por_reserva",
    PagosBuscarPorMonedaTool: "pagos_buscar_por_moneda",
    PagosBuscarPorMontoTool: "pagos_buscar_por_monto",
    PagosBuscarPorFechaTool: "pagos_buscar_por_fecha",
    PagosBuscarPorMetodoTool: "pagos_buscar_por_metodo",
    PagosCrearTool: "pagos_crear",
    # Reservas
    ReservasGetAllTool: "reservas_get_all",
    ReservasGetByIdTool: "reservas_get_by_id",
    ReservasBuscarPorUsuarioTool: "reservas_buscar_por_usuario",
    ReservasBuscarPorEstadoTool: "reservas_buscar_por_estado",
    ReservasBuscarPorVueloTool: "reservas_buscar_por_vuelo",
    ReservasContarTool: "reservas_contar",
    ReservasContarPorEstadoTool: "reservas_contar_por_estado",
    ReservasCrearTool: "reservas_crear",
    # Mantenimientos
    MantenimientosGetAllTool: "mantenimientos_get_all",
    MantenimientosPorAvionTool: "mantenimientos_por_avion",
    MantenimientosPorEstadoTool: "mantenimientos_por_estado",
    MantenimientosGetByIdTool: "mantenimientos_get_by_id",
    MantenimientosCrearTool: "mantenimientos_crear",
    # Usuarios
    UsuariosGetAllTool: "usuarios_get_all",
    UsuarioGetByIdTool: "usuario_get_by_id",
    UsuariosCountTool: "usuarios_count",
    UsuariosPorEmailTool: "usuarios_por_email",
    UsuariosPorCedulaTool: "usuarios_por_cedula",
    AdminsGetAllTool: "admins_get_all",
    EmpleadosGetAllTool: "empleados_get_all",
    EmpleadosPorCargoTool: "empleados_por_cargo",
    PersonasGetAllTool: "personas_get_all",
}
TOOL_NAME_TO_CLASS_MAP = {cls.__name__: cls for cls in TOOL_MAP.keys()}

# --- 3. Función de llamada al LLM ---
@llm.call(
    "google",
    model="gemini-2.5-pro",
    tools=[
        # Aviones
        GetTotalAvionCountTool,
        GetAvionByIdTool,
        GetAvionesByEstadoTool,
        GetAvionesByAerolineaTool,
        GetAvionesByFechaFabricacionTool,
        CreateAvionTool,
        # Pagos
        PagosGetAllTool,
        PagosGetByIdTool,
        PagosBuscarPorEstadoTool,
        PagosBuscarPorReservaTool,
        PagosBuscarPorMonedaTool,
        PagosBuscarPorMontoTool,
        PagosBuscarPorFechaTool,
        PagosBuscarPorMetodoTool,
        PagosCrearTool,
        # Reservas
        ReservasGetAllTool,
        ReservasGetByIdTool,
        ReservasBuscarPorUsuarioTool,
        ReservasBuscarPorEstadoTool,
        ReservasBuscarPorVueloTool,
        ReservasContarTool,
        ReservasContarPorEstadoTool,
        ReservasCrearTool,
        # Mantenimientos
        MantenimientosGetAllTool,
        MantenimientosPorAvionTool,
        MantenimientosPorEstadoTool,
        MantenimientosGetByIdTool,
        MantenimientosCrearTool,
        # Usuarios
        UsuariosGetAllTool,
        UsuarioGetByIdTool,
        UsuariosCountTool,
        UsuariosPorEmailTool,
        UsuariosPorCedulaTool,
        AdminsGetAllTool,
        EmpleadosGetAllTool,
        EmpleadosPorCargoTool,
        PersonasGetAllTool,
    ],
)
def get_user_intent(query: str):
    """
    Convierte la solicitud del usuario en una salida JSON ESTRICTA que indique:
    - selección de herramienta con argumentos tipados, o
    - necesidad de aclaración si faltan campos críticos.

    Instrucciones del router:
    1) Lee primero la sección "Campos normalizados" si está presente al final del prompt: "Campos normalizados: k=v, ...". Estos valores prevalecen sobre el texto libre cuando haya conflicto.
    2) Usa los nombres de clase EXACTOS de las herramientas disponibles.
    3) Devuelve SOLO uno de los siguientes formatos JSON:
       a) Selección de herramienta:
          [{"name": "<NombreClaseDeHerramienta>", "arguments": { ... }}]
       b) Aclaración:
          {"clarify": {"message": "Describe brevemente qué falta", "missing_fields": ["campo1", "campo2"]}}
    4) Usa sinónimos mínimos y mapea a los nombres canónicos de argumentos:
       Aviones:
         - GetAvionByIdTool: {"avion_id": int}
         - GetAvionesByEstadoTool: {"estado": "disponible|mantenimiento|fuera_de_servicio"}
         - GetAvionesByAerolineaTool: {"aerolinea": string}
         - GetAvionesByFechaFabricacionTool: {"fecha_fabricacion": "YYYY-MM-DD"}
         - CreateAvionTool: {"modelo": string, "capacidad": int, "aerolinea": string, "estado"?: string, "fecha_fabricacion"?: "YYYY-MM-DD"}
       Pagos:
         - PagosGetByIdTool: {"id": int}
         - PagosBuscarPorEstadoTool: {"estado": string}
         - PagosBuscarPorReservaTool: {"reserva_id": string}
         - PagosBuscarPorMonedaTool: {"moneda": string}
         - PagosBuscarPorMontoTool: {"monto": float}
         - PagosBuscarPorFechaTool: {"fecha": "YYYY-MM-DD"}
         - PagosBuscarPorMetodoTool: {"metodo": string}
         - PagosCrearTool: {"pago": { ... objeto PagoCreate ... }}
       Reservas:
         - ReservasGetByIdTool: {"id": int}
         - ReservasBuscarPorUsuarioTool: {"usuario": string}
         - ReservasBuscarPorEstadoTool: {"estado": string}
         - ReservasBuscarPorVueloTool: {"vuelo": string}
         - ReservasContarPorEstadoTool: {"estado": string}
         - ReservasCrearTool: {"reserva": { ... objeto ReservaCreate ... }}
       Mantenimientos:
         - MantenimientosPorAvionTool: {"avion_id": string}
         - MantenimientosPorEstadoTool: {"estado": string}
         - MantenimientosGetByIdTool: {"id": string}
         - MantenimientosCrearTool: {"mantenimiento": { ... objeto MantenimientoCreate ... }}
       Usuarios:
         - UsuarioGetByIdTool: {"id": int}
         - UsuariosPorEmailTool: {"email": string}
         - UsuariosPorCedulaTool: {"cedula": string}
         - EmpleadosPorCargoTool: {"cargo": string}

    5) Si no puedes determinar ninguna herramienta y tampoco sabes qué campos faltan, responde con:
       {"clarify": {"message": "No match", "missing_fields": [], "original_query": "{query}"}}

    Responde SOLO con JSON válido, sin texto adicional.
    Solicitud del usuario: "{query}"
    """
    return query

# --- Utilidad: selección de herramienta desde respuesta del router ---
def _select_tool_from_response(response):
    """Parsea la salida estructurada del router IA y devuelve (tool_instance, clarify_dict).
    Soporta:
    - Selección directa de herramienta (response.tool) de Mirascope
    - JSON en response.content con dos formatos:
      a) [{"name": "NombreClaseDeHerramienta", "arguments": { ... }}]
      b) {"clarify": {"message": str, "missing_fields": [..], "original_query"?: str}}
    """
    try:
        # Selección directa de herramienta (Mirascope)
        if response and getattr(response, "tool", None):
            return response.tool, None
        # Salida JSON estructurada
        if response and getattr(response, "content", None):
            import json as _json
            json_str = response.content.strip()
            data = _json.loads(json_str)
            # Herramienta elegida
            if isinstance(data, list) and data:
                tool_info = data[0]
                tool_name = tool_info.get("name")
                tool_args = tool_info.get("arguments", {})
                if tool_name in TOOL_NAME_TO_CLASS_MAP:
                    tool_class = TOOL_NAME_TO_CLASS_MAP[tool_name]
                    try:
                        return tool_class(**tool_args), None
                    except Exception:
                        return None, None
            # Aclaración solicitada
            if isinstance(data, dict) and "clarify" in data:
                clarify = data.get("clarify")
                if isinstance(clarify, dict):
                    return None, clarify
    except Exception:
        pass
    return None, None

# --- 4. Función Principal de Procesamiento ---
async def process_query(prompt: str, session: ClientSession) -> Dict[str, Any]:
    """
    Router determinista y limpio para el SDK MCP de Python:
    1) Intenta una intención de creación vía parseo mínimo (parse_natural_intent)
    2) Si no hay creación, intenta consultas específicas por dominio (id, estado, etc.)
    3) Fallback a herramientas de listado por dominio
    4) Ejecuta la herramienta vía MCP y retorna resultado estructurado
    """
    try:
        parsed = parse_natural_intent(prompt)
        tool_instance = None
        if parsed:
            tool_class, tool_args = parsed
            try:
                tool_instance = tool_class(**tool_args)
            except Exception:
                tool_instance = None

        # Si no hubo creación, intenta consultas por dominio con filtros específicos
        lower = prompt.lower()
        norm = _parse_normalized_hint(prompt)
        if not tool_instance:
            # --- Pagos ---
            if any(k in lower for k in ["pago", "payment", "amount", "monto"]):
                # Orden de preferencia: id > reserva > estado > moneda > método > fecha > monto
                pid_txt = norm.get("id") or _extract_key(prompt, ["id", "pago", "pago_id"])
                if pid_txt:
                    try:
                        tool_instance = PagosGetByIdTool(id=int("".join([c for c in pid_txt if c.isdigit()])))
                    except Exception:
                        tool_instance = None
                if not tool_instance:
                    rid = norm.get("reserva_id") or _extract_text(prompt, ["reserva", "booking", "reservation", "reserva_id", "res-id"]) or _extract_key(prompt, ["reserva", "booking", "reservation", "reserva_id", "res-id"]) 
                    if rid:
                        tool_instance = PagosBuscarPorReservaTool(reserva_id=rid)
                if not tool_instance:
                    est = norm.get("estado") or _extract_text(prompt, ["estado", "status"]) or _extract_key(prompt, ["estado", "status"]) 
                    if est:
                        tool_instance = PagosBuscarPorEstadoTool(estado=str(est))
                if not tool_instance:
                    mon = norm.get("moneda") or _extract_text(prompt, ["moneda", "currency"]) or _extract_key(prompt, ["moneda", "currency"]) or _detect_currency(prompt)
                    if mon:
                        tool_instance = PagosBuscarPorMonedaTool(moneda=str(mon))
                if not tool_instance:
                    met = norm.get("metodo") or _extract_text(prompt, ["metodo", "método", "method"]) or _extract_key(prompt, ["metodo", "método", "method"]) 
                    if met:
                        tool_instance = PagosBuscarPorMetodoTool(metodo=str(met))
                if not tool_instance:
                    ftxt = norm.get("fecha") or _extract_text(prompt, ["fecha", "date"]) or _extract_key(prompt, ["fecha", "date"]) 
                    if ftxt:
                        fiso = _to_iso_date(str(ftxt)) or str(ftxt)
                        tool_instance = PagosBuscarPorFechaTool(fecha=fiso)
                if not tool_instance:
                    mtxt = norm.get("monto") or _extract_text(prompt, ["monto", "amount"]) or _extract_key(prompt, ["monto", "amount"]) 
                    mval = _parse_amount_text(mtxt) if mtxt else None
                    if mval is not None:
                        tool_instance = PagosBuscarPorMontoTool(monto=mval)
                if not tool_instance:
                    tool_instance = PagosGetAllTool()

            # --- Reservas ---
            elif any(k in lower for k in ["reserva", "booking", "vuelo", "flight"]):
                rid_txt = norm.get("id") or _extract_key(prompt, ["id", "reserva", "reserva_id"]) 
                if rid_txt:
                    try:
                        tool_instance = ReservasGetByIdTool(id=int("".join([c for c in rid_txt if c.isdigit()])))
                    except Exception:
                        tool_instance = None
                if not tool_instance:
                    user = norm.get("usuario") or _extract_text(prompt, ["usuario", "user", "cliente", "customer"]) or _extract_key(prompt, ["usuario", "user", "cliente", "customer"]) 
                    if user:
                        tool_instance = ReservasBuscarPorUsuarioTool(usuario=user)
                if not tool_instance:
                    vuelo = norm.get("vuelo") or _extract_text(prompt, ["vuelo", "flight"]) or _extract_key(prompt, ["vuelo", "flight"]) 
                    if vuelo:
                        tool_instance = ReservasBuscarPorVueloTool(vuelo=vuelo)
                if not tool_instance:
                    est = norm.get("estado") or _extract_text(prompt, ["estado", "status"]) or _extract_key(prompt, ["estado", "status"]) 
                    if est:
                        tool_instance = ReservasBuscarPorEstadoTool(estado=str(est))
                # Contar por estado si el usuario solicita conteo
                if not tool_instance and any(k in lower for k in ["contar", "count", "cuantas", "cuántas"]):
                    est = norm.get("estado") or _extract_text(prompt, ["estado", "status"]) or _extract_key(prompt, ["estado", "status"]) 
                    if est:
                        tool_instance = ReservasContarPorEstadoTool(estado=str(est))
                    else:
                        tool_instance = ReservasContarTool()
                if not tool_instance:
                    tool_instance = ReservasGetAllTool()

            # --- Mantenimientos ---
            elif any(k in lower for k in ["mantenimiento", "maintenance", "repair"]):
                # Creación determinista de mantenimiento si el prompt indica intención de crear
                if any(k in lower for k in ["crear", "create", "nuevo", "registrar", "alta", "agregar", "añadir"]):
                    avion_id = norm.get("avion_id") or _extract_text(prompt, ["avion", "aircraft", "plane", "avion_id"]) or _extract_key(prompt, ["avion", "aircraft", "plane", "avion_id"]) 
                    tipo = norm.get("tipo") or _extract_text(prompt, ["tipo", "type"]) or _extract_key(prompt, ["tipo", "type"]) 
                    descripcion = norm.get("descripcion") or _extract_text(prompt, ["descripcion", "descripción", "description"]) or _extract_key(prompt, ["descripcion", "descripción", "description"]) 
                    fecha_txt = norm.get("fecha") or _extract_text(prompt, ["fecha", "date"]) or _extract_key(prompt, ["fecha", "date"]) 
                    fecha_iso = _to_iso_date(fecha_txt) if fecha_txt else None
                    responsable = norm.get("responsable") or _extract_text(prompt, ["responsable", "technician", "engineer"]) or _extract_key(prompt, ["responsable", "technician", "engineer"]) 
                    costo_txt = norm.get("costo") or _extract_text(prompt, ["costo", "cost"]) or _extract_key(prompt, ["costo", "cost"]) 
                    costo = _parse_amount_text(costo_txt) if costo_txt else None
                    estado = norm.get("estado") or _extract_text(prompt, ["estado", "status"]) or _extract_key(prompt, ["estado", "status"]) or "pendiente"
                    if all([avion_id, tipo, descripcion, responsable]) and costo is not None:
                        tool_instance = MantenimientosCrearTool(mantenimiento={"avion_id": str(avion_id), "tipo": str(tipo), "descripcion": str(descripcion), "fecha": fecha_iso, "responsable": str(responsable), "costo": costo, "estado": estado})

                if not tool_instance:
                    mid = norm.get("id") or _extract_key(prompt, ["id", "mantenimiento", "maint_id"]) 
                    if mid:
                        tool_instance = MantenimientosGetByIdTool(id=str(mid))
                if not tool_instance:
                    aid = norm.get("avion_id") or _extract_text(prompt, ["avion", "aircraft", "plane", "avion_id"]) or _extract_key(prompt, ["avion", "aircraft", "plane", "avion_id"]) 
                    if aid:
                        tool_instance = MantenimientosPorAvionTool(avion_id=str(aid))
                if not tool_instance:
                    est = norm.get("estado") or _extract_text(prompt, ["estado", "status"]) or _extract_key(prompt, ["estado", "status"]) 
                    if est:
                        tool_instance = MantenimientosPorEstadoTool(estado=str(est))
                if not tool_instance:
                    tool_instance = MantenimientosGetAllTool()

            # --- Notificaciones retiradas: microservicio eliminado ---
            # --- Aviones ---
            elif any(k in lower for k in ["avion", "aircraft", "plane", "modelo", "aerolinea", "aerolínea"]):
                aid_txt = norm.get("id") or _extract_key(prompt, ["id", "avion", "avion_id"]) 
                if aid_txt:
                    try:
                        tool_instance = GetAvionByIdTool(avion_id=int("".join([c for c in aid_txt if c.isdigit()])))
                    except Exception:
                        tool_instance = None
                if not tool_instance:
                    est = norm.get("estado") or _extract_text(prompt, ["estado", "status"]) or _extract_key(prompt, ["estado", "status"]) 
                    if est:
                        tool_instance = GetAvionesByEstadoTool(estado=str(est))
                if not tool_instance:
                    aer = norm.get("aerolinea") or _extract_text(prompt, ["aerolinea", "aerolínea", "airline"]) or _extract_key(prompt, ["aerolinea", "aerolínea", "airline"]) 
                    if aer:
                        tool_instance = GetAvionesByAerolineaTool(aerolinea=aer)
                if not tool_instance:
                    ftxt = norm.get("fecha_fabricacion") or _extract_text(prompt, ["fecha_fabricacion", "fecha", "date"]) or _extract_key(prompt, ["fecha_fabricacion", "fecha", "date"]) 
                    if ftxt:
                        fiso = _to_iso_date(str(ftxt)) or str(ftxt)
                        tool_instance = GetAvionesByFechaFabricacionTool(fecha_fabricacion=fiso)
                if not tool_instance:
                    # No hay get_all para aviones. Ofrece conteo total como fallback genérico.
                    tool_instance = GetTotalAvionCountTool()

        target_tool = tool_instance
        if not target_tool:
            return {"status": "no_tool", "message": "No se pudo determinar una herramienta para la consulta."}

        tool_name_on_server = TOOL_MAP.get(type(target_tool))
        if not tool_name_on_server:
            return {"status": "error", "message": f"Herramienta no mapeada en el servidor: {type(target_tool).__name__}"}

        tool_args = {k: v for k, v in target_tool.model_dump().items() if v is not None}
        result = await session.call_tool(tool_name_on_server, arguments=tool_args)
        if result.isError:
            return {"status": "error", "message": f"Error del servidor: {result.content}"}
        return {"status": "success", "data": result.structuredContent or result.content}

    except Exception as e:
        return {"status": "error", "message": f"Error interno del agente: {str(e)}"}


def _extract_key(prompt: str, keys: List[str]) -> Optional[str]:
    import re
    pattern = r"(?:" + "|".join([re.escape(k) for k in keys]) + r")[\s:=-]+([\w#\-_/\.]+)"
    m = re.search(pattern, prompt, flags=re.IGNORECASE)
    return m.group(1) if m else None


def _extract_text(prompt: str, keys: List[str]) -> Optional[str]:
    import re
    boundary_tokens = [
        "tipo", "type", "descripcion", "descripción", "description",
        "fecha", "date", "responsable", "technician", "engineer",
        "estado", "status", "usuario", "user", "cliente", "customer",
        "vuelo", "flight", "asiento", "seat", "metodo", "método", "method",
        "moneda", "currency", "reserva", "booking", "reservation",
        "model", "modelo", "capacity", "capacidad", "aerolinea", "aerolínea", "airline",
        "id", "avion", "aircraft", "plane", "avion_id"
    ]
    keys_pattern = r"(?:" + "|".join([re.escape(k) for k in keys]) + r")"
    boundary_pattern = r"(?=\\b(?:" + "|".join([re.escape(t) for t in boundary_tokens]) + r")\\b|[,;:\\n]|$)"
    pattern = keys_pattern + r"[\\s:=-]+(.+?)" + boundary_pattern
    m = re.search(pattern, prompt, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip()
    legacy_pattern = keys_pattern + r"[\\s:=-]+([^,\\n;]+)"
    m2 = re.search(legacy_pattern, prompt, flags=re.IGNORECASE)
    return m2.group(1).strip() if m2 else None


def _parse_normalized_hint(prompt: str) -> Dict[str, Any]:
    """Parseo mínimo de pistas 'Campos normalizados: k=v'. Mantiene tipos básicos.
    Este helper es opcional y no crítico para el flujo.
    """
    import re
    norm: Dict[str, Any] = {}
    m = re.search(r"Campos normalizados:\s*(.+)", prompt, flags=re.IGNORECASE | re.DOTALL)
    if m:
        for pair in [p.strip() for p in m.group(1).split(",")]:
            if "=" in pair:
                k, v = pair.split("=", 1)
                norm[k.strip().lower()] = v.strip()
    # Normalizar tipos básicos
    for key in ("costo", "monto"):
        if key in norm:
            try:
                norm[key] = float(str(norm[key]).replace(",", "").replace(" ", ""))
            except Exception:
                norm.pop(key)
    if "estado" in norm:
        _map_est = {
            "pendiente": "PENDIENTE",
            "pending": "PENDIENTE",
            "confirmado": "CONFIRMADA",
            "confirmada": "CONFIRMADA",
            "confirm": "CONFIRMADA",
            "cancelado": "CANCELADA",
            "cancelada": "CANCELADA",
            "canceled": "CANCELADA",
            "cancel": "CANCELADA",
        }
        s = str(norm["estado"]).strip()
        norm["estado"] = _map_est.get(s.lower(), s.upper())
    return norm


# --- Helpers de normalización y parseo (mantenibles y documentados) ---

def _to_iso_date(text: Optional[str]) -> Optional[str]:
    """Convierte fechas comunes a formato ISO YYYY-MM-DD de forma defensiva.
    Soporta: YYYY-MM-DD, DD/MM/YYYY, YYYY/MM/DD, DD-MM-YYYY.
    Devuelve None si no puede convertir.
    """
    if not text:
        return None
    import re
    from datetime import datetime
    t = text.strip()
    # Ya ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}$", t):
        return t
    # DD/MM/YYYY
    try:
        if "/" in t:
            try:
                return datetime.strptime(t, "%d/%m/%Y").strftime("%Y-%m-%d")
            except Exception:
                return datetime.strptime(t, "%Y/%m/%d").strftime("%Y-%m-%d")
        if "-" in t:
            return datetime.strptime(t, "%d-%m-%Y").strftime("%Y-%m-%d")
    except Exception:
        return None
    return None


def _parse_amount_text(text: Optional[str]) -> Optional[float]:
    """Extrae un monto flotante desde texto, ignorando símbolos y separadores.
    Ejemplos: "$1.234,56", "USD 1234.56", "1234" -> 1234.56
    """
    if not text:
        return None
    import re
    s = str(text).strip()
    # Elimina moneda y símbolos
    s = re.sub(r"[A-Za-z$€₱₽£¥]", "", s)
    # Normaliza separadores: si hay ambos , y ., asume , mil y . decimal
    if "," in s and "." in s:
        s = s.replace(",", "")
    else:
        # Si solo hay coma, úsala como decimal
        s = s.replace(",", ".")
    s = re.sub(r"\s+", "", s)
    try:
        return float(s)
    except Exception:
        return None


def _detect_currency(text: Optional[str]) -> Optional[str]:
    """Detecta moneda por tokens comunes en el texto. Devuelve código ISO simple.
    "$" -> USD (ambiguo, se puede ajustar por configuración)
    "EUR"/"€" -> EUR, "COP" -> COP, "MXN" -> MXN.
    """
    if not text:
        return None
    lower = str(text).lower()
    if "eur" in lower or "€" in lower:
        return "EUR"
    if "cop" in lower:
        return "COP"
    if "mxn" in lower:
        return "MXN"
    if "pen" in lower:
        return "PEN"
    if "ars" in lower:
        return "ARS"
    if "$" in lower or "usd" in lower or "dolar" in lower or "dólar" in lower:
        return "USD"
    return None


def _normalize_estado_reserva(raw: Optional[str]) -> str:
    """Normaliza estados de reserva a valores canónicos esperados por el backend.
    Entrada libre en ES/EN -> "PENDIENTE" | "CONFIRMADA" | "CANCELADA".
    """
    if not raw:
        return "PENDIENTE"
    s = str(raw).strip().lower()
    if s in ("confirmado", "confirmada", "confirm"):
        return "CONFIRMADA"
    if s in ("pendiente", "pending"):
        return "PENDIENTE"
    if s in ("cancelado", "cancelada", "canceled", "cancel"):
        return "CANCELADA"
    up = str(raw).strip().upper()
    return up if up in ("PENDIENTE", "CONFIRMADA", "CANCELADA") else "PENDIENTE"


def _normalize_canal(value: Optional[str]) -> Optional[str]:
    """Función obsoleta: retorna None siempre."""
    return None


def parse_natural_intent(prompt: str) -> Optional[tuple]:
    """Detecta intenciones de creación y extrae argumentos clave en múltiples idiomas.
    Retorna (ToolClass, args_dict) o None si no puede determinar una creación válida.
    """
    text = prompt.strip()
    lower = text.lower()

    create_markers = ["crear", "crea", "nuevo", "registrar", "alta", "add", "create", "register", "book", "reserva", "booking"]

    # Heurística de dominio por palabras clave
    # Heurística de dominio por palabras clave (sin exigir marcadores de "crear")
    is_reserva = any(k in lower for k in ["reserva", "booking", "book", "vuelo", "flight"])
    is_pago = any(k in lower for k in ["pago", "payment", "amount", "monto"])
    is_avion = any(k in lower for k in ["avion", "aircraft", "plane", "modelo", "aerolinea"])
    is_mant = any(k in lower for k in ["mantenimiento", "maintenance", "repair"])

    try:
        if is_reserva:
            usuario = _extract_text(text, ["usuario", "user", "cliente", "customer"]) or _extract_key(text, ["usuario", "user", "cliente", "customer"]) or ""
            vuelo = _extract_text(text, ["vuelo", "flight"]) or _extract_key(text, ["vuelo", "flight"]) or ""
            asiento = _extract_text(text, ["asiento", "seat", "Numasiento"]) or _extract_key(text, ["asiento", "seat", "Numasiento"]) or ""
            # Fallbacks adicionales: intenta detectar códigos comunes
            import re
            if not vuelo:
                m_v = re.search(r"\b([A-Z]{2,3}\d{2,4})\b", text)
                if m_v:
                    vuelo = m_v.group(1)
            if not asiento:
                m_s = re.search(r"\b(\d{1,2}[A-Z]|[A-Z]\d{1,2})\b", text)
                if m_s:
                    asiento = m_s.group(1)
            if not usuario:
                m_u = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
                if m_u:
                    usuario = m_u.group(0)
            # Limpiar posibles colas de texto pegadas a los campos
            if usuario:
                usuario = usuario.strip().split()[0]
            if vuelo:
                vuelo = vuelo.strip().split()[0]
            if asiento:
                asiento = asiento.strip().split()[0]
            estado_raw = _extract_text(text, ["estado", "status"]) or _extract_key(text, ["estado", "status"]) or "pendiente"
            estado_norm = (estado_raw or "").strip().split()[0].lower()
            if estado_norm in ("confirmado", "confirmada", "confirm"):
                estado = "CONFIRMADA"
            elif estado_norm in ("pendiente", "pending"):
                estado = "PENDIENTE"
            elif estado_norm in ("cancelado", "cancelada", "canceled", "cancel"):
                estado = "CANCELADA"
            else:
                # Si viene ya en el esperado, mantener; si no, por defecto PENDIENTE
                upper = (estado_raw or "").strip().upper()
                estado = upper if upper in ("PENDIENTE", "CONFIRMADA", "CANCELADA") else "PENDIENTE"
            if usuario and vuelo and asiento:
                return (ReservasCrearTool, {"reserva": {"usuario": usuario, "vuelo": vuelo, "estado": estado, "numasiento": asiento}})

        if is_pago:
            import re
            amt_text = _extract_text(text, ["monto", "amount"]) or _extract_key(text, ["monto", "amount"]) or ""
            if not amt_text:
                m_amt = re.search(r"(?P<cur>\$|USD|EUR|COP|MXN|PEN|ARS|BRL|CLP)\s*(?P<val>\d{1,3}([,.]\d{3})*([,.]\d{2})?|\d+)", text, flags=re.IGNORECASE)
                if m_amt:
                    amt_text = m_amt.group("val")
            monto = _parse_amount_text(amt_text) if amt_text else None

            moneda = _extract_text(text, ["moneda", "currency"]) or _extract_key(text, ["moneda", "currency"]) or ""
            if not moneda:
                moneda = _detect_currency(text)

            reserva_id = _extract_text(text, ["reserva", "booking", "reservation", "reserva_id", "res-id"]) or _extract_key(text, ["reserva", "booking", "reservation", "reserva_id", "res-id"]) or ""
            if not reserva_id:
                m_res = re.search(r"(?:reserva(?:_id)?|booking|reservation|res-id)[\s:#-]*([A-Za-z0-9\-]+)", text, flags=re.IGNORECASE)
                if m_res:
                    reserva_id = m_res.group(1)
            metodo = _extract_text(text, ["metodo", "método", "method"]) or _extract_key(text, ["metodo", "método", "method"]) or None
            estado = _extract_text(text, ["estado", "status"]) or _extract_key(text, ["estado", "status"]) or "pendiente"
            from datetime import datetime
            fecha = _extract_text(text, ["fecha", "date"]) or _extract_key(text, ["fecha", "date"]) or None
            fecha_iso = None
            if not fecha:
                fecha_iso = datetime.utcnow().strftime("%Y-%m-%d")
            else:
                try:
                    if "/" in fecha:
                        d, m, y = fecha.split("/")
                        fecha_iso = f"{y}-{int(m):02d}-{int(d):02d}"
                    else:
                        fecha_iso = fecha
                except Exception:
                    fecha_iso = datetime.utcnow().strftime("%Y-%m-%d")
            if monto is not None and moneda and reserva_id:
                return (PagosCrearTool, {"pago": {"monto": monto, "fecha": fecha_iso, "estado": estado, "moneda": moneda, "metodo_pago": metodo, "reserva": reserva_id}})

        if is_avion:
            modelo = _extract_text(text, ["modelo", "model"]) or _extract_key(text, ["modelo", "model"]) or ""
            capacidad_txt = _extract_text(text, ["capacidad", "capacity"]) or _extract_key(text, ["capacidad", "capacity"]) or ""
            try:
                capacidad = int("".join([c for c in capacidad_txt if c.isdigit()])) if capacidad_txt else None
            except Exception:
                capacidad = None
            aerolinea = _extract_text(text, ["aerolinea", "aerolínea", "airline"]) or _extract_key(text, ["aerolinea", "aerolínea", "airline"]) or ""
            estado = _extract_text(text, ["estado", "status"]) or _extract_key(text, ["estado", "status"]) or None
            fecha = _extract_text(text, ["fecha", "date"]) or _extract_key(text, ["fecha", "date"]) or None
            if modelo and capacidad is not None and aerolinea:
                args = {"modelo": modelo, "capacidad": capacidad, "aerolinea": aerolinea}
                if estado: args["estado"] = estado
                if fecha: args["fecha_fabricacion"] = fecha
                return (CreateAvionTool, args)

        if is_mant:
            avion_id = _extract_text(text, ["avion", "aircraft", "plane", "avion_id"]) or _extract_key(text, ["avion", "aircraft", "plane", "avion_id"]) or ""
            tipo = _extract_text(text, ["tipo", "type"]) or _extract_key(text, ["tipo", "type"]) or ""
            descripcion = _extract_text(text, ["descripcion", "descripción", "description"]) or _extract_key(text, ["descripcion", "descripción", "description"]) or ""
            fecha_txt = _extract_text(text, ["fecha", "date"]) or _extract_key(text, ["fecha", "date"]) or None
            fecha_iso = _to_iso_date(fecha_txt)
            responsable = _extract_text(text, ["responsable", "technician", "engineer"]) or _extract_key(text, ["responsable", "technician", "engineer"]) or ""
            costo_txt = _extract_text(text, ["costo", "cost"]) or _extract_key(text, ["costo", "cost"]) or ""
            costo = _parse_amount_text(costo_txt) if costo_txt else None
            estado = _extract_text(text, ["estado", "status"]) or _extract_key(text, ["estado", "status"]) or "pendiente"
            if all([avion_id, tipo, descripcion, responsable]) and costo is not None:
                return (MantenimientosCrearTool, {"mantenimiento": {"avion_id": avion_id, "tipo": tipo, "descripcion": descripcion, "fecha": fecha_iso, "responsable": responsable, "costo": costo, "estado": estado}})

        # Notificaciones retiradas: creación desde lenguaje natural deshabilitada
    except Exception:
        return None

    return None


async def run_agent(prompt: str) -> Dict[str, Any]:
    """Crea una sesión MCP (SSE) y procesa la consulta usando process_query."""
    import os
    mcp_url = os.getenv("MCP_SERVER_URL", "http://localhost:3001/sse")
    async with sse_client(mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await process_query(prompt, session)

