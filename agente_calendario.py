#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2026 Reinel G. Paredes
# 
# Este código está bajo la licencia MIT. Consulte el archivo LICENSE para más detalles.

"""
Agente conversacional para gestionar eventos del calendario.
Utiliza la librería oficial de OpenAI (openai) para comunicarse con el servidor llama.cpp.
El servidor debe emular el endpoint /v1/chat/completions.

El agente usa la funcionalidad de tools (tool_calls) para que el LLM decida
qué función ejecutar y con qué parámetros, en lugar de generar un JSON manualmente.
Esto hace el código más limpio, robusto y fácil de mantener.
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
import calendar

from openai import OpenAI  # Librería oficial de OpenAI

# Importación de las funciones del módulo calendario_ics
import calendario_ics as cal

# Variables para detectar repeticiones
_recent_calls = []   # lista de (nombre, args_json) de las últimas llamadas
MAX_STEPS = 10         # número máximo de iteraciones del agente

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

def get_log_path():
    """Devuelve la ruta del directorio de logs según el SO."""
    if sys.platform.startswith("linux"):
        log_dir = Path.home() / ".local" / "share" / "calendario_agent" / "logs"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        log_dir = Path(appdata) / "calendario_agent" / "logs"
    else:
        log_dir = Path.home() / ".local" / "share" / "calendario_agent" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "calendario_agent.log"

# Configurar logging (archivo + consola)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(get_log_path()),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN DEL SERVIDOR LLM (con argumentos CLI)
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Agente calendario con LLM (usando tool_calls)")
    parser.add_argument(
        "--host",
        help="Dirección del servidor LLM (ej: 127.0.0.1)",
        default=os.getenv("LLAMA_HOST", "127.0.0.1")
    )
    parser.add_argument(
        "--port",
        help="Puerto del servidor LLM (ej: 8082)",
        default=os.getenv("LLAMA_PORT", "8082")
    )
    return parser.parse_args()

args = parse_args()
HOST = args.host
PORT = args.port
BASE_URL = f"http://{HOST}:{PORT}/v1"

# Crear el cliente OpenAI apuntando al servidor local
# La API key no es necesaria para llama.cpp, pero la librería la exige
client = OpenAI(
    base_url=BASE_URL,
    api_key="ignored"  # cualquier valor sirve
)

# Número máximo de mensajes en el historial de conversación (para no saturar el contexto)
MAX_HISTORIAL = 10

# ============================================================================
# DEFINICIÓN DE LAS HERRAMIENTAS (TOOLS) PARA EL LLM
# ============================================================================

# Aquí se definen las herramientas que el LLM podrá usar.
# Cada herramienta tiene un nombre, descripción y un esquema JSON con los parámetros.
# El LLM decide qué herramienta llamar y con qué argumentos.

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "listar_eventos",
            "description": "Lista los eventos del calendario. Permite filtrar por calendario y rango de fechas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."},
                    "start": {"type": "string", "description": "Fecha de inicio (YYYY-MM-DD)."},
                    "end": {"type": "string", "description": "Fecha de fin (YYYY-MM-DD)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_eventos",
            "description": "Busca eventos que coincidan con filtros (fecha, texto, ubicación, hora, rango).",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."},
                    "fecha": {"type": "string", "description": "Fecha exacta (YYYY-MM-DD)."},
                    "start": {"type": "string", "description": "Fecha de inicio del rango (YYYY-MM-DD)."},
                    "end": {"type": "string", "description": "Fecha de fin del rango (YYYY-MM-DD)."},
                    "texto": {"type": "string", "description": "Texto a buscar en título o descripción."},
                    "ubicacion": {"type": "string", "description": "Ubicación del evento."},
                    "hora": {"type": "string", "description": "Hora exacta (HH:MM)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "contar_eventos",
            "description": "Cuenta el número de eventos que coinciden con los filtros.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."},
                    "fecha": {"type": "string", "description": "Fecha exacta (YYYY-MM-DD)."},
                    "start": {"type": "string", "description": "Fecha de inicio del rango (YYYY-MM-DD)."},
                    "end": {"type": "string", "description": "Fecha de fin del rango (YYYY-MM-DD)."},
                    "texto": {"type": "string", "description": "Texto a buscar en título o descripción."},
                    "ubicacion": {"type": "string", "description": "Ubicación del evento."},
                    "hora": {"type": "string", "description": "Hora exacta (HH:MM)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_evento",
            "description": "Agrega un nuevo evento al calendario.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."},
                    "summary": {"type": "string", "description": "Título del evento (obligatorio)."},
                    "description": {"type": "string", "description": "Descripción (opcional)."},
                    "dtstart": {"type": "string", "description": "Inicio (YYYY-MM-DD HH:MM) (obligatorio)."},
                    "dtend": {"type": "string", "description": "Fin (YYYY-MM-DD HH:MM) (opcional)."},
                    "location": {"type": "string", "description": "Ubicación (opcional)."},
                    "priority": {"type": "integer", "description": "Prioridad (0-9) (obligatorio)."}
                },
                "required": ["summary", "dtstart"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mostrar_evento",
            "description": "Muestra los detalles de un evento usando su UID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "UID del evento (obligatorio)."},
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."}
                },
                "required": ["uid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modificar_evento",
            "description": "Modifica un evento existente usando su UID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "UID del evento (obligatorio)."},
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."},
                    "summary": {"type": "string", "description": "Nuevo título."},
                    "description": {"type": "string", "description": "Nueva descripción."},
                    "dtstart": {"type": "string", "description": "Nuevo inicio."},
                    "dtend": {"type": "string", "description": "Nuevo fin."},
                    "location": {"type": "string", "description": "Nueva ubicación."},
                    "priority": {"type": "integer", "description": "Nueva prioridad."}
                },
                "required": ["uid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_evento",
            "description": "Elimina un evento usando su UID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {"type": "string", "description": "UID del evento (obligatorio)."},
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."}
                },
                "required": ["uid"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "eliminar_por_filtro",
            "description": "Elimina eventos que coinciden con filtros. Si hay varios, devuelve una lista para que el usuario elija.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."},
                    "fecha": {"type": "string", "description": "Fecha exacta (YYYY-MM-DD)."},
                    "start": {"type": "string", "description": "Fecha de inicio del rango (YYYY-MM-DD)."},
                    "end": {"type": "string", "description": "Fecha de fin del rango (YYYY-MM-DD)."},
                    "texto": {"type": "string", "description": "Texto en título o descripción."},
                    "ubicacion": {"type": "string", "description": "Ubicación."},
                    "hora": {"type": "string", "description": "Hora exacta (HH:MM)."},
                    "priority": {"type": "integer", "description": "Prioridad (0-9)."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modificar_por_filtro",
            "description": "Modifica eventos que coinciden con filtros. Si hay varios, devuelve una lista para que el usuario elija.",
            "parameters": {
                "type": "object",
                "properties": {
                    "calendar": {"type": "string", "description": "Nombre del calendario (opcional)."},
                    "fecha": {"type": "string", "description": "Fecha exacta (YYYY-MM-DD)."},
                    "start": {"type": "string", "description": "Fecha de inicio del rango (YYYY-MM-DD)."},
                    "end": {"type": "string", "description": "Fecha de fin del rango (YYYY-MM-DD)."},
                    "texto": {"type": "string", "description": "Texto en título o descripción."},
                    "ubicacion": {"type": "string", "description": "Ubicación."},
                    "hora": {"type": "string", "description": "Hora exacta (HH:MM)."},
                    "summary": {"type": "string", "description": "Nuevo título."},
                    "description": {"type": "string", "description": "Nueva descripción."},
                    "dtstart": {"type": "string", "description": "Nuevo inicio."},
                    "dtend": {"type": "string", "description": "Nuevo fin."},
                    "location": {"type": "string", "description": "Nueva ubicación."},
                    "priority": {"type": "integer", "description": "Nueva prioridad."}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_calendarios",
            "description": "Lista los calendarios disponibles.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# Mapeo de nombres de herramientas a funciones reales de calendario_ics
TOOL_FUNCTIONS = {
    "listar_eventos": cal.listar_eventos,
    "buscar_eventos": cal.buscar_eventos,
    "contar_eventos": cal.contar_eventos,
    "agregar_evento": cal.agregar_evento,
    "mostrar_evento": cal.mostrar_evento,
    "modificar_evento": cal.modificar_evento,
    "eliminar_evento": cal.eliminar_evento,
    "eliminar_por_filtro": cal.eliminar_por_filtro,
    "modificar_por_filtro": cal.modificar_por_filtro,
    "listar_calendarios": cal.listar_calendarios,
}

# ============================================================================
# FUNCIÓN CONSULTAR LLM (CON TOOL_CALLS)
# ============================================================================

def consultar_llm(prompt_usuario):
    """
    Envía el prompt del usuario al LLM y maneja las tool_calls.
    Retorna la respuesta final del asistente o un diccionario con coincidencias.
    """

    global _recent_calls
    
    # Construir el historial de mensajes
    # Añadir el mensaje del usuario al historial
    historial.append({"role": "user", "content": prompt_usuario})
    # Recortar historial para no exceder el contexto
    if len(historial) > MAX_HISTORIAL:
        historial[:] = [historial[0]] + historial[-(MAX_HISTORIAL-1):]

    # Bucle principal del agente (con límite de pasos)
    for step in range(MAX_STEPS):
        logger.info(f"Paso {step+1}/{MAX_STEPS}")
        logger.debug(f"Historial en paso {step+1}: {json.dumps(historial, indent=2)}")

        # Llamar al LLM con las herramientas
        try:
            response = client.chat.completions.create(
                model="ignored",           # El modelo se define en el servidor
                messages=historial,
                tools=TOOLS,
                tool_choice="auto",        # El LLM decide si llama a una herramienta
                temperature=0.3,
                max_tokens=2000            # Límite para la respuesta
            )
        except Exception as e:
            logger.exception(f"Error al llamar al LLM en paso {step+1}: {e}")
            return f"Error en el paso {step+1}: {e}"

        # Extraer el mensaje del asistente
        message = response.choices[0].message
        # Guardar el mensaje del asistente en el historial (si no es system_prompt_override)
        historial.append(message.model_dump())

        # Si el asistente no ha llamado a ninguna herramienta, su mensaje es la respuesta final
        if not message.tool_calls:
            if message.content:
                return message.content
            else:
                # Si no hay contenido y no hay tool_calls, el LLM no sabe qué hacer
                # Que intente de nuevo o dar un mensaje genérico
                historial.append({"role": "user", "content": "La respuesta anterior no fue clara. Intenta resolverlo de otra manera."})
                continue  # forzar siguiente iteración

        # Si el asistente llamó a herramientas, ejecutarlas y repetir
        for call in message.tool_calls:
            tool_name = call.function.name
            tool_args = json.loads(call.function.arguments)
            args_json_str = json.dumps(tool_args, sort_keys=True)
            signature = (tool_name, args_json_str)
            logger.info(f"Herramienta llamada: {tool_name} con argumentos: {tool_args}")

            # --- DETECCIÓN DE REPETICIÓN ---
            # Si la misma llamada aparece 2 veces en las últimas 3, la bloqueamos
            if _recent_calls.count(signature) >= 2:
                result = "Parece que esta llamada se repite. Intenta con otra acción o da una respuesta final."
                logger.warning(f"Repetición detectada: {signature}")
                historial.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result
                })

                continue  # saltar esta llamada

            # Registrar la llamada actual
            _recent_calls.append(signature)

            # Obtener la función correspondiente
            func = TOOL_FUNCTIONS.get(tool_name)
            if not func:
                result = f"Error: Herramienta '{tool_name}' no reconocida."
            else:
                try:
                    # Ejecutar la función con los argumentos recibidos
                    result = func(**tool_args)
                    # Si el resultado es una tupla (uid, msg), extraer solo el mensaje
                    if isinstance(result, tuple) and len(result) == 2:
                        result = result[1]
                    # Si el resultado es un diccionario con 'coincidencias', se maneja de forma especial
                    if isinstance(result, dict) and "coincidencias" in result:
                        # Devolvemos el resultado al main para que el usuario elija
                        return result
                except Exception as e:
                    result = f"Error al ejecutar {tool_name}: {e}"
                    logger.exception(f"Error al ejecutar {tool_name}")

            # Añadir el resultado de la herramienta como mensaje 'tool'
            tool_msg = {
                "role": "tool",
                "tool_call_id": call.id,
                "content": str(result)
            }
            historial.append(tool_msg)

        # Si se agota el número de pasos
    return "Límite de pasos del agente alcanzado. No se pudo resolver la solicitud."

# ============================================================================
# BUCLE PRINCIPAL DE INTERACCIÓN
# ============================================================================

def main():
    """
    Bucle infinito que lee instrucciones del usuario, consulta al LLM,
    y maneja la selección cuando hay múltiples coincidencias.
    """
    global historial

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia = calendar.day_name[datetime.now().weekday()]

    # Variables de contexto para manejar elecciones del usuario
    ultima_lista = []
    ultima_accion = None
    ultimos_cambios = None
    modo_seleccion = False

    # Inicializar el historial de conversación con el mensaje del sistema
    system_prompt = f"""
Eres un asistente amable y conversacional para gestionar un calendario.
Tienes acceso a varias herramientas para listar, buscar, agregar, modificar y eliminar eventos.
Usa las herramientas cuando sea necesario para cumplir con la solicitud del usuario.
Cuando el usuario pregunte por el evento más importante, busca la mayor prioridad.
Siempre antes de eliminar confirma primero con el usuario.
Si te falta un dato, pregunta al usuario
Si varios eventos coinciden, muestralos y pregunta sobre cual se quiere realizar la accion.
Siempre ofrece respuestas claras y útiles, y ofrece ayuda adicional al final.
Hoy es {dia} {hoy}
"""
    historial = [{"role": "system", "content": system_prompt}]

    print("=" * 70)
    print("AGENTE de IA CONVERSACIONAL PARA GESTIONAR EVENTOS DEL CALENDARIO")
    print("=" * 70)
    print("Escribe instrucciones en lenguaje natural.")
    print("Ejemplos:")
    print("  - 'Lista los eventos de hoy'")
    print("  - '¿Cuántos eventos tengo para el 25 de julio?'")
    print("  - 'Agrega una reunión mañana desde las 10:00 hasta las 12:45'")
    print("  - 'Borra el evento con UID agente-123'")
    print("  - 'Elimina la reunión de mañana a las 10:00'")
    print("  - 'Dime los eventos de esta semana'")
    print("  - 'Cambia la reunión del jueves las 10:00 y ponla de las 11:00 a las 12:00'")
    print("\nEscribe 'salir' para terminar.\n")

    while True:
        try:
            prompt = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            break

        if not prompt:
            continue
        if prompt.lower() in ("salir", "exit", "quit"):
            print("\n¡Hasta luego!")
            break

        # =======================================================
        # MODO SELECCIÓN (el usuario eligió un número)
        # =======================================================
        if modo_seleccion:
            import re
            match = re.search(r'(\d+)', prompt)
            if match:
                indice = int(match.group(1))
                if 1 <= indice <= len(ultima_lista):
                    uid = ultima_lista[indice-1]['uid']
                    # Ejecutar la acción correspondiente (delete o modify) directamente
                    if ultima_accion == "delete":
                        # Llamar a eliminar_evento con el UID
                        ok, msg = cal.eliminar_evento(uid, calendar=None)
                        if ok:
                            print(f"Evento con UID {uid} eliminado.")
                        else:
                            print(f"Error al eliminar: {msg}")
                    elif ultima_accion == "modify":
                        # Llamar a modificar_evento con el UID y los cambios guardados
                        ok, msg = cal.modificar_evento(uid, calendar=None, **ultimos_cambios)
                        if ok:
                            print(f"Evento con UID {uid} modificado.")
                        else:
                            print(f"Error al modificar: {msg}")
                    else:
                        print("Acción no soportada en modo selección.")
                    # Resetear modo selección
                    modo_seleccion = False
                    ultima_lista = []
                    ultima_accion = None
                    ultimos_cambios = None
                    continue
                else:
                    print(f"Número inválido. Elige entre 1 y {len(ultima_lista)}.")
                    continue
            else:
                print("Por favor, responde con el número del evento que quieres procesar.")
                continue

        # =======================================================
        # FLUJO NORMAL: Consultar al LLM
        # =======================================================
        logger.info(f"\nUsuario: {prompt}")
        print("\n[*] Enviando petición al LLM...\n")

        # Llamar al LLM y obtener el resultado (puede ser un dict con coincidencias)
        resultado = consultar_llm(prompt)

        # Si el resultado es un diccionario con 'coincidencias', entramos en modo selección
        if isinstance(resultado, dict) and "coincidencias" in resultado:
            ultima_lista = resultado["coincidencias"]
            ultima_accion = resultado.get("accion", "delete")  # por defecto delete
            ultimos_cambios = resultado.get("cambios", {})
            modo_seleccion = True
            print(resultado.get("mensaje", "Varios eventos coinciden. Elige uno:"))
            for i, ev in enumerate(ultima_lista, 1):
                dtstart = ev['dtstart'].strftime("%Y-%m-%d %H:%M") if isinstance(ev.get('dtstart'), datetime) else "Sin fecha"
                print(f"{i}. {ev['summary']} - {dtstart}")
            print("Responde con el número del evento que quieres procesar.")
            continue

        # Si el resultado es un string, es la respuesta final del asistente
        if isinstance(resultado, str):
            print(resultado)
        else:
            # Fallback (no debería ocurrir)
            print(str(resultado))

if __name__ == "__main__":
    main()