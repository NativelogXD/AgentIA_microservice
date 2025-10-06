"""
# client_mcp.py
Cliente del proyecto que delega toda la lógica en el agente central.

Este cliente evita duplicar definiciones de herramientas y lógica de LLM.
Sólo expone una función `main(prompt)` que llama al agente síncrono `run_agent`.
"""

import sys
import json
import asyncio
from typing import Any, Dict

from ..agent.agent import run_agent


async def main(prompt: str) -> Dict[str, Any]:
    """
    Ejecuta el agente con el prompt dado y retorna el resultado.
    """
    return await run_agent(prompt)


if __name__ == "__main__":
    # Soporta prompt por argumentos o por stdin
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:]).strip()
    else:
        prompt = sys.stdin.read().strip()
    resultado = asyncio.run(main(prompt))
    print(json.dumps(resultado, ensure_ascii=False))
