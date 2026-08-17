#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2026 Reinel G. Paredes
# 
# Este código está bajo la licencia MIT. Consulte el archivo LICENSE para más detalles.

"""
Agente conversacional para gestionar eventos del calendario.
Utiliza un modelo de lenguaje (LLM) para interpretar instrucciones en lenguaje natural,
genera un JSON con la acción y los parámetros, y ejecuta la operación correspondiente
sobre el archivo ICS del calendario a través del módulo calendario_ics (su backend).
"""

import os
import sys
import json
import argparse
import re
# import requests
import urllib.request
import urllib.error
import logging
from datetime import datetime, timedelta
from pathlib import Path
import calendar

# Importación de las funciones del módulo de calendario_ics
import calendario_ics as cal

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
        # macOS u otros
        log_dir = Path.home() / ".local" / "share" / "calendario_agent" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "calendario_agent.log"

# Configurar logging (archivo + consola)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(get_log_path()),  # Archivo de log
        logging.StreamHandler()               # Consola (sigue viendo mensajes)
    ]
)
logger = logging.getLogger(__name__)

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
MAX_HISTORIAL = 4

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

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia = calendar.day_name[datetime.now().weekday()]

    system_prompt = f"""
    Hoy es {dia} {hoy}

    Eres un asistente que gestiona un calendario. Tienes estas funciones disponibles:

    - **listar_eventos(calendar=None, start=None, end=None)**: Lista eventos en un rango de fechas.
    - **buscar_eventos(fecha=None, start=None, end=None, texto=None, ubicacion=None, hora=None)**: Busca eventos con filtros.
    - **contar_eventos(fecha=None, start=None, end=None, texto=None, ubicacion=None, hora=None)**: Cuenta eventos que coinciden con filtros.
    - **agregar_evento(summary, dtstart, dtend=None, location=None, priority=0, calendar=None)**: Agrega un nuevo evento.
    - **eliminar_por_filtro(fecha=None, start=None, end=None, texto=None, ubicacion=None, hora=None, calendar=None)**: Elimina eventos que coinciden con filtros.
    - **modificar_por_filtro(fecha=None, start=None, end=None, texto=None, ubicacion=None, hora=None, calendar=None, summary=None, description=None, dtstart=None, dtend=None, location=None, priority=None)**: Modifica eventos que coinciden con los filtros.
    - **eliminar_evento(uid, calendar=None)**: Elimina un evento por su UID.
    - **mostrar_evento(uid, calendar=None)**: Muestra detalles de un evento por UID.
    - **modificar_evento(uid, calendar=None, **kwargs)**: Modifica un evento por UID.

    Responde SOLO con un JSON que contenga "accion" (nombre de la función) y "parametros" (diccionario con los argumentos).

    REGLAS:
    - Usa exactamente los nombres de funciones y parámetros descritos. Si no estás seguro, elige la función más parecida, pero no inventes ninguna.
    - Prefiere usar filtros (fecha, texto, ubicación, hora) en lugar de UID cuando sea posible.
    - mostrar_evento y modificar_evento SOLO aceptan uid. No aceptan fecha, texto, ni ningún otro filtro.
    - Si el usuario pide detalles de un evento por fecha, texto o ubicación, usa buscar_eventos primero. Luego, si encuentras un solo evento, puedes mostrar sus detalles con mostrar_evento(uid=...).
    - Si hay múltiples coincidencias al eliminar/modificar, el agente te pedirá que elijas y el usuario pondrá el número de su opción.
    - Los eventos tienen "priority" (0-9). Si el usuario pregunta por el más importante, usa buscar_eventos y luego filtra por mayor priority.
    """
    
    global historial
    historial = [{"role": "system", "content": system_prompt}]

# Inicializar el historial al cargar el módulo
inicializar_historial()

# ============================================================================
# CONSULTA AL LLM
# ============================================================================

def consultar_llm(prompt_usuario, max_tokens=2000, temperature=0.0, guardar_historial=True, system_prompt_override=None):
    """
    Envía el prompt del usuario al servidor LLM y devuelve la respuesta en texto.
    Los parámetros de generación (max_tokens, temperature, guardar_historial) controlan la salida.
    Si guardar_historial es False, no se añade al historial (para formateo de resultados).
    Si system_prompt_override se proporciona, se usa en lugar del system_prompt global.
    """

    # Construir mensajes
    if system_prompt_override is not None:
        # Usar un system_prompt diferente para esta consulta (por ejemplo, para formateo)
        messages = [{"role": "system", "content": system_prompt_override}]
        # Añadir el historial reciente (sin el system original) para mantener contexto
        # Como guardar_historial=False normalmente, no se tiene historial.
        # En formateo, no se necesita historial, solo el prompt del usuario.
        messages.append({"role": "user", "content": prompt_usuario})

    else:
        if guardar_historial:
            historial.append({"role": "user", "content": prompt_usuario})

        # Recortar el historial si supera el límite, manteniendo el mensaje del sistema
        if len(historial) > MAX_HISTORIAL:
            historial[:] = [historial[0]] + historial[-(MAX_HISTORIAL-1):]
        messages = historial

    url = f"{BASE_URL}/chat/completions"
    # Construcción del payload según la API de llama.cpp
    payload = {
        "model": "ignored",          # El modelo se ignora en llama.cpp (se define al levantar el servidor)
        # "messages": historial,
        "messages": messages,
        "n_predict": max_tokens,
        "temperature": temperature,
    }
    # headers = {"Content-Type": "application/json"}
    data_json = json.dumps(payload).encode('utf-8')

    req = urllib.request.Request(
        url,
        data=data_json,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        # resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_HTTP)
        # resp.raise_for_status()
        # data = resp.json()
        with urllib.request.urlopen(req, timeout=TIMEOUT_HTTP) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if "choices" in data and data["choices"]:
            msg = data["choices"][0].get("message", {})
            # Se prefiere 'content' o 'reasoning_content' (según el modelo)
            respuesta = msg.get("content", "") or msg.get("reasoning_content", "")
            if guardar_historial:
                historial.append({"role": "assistant", "content": respuesta})
            return respuesta
        else:
            logger.warning("La respuesta del LLM no contiene 'choices'.")
            return None
    except urllib.error.URLError as e:
        print("Error de red al conectar con el LLM")
        return None
    except Exception as e:
        print("Error inesperado en la consulta al LLM")
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
# EXTRACCIÓN DE JSON GENÉRICO (para formateo de respuestas)
# ============================================================================

def extraer_cualquier_json(texto):
    """
    Busca y extrae el primer objeto JSON válido de cualquier texto.
    No valida que tenga claves específicas; solo devuelve el JSON.
    """
    if not texto:
        return None

    # Búsqueda por balance de llaves
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
                    return json.loads(json_str)
                except:
                    pass
                start = i + 1
                brace_count = 0

    # Fallback: buscar bloque con ```json ... ```
    match = re.search(r'```json\s*(\{.*?\})\s*```', texto, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    return None

# ============================================================================
# EJECUTOR DE ACCIÓN: LLAMA A LAS FUNCIONES DEL MÓDULO calendario_ics
# ============================================================================

def ejecutar_accion(data):
    accion = data.get("accion")
    params = data.get("parametros", {})

    # Mapeo de nombres a funciones
    funciones = {
        "listar_eventos": cal.listar_eventos,
        "buscar_eventos": cal.buscar_eventos,
        "contar_eventos": cal.contar_eventos,  # nueva función que devuelve solo el número
        "agregar_evento": cal.agregar_evento,
        "eliminar_por_filtro": cal.eliminar_por_filtro,
        "modificar_por_filtro": cal.modificar_por_filtro,
        "eliminar_evento": cal.eliminar_evento,
        "mostrar_evento": cal.mostrar_evento,
        "modificar_evento": cal.modificar_evento,
    }

    if accion not in funciones:
        return f"Acción no reconocida: {accion}"

    elif accion == "eliminar_por_filtro":
        filtros = {k: params[k] for k in ["fecha", "hora", "texto", "ubicacion", "start", "end"] if k in params}
        ok, msg, coincidencias = cal.eliminar_por_filtro(
            calendario=params.get("calendar"), 
            filtros=filtros
        )
        if not ok and coincidencias:
            return {
                "mensaje": msg,
                "coincidencias": coincidencias,
                "accion": "delete"
            }
        return msg

    elif accion == "modificar_por_filtro":
        filtros = {k: params[k] for k in ["fecha", "hora", "texto", "ubicacion", "start", "end"] if k in params}
        cambios = params.get("cambios", {})
        ok, msg, coincidencias = cal.modificar_por_filtro(
            calendario=params.get("calendar"),
            filtros=filtros,
            cambios=cambios
        )
        if not ok and coincidencias:
            return {
                "mensaje": msg,
                "coincidencias": coincidencias,
                "accion": "modify",
                "cambios": cambios
            }
        return msg

    # Llamar a la función con los parámetros
    funcion = funciones[accion]
    try:
        resultado = funcion(**params)
        # Si es un tuple (uid, msg), devolver msg
        if isinstance(resultado, tuple) and len(resultado) == 2:
            return resultado[1]
        return resultado
    except Exception as e:
        return f"Error al ejecutar {accion}: {e}"


# ============================================================================
# FORMATEO DE RESPUESTAS CON EL LLM
# ============================================================================

# System prompt alternativo para el formateo conversacional
SYSTEM_PROMPT_FORMATEO = """
Eres un asistente conversacional cubano, amable y cercano. Tu única tarea es redactar respuestas para el usuario basándote en los resultados de las acciones que el sistema ha ejecutado.

No generes comandos, ni acciones, ni JSON con "accion". Solo debes devolver un JSON con una clave "respuesta" que contenga un mensaje en lenguaje natural y no pienses más de 2 veces para responder.

Ejemplo:
Si el sistema te dice: "El evento se agregó correctamente con UID: 123", tu respuesta debe ser:
{"respuesta": "¡Listo! He agregado el evento. ¿Necesitas algo más?"}

Si el sistema te dice: "No se encontraron eventos", tu respuesta debe ser:
{"respuesta": "No encontré ningún evento para esa fecha. ¿Quieres probar con otra?"}

Los eventos tienen "priority" (0-9). Si el usuario pregunta por el más importante, usa buscar_eventos y luego filtra por mayor priority.
Siempre usa un tono cálido y ofrécele ayuda adicional al final.
"""

def formatear_respuesta(resultado, prompt_usuario, accion=None):
    """Formatea un resultado técnico en una respuesta conversacional usando el LLM."""
    logger.info(f"Resultado técnico: {resultado}")
    prompt_formateo = f"""
El usuario pidió: "{prompt_usuario}"
El sistema ejecutó la acción: "{accion if accion else 'desconocida'}"
El resultado obtenido fue: "{resultado}"

Ahora, como asistente conversacional cubano, redacta una respuesta amigable para el usuario. 
Si {resultado} es una lista, ponla sin los UID y muestra los datos más importantes.
Si fue exitoso, confirma con entusiasmo. Si hubo error, explícalo con empatía y sugiere alternativas.
Si no hay eventos, dilo de manera amable.
Termina siempre ofreciendo ayuda adicional (ej: "¿Necesitas algo más?").

Responde SOLO con un JSON que contenga la clave "respuesta".
"""
    # Llamar al LLM con system_prompt alternativo y temperatura 0.0
    respuesta_llm = consultar_llm(
        prompt_formateo, 
        guardar_historial=False, 
        temperature=0.0,
        system_prompt_override=SYSTEM_PROMPT_FORMATEO
    )
    logger.info(f"\nRespuesta del LLM para formateo: {respuesta_llm}")
    if respuesta_llm:
        datos_respuesta = extraer_cualquier_json(respuesta_llm)
        logger.info(f"Datos extraídos: {datos_respuesta}")
        if datos_respuesta and "respuesta" in datos_respuesta:
            return datos_respuesta["respuesta"]
    logger.warning("\nNo se pudo obtener una respuesta formateada del LLM. Usando fallback.")
    return resultado  # fallback

# ============================================================================
# BUCLE PRINCIPAL DE INTERACCIÓN
# ============================================================================

def main():
    """
    Bucle infinito que lee instrucciones del usuario, consulta al LLM,
    muestra el JSON y el comando equivalente, y ejecuta la acción.
    """

    # Variables de contexto para manejar elecciones del usuario
    ultima_lista = []
    ultima_accion = None
    ultimos_cambios = None
    modo_seleccion = False

    print("=" * 70)
    print("AGENTE CONVERSACIONAL PARA GESTIONAR EVENTOS DEL CALENDARIO (con LLM)")
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

        # Si está en modo selección (el usuario eligió un número)
        if modo_seleccion:
            # Intentar extraer un número de la respuesta
            import re
            match = re.search(r'(\d+)', prompt)
            if match:
                indice = int(match.group(1))
                if 1 <= indice <= len(ultima_lista):
                    uid = ultima_lista[indice-1]['uid']
                    if ultima_accion == "delete":
                        data = {"accion": "delete", "parametros": {"uid": uid}}
                    elif ultima_accion == "modify":
                        data = {"accion": "modify", "parametros": {"uid": uid, **ultimos_cambios}}
                    else:
                        print("Lo siento, no puedo procesar esa acción.")
                        modo_seleccion = False
                        ultima_lista = []
                        ultima_accion = None
                        ultimos_cambios = None
                        continue

                    resultado = ejecutar_accion(data)
                    respuesta_formateada = formatear_respuesta(resultado, prompt, ultima_accion)
                    print(respuesta_formateada)
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

        logger.info(f"\nUsuario: {prompt}")   
        print("\n[*] Enviando petición al LLM...\n")
        respuesta = consultar_llm(prompt)
        if not respuesta:
            logger.error("\n[!] Error en la comunicación con el LLM.")
            print("[!] Error en la comunicación con el LLM.\n")
            continue

        # Extraer el JSON de la respuesta del modelo
        data = extraer_json(respuesta)
        if not data:
            logger.error("[\n!] El LLM no devolvió un JSON válido.")
            print("[\n!] El LLM no devolvió un JSON válido.")
            logger.debug(f"\n[DEBUG] Respuesta del LLM: {respuesta}")
            continue

        # Mostrar el JSON interpretado
        logger.info("\n[*] JSON recibido:")
        logger.info(json.dumps(data, indent=2))

        # Ejecutar la acción y mostrar el resultado
        resultado = ejecutar_accion(data)
        # Si el resultado es una lista de "coincidencias" (porque hay múltiples) y "accion"
        if isinstance(resultado, dict) and "coincidencias" in resultado:
            ultima_lista = resultado["coincidencias"]
            ultima_accion = resultado["accion"]
            ultimos_cambios = resultado.get("cambios")
            modo_seleccion = True
            print(resultado["mensaje"])
            for i, ev in enumerate(ultima_lista, 1):
                dtstart = ev['dtstart'].strftime("%Y-%m-%d %H:%M") if isinstance(ev.get('dtstart'), datetime) else "Sin fecha"
                print(f"{i}. {ev['summary']} - {dtstart}")
            print("Responde con el número del evento que quieres procesar.")
            continue

        else:
            respuesta_formateada = formatear_respuesta(resultado, prompt, data.get('accion'))
            print(respuesta_formateada)

if __name__ == "__main__":
    # Verificar la existencia del módulo calendario_ics antes de iniciar
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "calendario_ics.py")):
        logger.error("Error: No se encuentra calendario_ics.py")
        print("Error: No se encuentra calendario_ics.py")
        sys.exit(1)
    main()