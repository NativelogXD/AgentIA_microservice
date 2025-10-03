"""
# client_mcp.py
Cliente MCP que usa Gemini para decidir qué herramienta llamar en el servidor.

Flujo:
- Recibe un prompt del usuario.
- Llama a Gemini (vía Mirascope) con las herramientas declaradas.
- Si Gemini selecciona una herramienta, mapeamos al nombre del servidor MCP y
  hacemos la llamada por stdio.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
from mirascope import llm, BaseTool
from pydantic import Field
from mcp import ClientSession
from mcp.client.sse import sse_client

load_dotenv()
# --- 1. Definición de Herramientas (Aviones) ---
class GetTotalAvionCountTool(BaseTool):
    """Devuelve el número total de aviones."""
    def call(self) -> str:
        return "Herramienta 'GetTotalAvionCountTool' seleccionada."

class GetAvionByIdTool(BaseTool):
    """Obtiene un avión por ID."""
    avion_id: int = Field(..., description="ID del avión")
    def call(self) -> str:
        return f"Herramienta 'GetAvionByIdTool' seleccionada para {self.avion_id}."

class GetAvionesByEstadoTool(BaseTool):
    """Lista aviones por estado."""
    estado: str = Field(..., description="Estado del avión")
    def call(self) -> str:
        return f"Herramienta 'GetAvionesByEstadoTool' seleccionada para {self.estado}."

class GetAvionesByAerolineaTool(BaseTool):
    """Lista aviones por aerolínea."""
    aerolinea: str = Field(..., description="Aerolínea")
    def call(self) -> str:
        return f"Herramienta 'GetAvionesByAerolineaTool' seleccionada para {self.aerolinea}."

class GetAvionesByFechaFabricacionTool(BaseTool):
    """Lista aviones por fecha de fabricación (YYYY-MM-DD)."""
    fecha_fabricacion: str = Field(..., description="Fecha ISO YYYY-MM-DD")
    def call(self) -> str:
        return f"Herramienta 'GetAvionesByFechaFabricacionTool' seleccionada para {self.fecha_fabricacion}."

class CreateAvionTool(BaseTool):
    """Crea un avión."""
    modelo: str
    capacidad: int
    aerolinea: str
    estado: str | None = None
    fecha_fabricacion: str | None = None
    def call(self) -> str:
        return "Herramienta 'CreateAvionTool' seleccionada."

class UpdateAvionTool(BaseTool):
    """Actualiza parcialmente un avión."""
    avion_id: int
    modelo: str | None = None
    capacidad: int | None = None
    aerolinea: str | None = None
    estado: str | None = None
    fecha_fabricacion: str | None = None
    def call(self) -> str:
        return f"Herramienta 'UpdateAvionTool' seleccionada para {self.avion_id}."

class DeleteAvionTool(BaseTool):
    """Elimina un avión por ID."""
    avion_id: int
    def call(self) -> str:
        return f"Herramienta 'DeleteAvionTool' seleccionada para {self.avion_id}."


# --- 2. Mapeo de Herramientas (aviones) ---
TOOL_NAME_MAP = {
    "GetTotalAvionCountTool": "get_total_avion_count",
    "GetAvionByIdTool": "get_avion_by_id",
    "GetAvionesByEstadoTool": "get_aviones_by_estado",
    "GetAvionesByAerolineaTool": "get_aviones_by_aerolinea",
    "GetAvionesByFechaFabricacionTool": "get_aviones_by_fecha_fabricacion",
    "CreateAvionTool": "create_avion",
    "UpdateAvionTool": "update_avion",
    "DeleteAvionTool": "delete_avion",
}

# --- 3. Función de llamada al LLM ---
@llm.call(
    "google",
    model="gemini-2.5-pro",
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
    Eres un asistente de gestión de aviones que selecciona la herramienta adecuada según la consulta.
    """
    return query

# --- 4. Lógica Principal del Cliente (CORRECCIÓN FINAL) ---
async def main(prompt):
    # Configuración para conexión HTTP al servidor MCP en Docker
    import os
    
    # Obtener configuración de conexión desde variables de entorno
    mcp_host = os.getenv("MCP_HOST", "server-mcp")
    # El servidor MCP se ejecuta en puerto 3001 con HTTP transport
    server_url = f"http://{mcp_host}:3001/mcp/"
    
    print(f"🤖 Cliente Aviones MCP (usando Gemini) iniciado.")
    print(f"🌐 Conectando al servidor MCP en {server_url}")
    print("Ejemplos: 'cuántos aviones hay?', 'avión 5', 'aviones disponibles', 'aviones de LATAM', 'aviones fabricados 2020-01-01', 'crea avión A320 180 LATAM', 'actualiza avión 3 estado mantenimiento', 'elimina avión 4'")

    try:
        async with sse_client(f"http://{mcp_host}:3001/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                try:
                    response = get_user_intent(prompt)
                    
                    if tool := response.tool:
                        # CORRECCIÓN: Extraemos el nombre y los argumentos de la sub-estructura 'tool_call'
                        tool_call_info = tool.tool_call
                        tool_name = tool_call_info.name
                        tool_args = tool_call_info.args

                        # Obtenemos el nombre real de la herramienta en el servidor
                        tool_name_on_server = TOOL_NAME_MAP.get(tool_name)
                        
                        if not tool_name_on_server:
                             print(f"😕 Error: El LLM devolvió una herramienta desconocida: {tool_name}")
                             return f"Error: Herramienta desconocida: {tool_name}"

                        print(f"🧠 LLM decidió llamar a la herramienta '{tool_name_on_server}' con argumentos: {tool_args}")
                        
                        result = await session.call_tool(tool_name_on_server, arguments=tool_args)

                        if result.isError:
                            print(f"Error del servidor: {result.content}")
                            return {"status": "error", "message": result.content}
                        
                        # Normalizar salida (structuredContent o content)
                        output = result.structuredContent if result.structuredContent else result.content
                        try:
                            # Si es un modelo Pydantic, convertir a dict
                            if hasattr(output, "model_dump"):
                                output = output.model_dump()
                            # Si es lista de modelos, convertir cada uno
                            elif isinstance(output, list):
                                output = [o.model_dump() if hasattr(o, "model_dump") else o for o in output]
                            # Si viene envuelto como {"result": ...}, extraerlo
                            elif isinstance(output, dict) and "result" in output:
                                output = output["result"]
                        except Exception as norm_err:
                            print(f"Aviso: no se pudo normalizar la salida ({norm_err}). Devolviendo crudo.")
                        
                        print("Respuesta del servidor normalizada:")
                        return output
                    else:
                        return response.content
                except Exception as e:
                    print(f"Ha ocurrido un error inesperado: {e}")
                    return f"Error inesperado: {e}"
    except Exception as e:
        print(f"Error de conexión al servidor MCP: {e}")
        return f"Error de conexión: {e}"

    print("\n Cliente desconectado. ¡Adiós!")
