#!/usr/bin/env python3
"""
Script de instalación de dependencias para AgenteIA
Instala las dependencias de manera optimizada y verifica la instalación
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(command, description):
    """Ejecuta un comando y maneja errores"""
    print(f"\n🔄 {description}...")
    try:
        # Usar comillas para manejar espacios en rutas de Windows
        if sys.executable and " " in sys.executable:
            command = command.replace(sys.executable, f'"{sys.executable}"')
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completado")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error en {description}:")
        print(f"   Comando: {command}")
        print(f"   Error: {e.stderr}")
        return False

def main():
    """Función principal de instalación"""
    print("🚀 Iniciando instalación de dependencias para AgenteIA")
    
    # Verificar que estamos en el directorio correcto
    if not Path("pyproject.toml").exists():
        print("❌ Error: No se encontró pyproject.toml. Ejecuta este script desde el directorio raíz del proyecto.")
        sys.exit(1)
    
    # Verificar entorno virtual
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Advertencia: No se detectó un entorno virtual activo.")
        response = input("¿Continuar de todos modos? (y/N): ")
        if response.lower() != 'y':
            print("Instalación cancelada.")
            sys.exit(1)
    
    # Actualizar pip
    if not run_command(f"{sys.executable} -m pip install --upgrade pip", "Actualizando pip"):
        sys.exit(1)
    
    # Instalar dependencias desde pyproject.toml (recomendado)
    if not run_command(f"{sys.executable} -m pip install -e .", "Instalando dependencias desde pyproject.toml"):
        print("⚠️  Instalación desde pyproject.toml falló, intentando con requirements.txt...")
        if not run_command(f"{sys.executable} -m pip install -r requirements.txt", "Instalando desde requirements.txt"):
            print("❌ Error: No se pudieron instalar las dependencias")
            sys.exit(1)
    
    # Verificar imports críticos
    print("\n🔍 Verificando imports críticos...")
    critical_imports = [
        ("app.api", "API module"),
        ("app.client", "Client module"),
        ("app.server", "Server module"),
        ("app.agent", "Agent module"),
        ("flask", "Flask"),
        ("mcp", "MCP"),
        ("mirascope", "Mirascope"),
        ("asyncpg", "AsyncPG"),
    ]
    
    failed_imports = []
    for module, description in critical_imports:
        try:
            __import__(module)
            print(f"✅ {description} - OK")
        except ImportError as e:
            print(f"❌ {description} - FALLO: {e}")
            failed_imports.append(module)
    
    if failed_imports:
        print(f"\n❌ Fallos en imports: {', '.join(failed_imports)}")
        print("Revisa las dependencias y la estructura del proyecto.")
        sys.exit(1)
    
    print("\n🎉 ¡Instalación completada exitosamente!")
    print("\nPróximos pasos:")
    print("1. Ejecutar: docker-compose up -d (para servicios de base de datos)")
    print("2. Probar API: python -m app.api.api")
    print("3. Probar cliente: python -m app.client.client_mcp")

if __name__ == "__main__":
    main()