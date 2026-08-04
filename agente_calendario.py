#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agente conversacional para gestionar eventos del calendario.
Utiliza un modelo de lenguaje (LLM) para interpretar instrucciones en lenguaje natural,
genera un JSON con la acción y los parámetros, y ejecuta la operación correspondiente
sobre el archivo ICS de KOrganizer a través del módulo calendario_ics (su backend).
"""

import os
import sys
import json
import argparse
import re
import requests
from datetime import datetime, timedelta

# Importación de las funciones del módulo de calendario_ics
import calendario_ics as cal

# ============================================================================
# CONFIGURACIÓN DEL SERVIDOR LLM (con argumentos CLI)
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="Agente calendario con LLM")
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

# Tiempo de espera para las peticiones HTTP (None = sin límite)
TIMEOUT_HTTP = None

# Número máximo de mensajes en el historial de conversación (para no saturar el contexto)
MAX_HISTORIAL = 6

# ============================================================================
# HISTORIAL DE CONVERSACIÓN (estado de la sesión)
# ============================================================================

# Lista que almacena los mensajes del sistema y del usuario para mantener el contexto
historial = []

def inicializar_historial():
    """
    Construye el mensaje inicial del sistema con la fecha actual y ejemplos
    de formato de respuesta (JSON). Este mensaje se mantiene al inicio del historial.
    """
    hoy = datetime.now()
    hoy_str = hoy.strftime("%Y-%m-%d")
    manana = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")
    ayer = (hoy - timedelta(days=1)).strftime("%Y-%m-%d")

    # Prompt del sistema: define la estructura esperada del JSON y da ejemplos
    system_prompt = f"""
Hoy es {hoy_str}. Ayer {ayer}. Mañana {manana}.

Responde ÚNICAMENTE con un JSON válido. Ejemplos:

Entrada: "lista los eventos de hoy"
Salida: {{"accion":"list","parametros":{{"start":"{hoy_str}","end":"{hoy_str}"}}}}

Entrada: "agrega un evento para mañana a las 15:00 hasta las 18:00 en la oficina"
Salida: {{"accion":"add","parametros":{{"summary":"Evento en oficina","dtstart":"{manana} 15:00","dtend":"{manana} 18:00","location":"oficina"}}}}

Entrada: "elimina el evento con UID agente-123"
Salida: {{"accion":"delete","parametros":{{"uid":"agente-123"}}}}

Ahora, para la siguiente instrucción, responde solo con el JSON correspondiente.
"""
    global historial
    historial = [{"role": "system", "content": system_prompt}]

# Inicializar el historial al cargar el módulo
inicializar_historial()

# ============================================================================
# CONSULTA AL LLM
# ============================================================================

def consultar_llm(prompt_usuario, max_tokens=30000, temperature=0.3):
    """
    Envía el prompt del usuario al servidor LLM y devuelve la respuesta en texto.
    Los parámetros de generación (max_tokens, temperature) controlan la salida.
    """
    url = f"{BASE_URL}/chat/completions"
    historial.append({"role": "user", "content": prompt_usuario})

    # Recortar el historial si supera el límite, manteniendo el mensaje del sistema
    if len(historial) > MAX_HISTORIAL:
        historial[:] = [historial[0]] + historial[-(MAX_HISTORIAL-1):]

    # Construcción del payload según la API de llama.cpp
    payload = {
        "model": "ignored",          # El modelo se ignora en llama.cpp (se define al levantar el servidor)
        "messages": historial,
        "n_predict": max_tokens,
        "temperature": temperature,
    }
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_HTTP)
        resp.raise_for_status()
        data = resp.json()
        if "choices" in data and data["choices"]:
            msg = data["choices"][0].get("message", {})
            # Se prefiere 'content' o 'reasoning_content' (según el modelo)
            respuesta = msg.get("content", "") or msg.get("reasoning_content", "")
            historial.append({"role": "assistant", "content": respuesta})
            return respuesta
        else:
            return None
    except Exception as e:
        return None

# ============================================================================
# EXTRACCIÓN DEL JSON A PARTIR DE LA RESPUESTA
# ============================================================================

def extraer_json(texto):
    """
    Busca y extrae el primer objeto JSON válido que contenga las claves
    'accion' y 'parametros'. Soporta JSON plano y bloques ```json.
    """
    if not texto:
        return None

    # Búsqueda por balance de llaves (permite anidación)
    start = texto.find('{')
    if start == -1:
        return None

    brace_count = 0
    for i in range(start, len(texto)):
        if texto[i] == '{':
            brace_count += 1
        elif texto[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = texto[start:i+1]
                try:
                    data = json.loads(json_str)
                    if "accion" in data and "parametros" in data:
                        return data
                except:
                    pass
                # Si no es válido, continuar buscando desde el siguiente carácter
                start = i + 1
                brace_count = 0

    # Fallback: buscar bloque con ```json ... ```
    match = re.search(r'```json\s*(\{.*?\})\s*```', texto, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            if "accion" in data and "parametros" in data:
                return data
        except:
            pass
    return None

# ============================================================================
# CONSTRUCCIÓN DEL COMANDO TEXTO PARA MOSTRAR AL USUARIO
# ============================================================================

def construir_comando_texto(data):
    """
    Convierte el JSON de acción/parámetros en un comando de shell equivalente
    para el script calendario_ics.py. Se usa únicamente para información visual.
    """
    accion = data.get("accion")
    params = data.get("parametros", {})

    if accion == "calendars":
        return "python calendario_ics.py calendars"

    elif accion == "list":
        cmd = "python calendario_ics.py list"
        if params.get("start"):
            cmd += f" --start {params['start']}"
        if params.get("end"):
            cmd += f" --end {params['end']}"
        return cmd

    elif accion == "add":
        cmd = f"python calendario_ics.py add --summary \"{params.get('summary', 'Evento')}\""
        if params.get("dtstart"):
            cmd += f" --dtstart \"{params['dtstart']}\""
        if params.get("dtend"):
            cmd += f" --dtend \"{params['dtend']}\""
        if params.get("location"):
            cmd += f" --location \"{params['location']}\""
        if params.get("description"):
            cmd += f" --description \"{params['description']}\""
        return cmd

    elif accion == "delete":
        uid = params.get("uid")
        if not uid:
            return None
        return f"python calendario_ics.py delete {uid}"

    elif accion == "show":
        uid = params.get("uid")
        if not uid:
            return None
        return f"python calendario_ics.py show {uid}"

    elif accion == "modify":
        uid = params.get("uid")
        if not uid:
            return None
        cmd = f"python calendario_ics.py modify {uid}"
        if params.get("summary"):
            cmd += f" --summary \"{params['summary']}\""
        if params.get("dtstart"):
            cmd += f" --dtstart \"{params['dtstart']}\""
        if params.get("dtend"):
            cmd += f" --dtend \"{params['dtend']}\""
        if params.get("location"):
            cmd += f" --location \"{params['location']}\""
        return cmd

    else:
        return None

# ============================================================================
# EJECUTOR DE ACCIÓN: LLAMA A LAS FUNCIONES DEL MÓDULO calendario_ics
# ============================================================================

def ejecutar_accion(data):
    """
    Interpreta el JSON y llama a la función correspondiente de calendario_ics.
    Devuelve el mensaje resultado de la operación.
    """
    accion = data.get("accion")
    params = data.get("parametros", {})

    if accion == "calendars":
        return cal.listar_calendarios()

    elif accion == "list":
        return cal.listar_eventos(
            calendario=params.get("calendar"),
            start=params.get("start"),
            end=params.get("end")
        )

    elif accion == "add":
        evento = {
            'summary': params.get("summary", "Evento"),
            'description': params.get("description", ""),
            'location': params.get("location", ""),
            'priority': params.get("priority", 0),
        }
        if params.get("dtstart"):
            evento['dtstart'] = cal.parsear_fecha_hora(params["dtstart"])
        if params.get("dtend"):
            evento['dtend'] = cal.parsear_fecha_hora(params["dtend"])
        uid, msg = cal.agregar_evento(
            calendario=params.get("calendar"),
            evento=evento
        )
        return msg

    elif accion == "delete":
        uid = params.get("uid")
        if not uid:
            return "Error: falta UID"
        ok, msg = cal.eliminar_evento(uid, calendario=params.get("calendar"))
        return msg

    elif accion == "show":
        uid = params.get("uid")
        if not uid:
            return "Error: falta UID"
        return cal.mostrar_evento(uid, calendario=params.get("calendar"))

    elif accion == "modify":
        uid = params.get("uid")
        if not uid:
            return "Error: falta UID"
        kwargs = {}
        for key in ['summary', 'description', 'dtstart', 'dtend', 'location']:
            if key in params and params[key]:
                if key in ['dtstart', 'dtend']:
                    kwargs[key] = cal.parsear_fecha_hora(params[key])
                else:
                    kwargs[key] = params[key]
        if 'priority' in params:
            kwargs['priority'] = params['priority']
        ok, msg = cal.modificar_evento(uid, calendario=params.get("calendar"), **kwargs)
        return msg

    else:
        return f"Acción no reconocida: {accion}"

# ============================================================================
# BUCLE PRINCIPAL DE INTERACCIÓN
# ============================================================================

def main():
    """
    Bucle infinito que lee instrucciones del usuario, consulta al LLM,
    muestra el JSON y el comando equivalente, y ejecuta la acción.
    """
    print("=" * 70)
    print("AGENTE CONVERSACIONAL PARA EL CALENDARIO KORGANIZER (con LLM)")
    print("=" * 70)
    print("Escribe instrucciones en lenguaje natural.")
    print("Ejemplos:")
    print("  - 'Lista los eventos de hoy'")
    print("  - 'Agrega una reunión mañana desde las 10:00 hasta las 12:45'")
    print("  - 'Elimina el evento con UID agente-123'")
    print("  - 'Muestra el evento con UID agente-456'")
    print("  - 'Modifica el evento con UID agente-789...'")
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

        print("\n[*] Enviando petición al LLM...")
        respuesta = consultar_llm(prompt)
        if not respuesta:
            print("[!] Error en la comunicación con el LLM.")
            continue

        # Extraer el JSON de la respuesta del modelo
        data = extraer_json(respuesta)
        if not data:
            print("[\n!] El LLM no devolvió un JSON válido.")
            print("[DEBUG] Respuesta del LLM:")
            print(respuesta)
            continue

        # Mostrar el JSON interpretado
        print("\n[*] JSON recibido:")
        print(json.dumps(data, indent=2))

        # Construir y mostrar el comando equivalente de calendario_ics
        comando_texto = construir_comando_texto(data)
        if comando_texto:
            print(f"\n[*] Comando equivalente: {comando_texto}\n")
        else:
            print("\n[*] No se pudo construir un comando textual para esta acción.")

        # Ejecutar la acción y mostrar el resultado
        resultado = ejecutar_accion(data)
        print(resultado)

if __name__ == "__main__":
    # Verificar la existencia del módulo calendario_ics antes de iniciar
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "calendario_ics.py")):
        print("Error: No se encuentra calendario_ics.py")
        sys.exit(1)
    main()