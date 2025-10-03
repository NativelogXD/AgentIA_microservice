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
from typing import Dict, Any, Optional

from mirascope import llm, BaseTool
from pydantic import Field, ValidationError
from mcp import ClientSession

# --- 1. Definición de Herramientas (Aviones) ---
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

class UpdateAvionTool(BaseTool):
    """Actualiza un avión parcialmente."""
    avion_id: int
    modelo: Optional[str] = None
    capacidad: Optional[int] = None
    aerolinea: Optional[str] = None
    estado: Optional[str] = None
    fecha_fabricacion: Optional[str] = None
    def call(self) -> str: return f"Herramienta 'UpdateAvionTool' seleccionada para avión {self.avion_id}."

class DeleteAvionTool(BaseTool):
    """Elimina un avión por ID."""
    avion_id: int
    def call(self) -> str: return f"Herramienta 'DeleteAvionTool' seleccionada para avión {self.avion_id}."

# --- 2. Mapeos de Herramientas ---
TOOL_MAP = {
    GetTotalAvionCountTool: "get_total_avion_count",
    GetAvionByIdTool: "get_avion_by_id",
    GetAvionesByEstadoTool: "get_aviones_by_estado",
    GetAvionesByAerolineaTool: "get_aviones_by_aerolinea",
    GetAvionesByFechaFabricacionTool: "get_aviones_by_fecha_fabricacion",
    CreateAvionTool: "create_avion",
    UpdateAvionTool: "update_avion",
    DeleteAvionTool: "delete_avion",
}
TOOL_NAME_TO_CLASS_MAP = {cls.__name__: cls for cls in TOOL_MAP.keys()}

# --- 3. Función de llamada al LLM ---
@llm.call(
    "ollama",
    model="mistral",
    tools=[
        GetTotalAvionCountTool,
        GetAvionByIdTool,
        GetAvionesByEstadoTool,
        GetAvionesByAerolineaTool,
        GetAvionesByFechaFabricacionTool,
        CreateAvionTool,
        UpdateAvionTool,
        DeleteAvionTool,
    ],
)
def get_user_intent(query: str):
    """
    Tu única función es convertir la solicitud del usuario en una llamada a herramienta en formato JSON.
    Responde ÚNICAMENTE con el objeto JSON de la llamada a la herramienta.
    NO incluyas explicaciones, texto adicional, ni formato markdown como ```.

    Solicitud del usuario: "{query}"
    """
    return query

# --- 4. Función Principal de Procesamiento ---
async def process_query(prompt: str, session: ClientSession) -> Dict[str, Any]:
    """
    Toma un prompt, lo procesa con el LLM, llama a la herramienta MCP y devuelve el resultado.
    """
    tool_to_call = None
    try:
        response = get_user_intent(prompt)
        
        if response.tool:
            tool_to_call = response.tool
        
        elif response.content:
            try:
                json_str = response.content.strip()
                if json_str.startswith('["name":'):
                    json_str = '[{' + json_str[1:]
                tool_data = json.loads(json_str)
                if isinstance(tool_data, list) and tool_data:
                    tool_info = tool_data[0]
                    tool_name = tool_info.get("name")
                    tool_args = tool_info.get("arguments", {})
                    if tool_name in TOOL_NAME_TO_CLASS_MAP:
                        tool_class = TOOL_NAME_TO_CLASS_MAP[tool_name]
                        tool_to_call = tool_class(**tool_args)
            except (json.JSONDecodeError, ValidationError, KeyError, IndexError):
                pass

        if tool_to_call:
            tool_name_on_server = TOOL_MAP.get(type(tool_to_call))
            tool_args = {k: v for k, v in tool_to_call.model_dump().items() if v is not None}
            
            print(f"🧠 LLM -> Herramienta: '{tool_name_on_server}', Args: {tool_args}")
            
            result = await session.call_tool(tool_name_on_server, arguments=tool_args)

            if result.isError:
                return {"status": "error", "message": f"Error del servidor: {result.content}"}
            else:
                return {"status": "success", "data": result.structuredContent or result.content}
        else:
            return {"status": "no_tool", "message": f"No se pudo determinar una herramienta. Respuesta del LLM: {response.content}"}

    except Exception as e:
        print(f"Ha ocurrido un error inesperado en el agente: {e}")
        return {"status": "error", "message": f"Error interno del agente: {str(e)}"}

