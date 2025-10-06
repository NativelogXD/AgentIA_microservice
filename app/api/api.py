"""
# api.py
API HTTP mínima para invocar al cliente MCP mediante POST /query.

Recibe {"consulta": "..."} y devuelve el resultado directo dentro de la clave 'data'.
"""

from flask import Flask, request
from ..client.client_mcp import main as client_main

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health_check():
    """Endpoint de salud para verificar que el servicio esté funcionando."""
    return {"status": "ok", "service": "AgenteIA"}

@app.route("/query", methods=["POST"])
async def leer_consulta():
    """Endpoint principal: envía la consulta al cliente MCP y retorna su resultado sin modificaciones."""
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict) or "consulta" not in datos:
        # Diagnóstico y fallback: capturar headers y cuerpo bruto e intentar parseo manual
        raw_body = request.get_data(as_text=True)
        content_type = request.headers.get("Content-Type")
        app.logger.warning("[api-mcp] JSON parse fallback: Content-Type=%s, RawBody=%s", content_type, (raw_body[:500] if raw_body else ""))
        try:
            import json
            datos = json.loads(raw_body) if raw_body else None
        except Exception as e:
            app.logger.warning("[api-mcp] Raw JSON parse failed: %s", e)
            return {"error": "El cuerpo de la solicitud debe ser un JSON con la clave 'consulta'"}, 400
        if not isinstance(datos, dict) or "consulta" not in datos:
            return {"error": "El cuerpo de la solicitud debe ser un JSON con la clave 'consulta'"}, 400

    consulta = datos.get("consulta")
    resultado = await client_main(consulta)

    return {"data": resultado}

if __name__ == "__main__":
    app.run(debug=True)