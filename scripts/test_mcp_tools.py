import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession

TOOLS = [
    ("Aviones: conteo", "get_total_avion_count", {}),
    ("Pagos: todos", "pagos_get_all", {}),
    ("Reservas: todas", "reservas_get_all", {}),
    ("Mantenimientos: todos", "mantenimientos_get_all", {}),
    ("Usuarios: todos", "usuarios_get_all", {}),
]

async def main():
    async with sse_client('http://localhost:3001/sse') as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for label, tool, args in TOOLS:
                print(f"\n=== {label} -> herramienta '{tool}' ===")
                try:
                    res = await session.call_tool(tool, arguments=args)
                    output = res.structuredContent if res.structuredContent else res.content
                    print(output)
                except Exception as e:
                    print(f"Error llamando {tool}: {e}")

if __name__ == "__main__":
    asyncio.run(main())