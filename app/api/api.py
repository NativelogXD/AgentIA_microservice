"""
# api.py
API HTTP mínima para invocar al cliente MCP mediante POST /query.

Recibe {"consulta": "..."} y devuelve la respuesta estructurada del servidor MCP.
"""

from flask import Flask, request, jsonify
import asyncio
import threading
from ..client.client_mcp import main as client_main

app = Flask(__name__)

# Event loop global para manejar operaciones asíncronas
_loop = None
_loop_thread = None

def get_or_create_event_loop():
    """Obtiene o crea un event loop dedicado para operaciones asíncronas."""
    global _loop, _loop_thread
    
    if _loop is None or _loop.is_closed():
        def run_loop():
            global _loop
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
            _loop.run_forever()
        
        _loop_thread = threading.Thread(target=run_loop, daemon=True)
        _loop_thread.start()
        
        # Esperar a que el loop esté listo
        while _loop is None:
            threading.Event().wait(0.01)
    
    return _loop

@app.route("/health", methods=["GET"])
def health_check():
    """Endpoint de salud para verificar que el servicio esté funcionando."""
    return {"status": "ok", "service": "AgenteIA"}

@app.route("/query", methods=["POST"])
def leer_consulta():
    """Endpoint principal: envía la consulta al cliente MCP y retorna su resultado."""
    try:
        datos = request.get_json()
        consulta = datos.get("consulta", "")
        
        if not consulta:
            return {"parametro_recibido": "Error: Consulta vacía"}, 400
        
        # Usar el event loop dedicado
        loop = get_or_create_event_loop()
        future = asyncio.run_coroutine_threadsafe(client_main(consulta), loop)
        resultado = future.result(timeout=30)  # Timeout de 30 segundos
        
        return {"parametro_recibido": resultado}
        
    except asyncio.TimeoutError:
        return {"parametro_recibido": "Error: Timeout en la consulta"}, 408
    except Exception as e:
        return {"parametro_recibido": f"Error interno: {str(e)}"}, 500

if __name__ == "__main__":
    app.run(debug=True)