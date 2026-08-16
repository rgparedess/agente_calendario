#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2026 Reinel G. Paredes
# 
# Este código está bajo la licencia MIT. Consulte el archivo LICENSE para más detalles.

"""
Módulo para gestionar eventos en archivos .ics del calendario.
Proporciona operaciones CRUD (crear, leer, actualizar, eliminar) sobre eventos
almacenados en archivos iCalendar (.ics) en el directorio del calendario.
Todas las funciones devuelven (bool, str) o (uid, str) según corresponda.
"""

import os
import re
import time
import argparse
from datetime import datetime
import sys
import logging
from pathlib import Path

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

def get_log_path():
    """Devuelve la ruta del directorio de logs según el SO (sin permisos especiales)."""
    if sys.platform.startswith("linux"):
        log_dir = Path.home() / ".local" / "share" / "calendario_agent" / "logs"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        log_dir = Path(appdata) / "calendario_agent" / "logs"
    else:
        # macOS u otros
        log_dir = Path.home() / ".local" / "share" / "calendario_agent" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "calendario_ics.log"

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(get_log_path()),
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN DEL DIRECTORIO DE CALENDARIOS
# ============================================================================

def _obtener_ruta_calendarios():
    """
    Devuelve la ruta al directorio de calendarios según el sistema operativo.
    Prioriza la variable de entorno CALENDARIO_ICS_DIR si está definida.
    """
    # 1. Variable de entorno (sobrescribe cualquier detección automática)
    env_dir = os.getenv("CALENDARIO_ICS_DIR")
    if env_dir:
        return os.path.expanduser(env_dir)

    # 2. Detección automática por SO
    if sys.platform.startswith("linux"):
        # KOrganizer en Linux (KDE)
        return os.path.expanduser("~/.local/share/apps/korganizer/")
    elif sys.platform == "win32":
        # Rainlendar en Windows (versión 2.x)
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            # Ruta principal de Rainlendar (carpeta oculta en el perfil)
            rainlendar_dir = os.path.join(user_profile, ".rainlendar2")
            # Posibles subcarpetas donde pueden estar los .ics
            candidatas = [
                rainlendar_dir,
                os.path.join(rainlendar_dir, "Calendar"),
            ]
            for ruta in candidatas:
                if os.path.exists(ruta) and os.path.isdir(ruta):
                    # Verificar si contiene archivos .ics
                    try:
                        archivos = [f for f in os.listdir(ruta) if f.lower().endswith('.ics')]
                        if archivos:
                            return ruta
                    except:
                        pass
            # Si no hay archivos, devolver la primera que exista
            for ruta in candidatas:
                if os.path.exists(ruta) and os.path.isdir(ruta):
                    return ruta
    else:
        # Otros sistemas.
        return None


# Ruta donde se guardan los archivos .ics (estándar)
CALENDAR_DIR = _obtener_ruta_calendarios()

# ============================================================================
# UTILIDADES DE ARCHIVOS Y CALENDARIOS
# ============================================================================

def obtener_archivos_calendario():
    """
    Devuelve una lista con las rutas completas de todos los archivos .ics
    encontrados en el directorio de calendarios.
    """
    if CALENDAR_DIR is None:
            logger.warning("CALENDAR_DIR es None. No se encontró una ruta de calendarios.")
            return []
    if not os.path.exists(CALENDAR_DIR):
        logger.warning(f"El directorio {CALENDAR_DIR} no existe.")
        return []
    return [os.path.join(CALENDAR_DIR, f) for f in os.listdir(CALENDAR_DIR)
            if f.lower().endswith('.ics')]

def obtener_nombre_calendario(ruta):
    """Devuelve el nombre base del archivo sin extensión (usado como identificador)."""
    return os.path.splitext(os.path.basename(ruta))[0]

def obtener_calendario_por_defecto():
    """
    Devuelve el nombre del primer archivo .ics encontrado, o None si no hay.
    Se usa como calendario predeterminado cuando no se especifica uno.
    """
    archivos = obtener_archivos_calendario()
    return obtener_nombre_calendario(archivos[0]) if archivos else None

def encontrar_calendario(nombre_calendario=None):
    """
    Busca la ruta del archivo .ics correspondiente al nombre de calendario dado.
    Si no se proporciona nombre, usa el calendario por defecto.
    Retorna la ruta completa o None si no se encuentra.
    """
    if nombre_calendario is None:
        nombre_calendario = obtener_calendario_por_defecto()
    if not nombre_calendario:
        return None
    for ruta in obtener_archivos_calendario():
        if obtener_nombre_calendario(ruta) == nombre_calendario:
            return ruta
    return None

def leer_archivo_ics(ruta):
    """Lee el contenido de un archivo .ics y lo retorna como cadena, o None si falla."""
    try:
        with open(ruta, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.exception(f"Error al leer {ruta}")
        return None

def escribir_archivo_ics(ruta, contenido):
    """Escribe el contenido en un archivo .ics (sobrescribe). Retorna True si éxito."""
    try:
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(contenido)
        return True
    except Exception as e:
        logger.exception(f"Error al escribir {ruta}")
        return False

# ============================================================================
# MANEJO DE FECHAS Y GENERACIÓN DE UID
# ============================================================================

def generar_uid():
    """Genera un identificador único para un nuevo evento, con formato 'agente-timestamp.pid'."""
    return f"agente-{int(time.time()*1000000)}.{os.getpid()}"

def convertir_datetime_a_ics(dt):
    """Convierte un objeto datetime a formato ICS (YYYYMMDDTHHMMSS)."""
    return dt.strftime("%Y%m%dT%H%M%S")

def convertir_ics_a_datetime(cadena):
    """
    Convierte una cadena en formato ICS (YYYYMMDD, YYYYMMDDTHHMMSS, YYYYMMDDTHHMM)
    a un objeto datetime. Si hay zona horaria (Z), se elimina (se asume UTC).
    Retorna None si el formato no es reconocido.
    """
    cadena = cadena.strip()
    if cadena.endswith('Z'):
        cadena = cadena[:-1]
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            dt = datetime.strptime(cadena, fmt)
            if fmt == "%Y%m%d":
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt
        except ValueError:
            continue
    return None

def parsear_fecha_hora(cadena, ajustar_end=False):
    """
    Convierte una cadena en formato 'YYYY-MM-DD HH:MM' o 'YYYY-MM-DD' a datetime.
    Si ajustar_end es True y solo se proporciona fecha, se fija la hora a 23:59:59
    para incluir todo el día en filtros de rango.
    """
    if not cadena:
        return None
    try:
        dt = datetime.strptime(cadena, "%Y-%m-%d %H:%M")
        return dt
    except ValueError:
        pass
    try:
        dt = datetime.strptime(cadena, "%Y-%m-%d")
        if ajustar_end:
            dt = dt.replace(hour=23, minute=59, second=59)
        return dt
    except ValueError:
        return None

# ============================================================================
# PARSEO DE EVENTOS (MANEJA LÍNEAS PLEGADAS)
# ============================================================================

def _unfold_lines(texto):
    """
    Normaliza líneas plegadas en iCalendar (líneas que comienzan con espacio o tab
    son continuación de la línea anterior). Devuelve el texto con las líneas unidas.
    """
    lines = texto.splitlines(keepends=True)
    resultado = []
    for line in lines:
        if line and (line[0] in ' \t'):
            if resultado:
                resultado[-1] = resultado[-1].rstrip('\r\n') + line.lstrip(' \t') + '\n'
            else:
                resultado.append(line)
        else:
            resultado.append(line)
    return ''.join(resultado)

def parsear_eventos(ics_text):
    """
    Extrae todos los bloques VEVENT del texto ICS y devuelve una lista de diccionarios,
    cada uno con los campos principales del evento (uid, summary, description,
    dtstart, dtend, location, priority).
    """
    ics_text = _unfold_lines(ics_text)
    eventos = []
    # Dividir el texto en bloques que comienzan con BEGIN:VEVENT
    partes = re.split(r'(?=BEGIN:VEVENT)', ics_text, flags=re.IGNORECASE)
    for parte in partes:
        if not parte.strip().upper().startswith('BEGIN:VEVENT'):
            continue
        # Extraer cada campo mediante expresiones regulares
        uid = re.search(r'^UID:(.+)$', parte, re.MULTILINE | re.IGNORECASE)
        summary = re.search(r'^SUMMARY:(.+)$', parte, re.MULTILINE | re.IGNORECASE)
        description = re.search(r'^DESCRIPTION:(.+)$', parte, re.MULTILINE | re.IGNORECASE)
        dtstart = re.search(r'^DTSTART(?:;[^:]*)?:(.+)$', parte, re.MULTILINE | re.IGNORECASE)
        dtend = re.search(r'^DTEND(?:;[^:]*)?:(.+)$', parte, re.MULTILINE | re.IGNORECASE)
        location = re.search(r'^LOCATION:(.+)$', parte, re.MULTILINE | re.IGNORECASE)
        priority = re.search(r'^PRIORITY:(.+)$', parte, re.MULTILINE | re.IGNORECASE)

        evento = {
            'uid': uid.group(1).strip() if uid else None,
            'summary': summary.group(1).strip() if summary else '',
            'description': description.group(1).strip() if description else '',
            'dtstart': dtstart.group(1).strip() if dtstart else None,
            'dtend': dtend.group(1).strip() if dtend else None,
            'location': location.group(1).strip() if location else '',
            'priority': int(priority.group(1).strip()) if priority else 0,
        }
        # Convertir fechas de texto a datetime
        if evento['dtstart']:
            evento['dtstart'] = convertir_ics_a_datetime(evento['dtstart'])
        if evento['dtend']:
            evento['dtend'] = convertir_ics_a_datetime(evento['dtend'])
        eventos.append(evento)
    return eventos

# ============================================================================
# CONSTRUCCIÓN DE BLOQUE DE EVENTO EN FORMATO ICS
# ============================================================================

def construir_evento_ics(evento, uid=None):
    """
    Genera una cadena con el bloque VEVENT completo a partir de un diccionario.
    Si no se proporciona UID, se genera uno nuevo.
    """
    if uid is None:
        uid = generar_uid()
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"SUMMARY:{evento.get('summary', '')}",
        f"DESCRIPTION:{evento.get('description', '')}",
    ]
    if 'dtstart' in evento and evento['dtstart']:
        if isinstance(evento['dtstart'], datetime):
            lines.append(f"DTSTART:{convertir_datetime_a_ics(evento['dtstart'])}")
        else:
            lines.append(f"DTSTART:{evento['dtstart']}")
    if 'dtend' in evento and evento['dtend']:
        if isinstance(evento['dtend'], datetime):
            lines.append(f"DTEND:{convertir_datetime_a_ics(evento['dtend'])}")
        else:
            lines.append(f"DTEND:{evento['dtend']}")
    if 'location' in evento and evento['location']:
        lines.append(f"LOCATION:{evento['location']}")
    if 'priority' in evento and evento['priority']:
        lines.append(f"PRIORITY:{evento['priority']}")
    lines.append("STATUS:CONFIRMED")
    lines.append("END:VEVENT")
    # Unir con retornos de carro (formato estándar iCalendar)
    return "\r\n".join(lines) + "\r\n"

# ============================================================================
# FUNCIÓN AUXILIAR PARA RECONSTRUIR EL ARCHIVO ICS COMPLETO
# ============================================================================

def _reconstruir_archivo(contenido_original, eventos):
    """
    Reconstruye el contenido ICS a partir de una lista de eventos,
    manteniendo la cabecera y el pie del archivo original.
    Esto asegura que elementos como VTIMEZONE, PRODID, etc., se preserven.
    """
    # Encontrar el primer BEGIN:VEVENT y el último END:VEVENT
    inicio = contenido_original.find('BEGIN:VEVENT')
    fin = contenido_original.rfind('END:VEVENT')
    if inicio == -1 or fin == -1:
        # Si no hay eventos, devolver el contenido original (no debería ocurrir)
        return contenido_original
    # Cabecera: desde el principio hasta justo antes del primer BEGIN:VEVENT
    cabecera = contenido_original[:inicio]
    # Pie: desde justo después del último END:VEVENT hasta el final
    pie = contenido_original[fin + len('END:VEVENT'):]
    # Construir los bloques de los eventos
    bloques = []
    for ev in eventos:
        uid = ev.get('uid')
        bloques.append(construir_evento_ics(ev, uid))
    nuevo_contenido = cabecera + ''.join(bloques) + pie
    return nuevo_contenido

# ============================================================================
# OPERACIONES CRUD
# ============================================================================

def listar_calendarios():
    """Devuelve una cadena con la lista de calendarios disponibles (archivos .ics)."""
    archivos = obtener_archivos_calendario()
    if not archivos:
        msg = f"No se encontraron archivos .ics en {CALENDAR_DIR}. Define la variable de entorno CALENDARIO_ICS_DIR para especificar una ruta personalizada."
        logger.warning(msg)
        return msg
    lines = ["Calendarios disponibles:"]
    for ruta in archivos:
        lines.append(f"  {obtener_nombre_calendario(ruta)} -> {ruta}")
    return "\n".join(lines)

def listar_eventos(calendario=None, start=None, end=None):
    """
    Lista los eventos del calendario especificado (o todos si no se indica).
    Permite filtrar por rango de fechas (start y end).
    Retorna una cadena con la lista formateada.
    """
    archivos = [encontrar_calendario(calendario)] if calendario else obtener_archivos_calendario()
    if not archivos:
        msg = "No se encontraron calendarios."
        logger.warning(msg)
        return msg
    output = []
    for ruta in archivos:
        if not ruta or not os.path.exists(ruta):
            output.append(f"Calendario no encontrado: {ruta}")
            continue
        contenido = leer_archivo_ics(ruta)
        if contenido is None:
            output.append(f"Error al leer {ruta}")
            continue
        eventos = parsear_eventos(contenido)
        # Aplicar filtros de fechas
        if start:
            start_dt = parsear_fecha_hora(start)
            if start_dt:
                eventos = [e for e in eventos if e.get('dtstart') and e['dtstart'] >= start_dt]
        if end:
            end_dt = parsear_fecha_hora(end, ajustar_end=True)
            if end_dt:
                eventos = [e for e in eventos if e.get('dtstart') and e['dtstart'] <= end_dt]
        if not eventos:
            output.append(f"No hay eventos en {ruta} para el rango dado.")
        else:
            output.append(f"Eventos en {obtener_nombre_calendario(ruta)}:")
            for ev in eventos:
                dtstart = ev['dtstart'].strftime("%Y-%m-%d %H:%M") if isinstance(ev.get('dtstart'), datetime) else "Sin fecha"
                dtend = ev['dtend'].strftime("%Y-%m-%d %H:%M") if isinstance(ev.get('dtend'), datetime) else "Sin fecha"
                output.append(f"  UID: {ev['uid']} | {ev['summary']} | {dtstart} -> {dtend}")
    return "\n".join(output)

def agregar_evento(calendario=None, evento=None):
    """
    Agrega un nuevo evento al calendario especificado.
    Retorna (uid, mensaje) o (None, mensaje de error).
    """
    if evento is None:
        evento = {}
    ruta = encontrar_calendario(calendario)
    if not ruta:
        msg = "Calendario no encontrado."
        logger.error(msg)
        return None, msg
    contenido = leer_archivo_ics(ruta)
    if contenido is None:
        msg = f"Error al leer {ruta}"
        logger.error(msg)
        return None, msg
    uid = generar_uid()
    bloque = construir_evento_ics(evento, uid)
    # Insertar el bloque antes del END:VCALENDAR o al final del archivo
    if contenido.strip().endswith("END:VCALENDAR"):
        contenido = contenido.replace("END:VCALENDAR", bloque + "END:VCALENDAR")
    else:
        contenido += "\r\n" + bloque
    if escribir_archivo_ics(ruta, contenido):
        logger.info(f"Evento agregado con UID: {uid}")
        return uid, f"Evento agregado con UID: {uid}"
    msg = "Error al escribir el archivo."
    logger.error(msg)
    return None, msg

def mostrar_evento(uid, calendario=None):
    """
    Busca un evento por su UID y muestra todos sus campos.
    Retorna una cadena con los detalles o un mensaje de no encontrado.
    """
    archivos = [encontrar_calendario(calendario)] if calendario else obtener_archivos_calendario()
    for ruta in archivos:
        if not ruta or not os.path.exists(ruta):
            continue
        contenido = leer_archivo_ics(ruta)
        if contenido is None:
            continue
        for ev in parsear_eventos(contenido):
            if ev.get('uid') == uid:
                lines = ["Detalles del evento:"]
                for k, v in ev.items():
                    if isinstance(v, datetime):
                        v = v.strftime("%Y-%m-%d %H:%M")
                    lines.append(f"  {k}: {v}")
                return "\n".join(lines)
    msg = f"Evento con UID {uid} no encontrado."
    logger.warning(msg)
    return msg

def modificar_evento(uid, calendario=None, **kwargs):
    """
    Modifica un evento existente identificado por su UID.
    Los cambios se especifican como argumentos clave (summary, dtstart, etc.).
    Retorna (True/False, mensaje).
    """
    archivos_a_buscar = []
    if calendario:
        ruta = encontrar_calendario(calendario)
        if not ruta:
            msg = "Calendario no encontrado."
            logger.error(msg)
            return False, msg
        archivos_a_buscar = [ruta]
    else:
        archivos_a_buscar = obtener_archivos_calendario()

    for ruta in archivos_a_buscar:
        contenido = leer_archivo_ics(ruta)
        if contenido is None:
            continue
        eventos = parsear_eventos(contenido)
        encontrado = False
        for ev in eventos:
            if ev.get('uid') == uid:
                encontrado = True
                # Aplicar las modificaciones al diccionario del evento
                for key, value in kwargs.items():
                    if key in ['summary', 'description', 'location']:
                        ev[key] = value
                    elif key in ['dtstart', 'dtend'] and value is not None:
                        ev[key] = value
                    elif key == 'priority':
                        ev[key] = int(value)
                break
        if encontrado:
            # Reconstruir el archivo completo con la lista de eventos modificada
            nuevo_contenido = _reconstruir_archivo(contenido, eventos)
            if escribir_archivo_ics(ruta, nuevo_contenido):
                logger.info(f"Evento {uid} modificado.")
                return True, f"Evento {uid} modificado."
            else:
                msg = "Error al escribir el archivo."
                logger.error(msg)
                return False, msg
    msg = f"Evento con UID {uid} no encontrado."
    logger.warning(msg)
    return False, msg

def eliminar_evento(uid, calendario=None):
    """
    Elimina un evento por su UID.
    Retorna (True/False, mensaje).
    """
    archivos_a_buscar = []
    if calendario:
        ruta = encontrar_calendario(calendario)
        if not ruta:
            msg = "Calendario no encontrado."
            logger.error(msg)
            return False, msg
        archivos_a_buscar = [ruta]
    else:
        archivos_a_buscar = obtener_archivos_calendario()

    for ruta in archivos_a_buscar:
        contenido = leer_archivo_ics(ruta)
        if contenido is None:
            continue
        eventos = parsear_eventos(contenido)
        encontrado = False
        nuevos_eventos = []
        for ev in eventos:
            if ev.get('uid') == uid:
                encontrado = True
                continue  # omitir este evento (eliminarlo)
            nuevos_eventos.append(ev)
        if encontrado:
            # Reconstruir el archivo sin el evento eliminado
            nuevo_contenido = _reconstruir_archivo(contenido, nuevos_eventos)
            if escribir_archivo_ics(ruta, nuevo_contenido):
                logger.info(f"Evento {uid} eliminado.")
                return True, f"Evento {uid} eliminado."
            else:
                msg = "Error al escribir el archivo."
                logger.error(msg)
                return False, msg
    msg = f"Evento con UID {uid} no encontrado."
    logger.warning(msg)
    return False, msg

# ============================================================================
# BÚSQUEDA Y OPERACIONES POR FILTROS (NUEVO EN v2.2.0)
# ============================================================================

def buscar_eventos(calendario=None, fecha=None, hora=None, texto=None, ubicacion=None):
    """
    Busca eventos que coincidan con los filtros proporcionados.
    Retorna una lista de eventos (diccionarios completos).
    """
    archivos = [encontrar_calendario(calendario)] if calendario else obtener_archivos_calendario()
    coincidencias = []
    
    for ruta in archivos:
        if not ruta or not os.path.exists(ruta):
            continue
        contenido = leer_archivo_ics(ruta)
        if contenido is None:
            continue
        for ev in parsear_eventos(contenido):
            # Aplicar filtros
            if fecha:
                dtstart = ev.get('dtstart')
                if isinstance(dtstart, datetime):
                    try:
                        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
                        if dtstart.date() != fecha_obj:
                            continue
                    except ValueError:
                        # Si el formato no es YYYY-MM-DD, intentar con fecha relativa
                        pass
            if hora:
                dtstart = ev.get('dtstart')
                if isinstance(dtstart, datetime):
                    if dtstart.strftime("%H:%M") != hora:
                        continue
            if texto:
                texto_lower = texto.lower()
                if not (texto_lower in ev.get('summary', '').lower() or 
                        texto_lower in ev.get('description', '').lower()):
                    continue
            if ubicacion:
                if ubicacion.lower() not in ev.get('location', '').lower():
                    continue
            coincidencias.append(ev)
    return coincidencias

def eliminar_por_filtro(calendario=None, filtros=None):
    """
    Busca eventos con los filtros y, si hay exactamente uno, lo elimina.
    Retorna (True/False, mensaje, lista_de_coincidencias) si hay más de uno.
    """
    if filtros is None:
        filtros = {}
    coincidencias = buscar_eventos(calendario, **filtros)
    if len(coincidencias) == 0:
        return False, "No se encontraron eventos con esos criterios.", []
    elif len(coincidencias) == 1:
        uid = coincidencias[0]['uid']
        ok, msg = eliminar_evento(uid, calendario)
        return ok, msg, []
    else:
        return False, "Varios eventos coinciden. Elige uno:", coincidencias

def modificar_por_filtro(calendario=None, filtros=None, cambios=None):
    """
    Busca eventos con los filtros y, si hay exactamente uno, lo modifica.
    Retorna (True/False, mensaje, lista_de_coincidencias) si hay más de uno.
    """
    if filtros is None:
        filtros = {}
    if cambios is None:
        cambios = {}
    coincidencias = buscar_eventos(calendario, **filtros)
    if len(coincidencias) == 0:
        return False, "No se encontraron eventos con esos criterios.", []
    elif len(coincidencias) == 1:
        uid = coincidencias[0]['uid']
        ok, msg = modificar_evento(uid, calendario, **cambios)
        return ok, msg, []
    else:
        return False, "Varios eventos coinciden. Elige uno:", coincidencias


# ============================================================================
# INTERFAZ DE LÍNEA DE COMANDOS (argparse)
# ============================================================================

def main():
    """
    Punto de entrada para el uso del módulo como script independiente.
    Proporciona una CLI con subcomandos para cada operación.
    """
    parser = argparse.ArgumentParser(description="Modulo para gestionar eventos del calendario mediante archivos .ics.")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    subparsers.add_parser("calendars", help="Listar calendarios")

    list_parser = subparsers.add_parser("list", help="Listar eventos")
    list_parser.add_argument("--calendar", help="Nombre del calendario")
    list_parser.add_argument("--start", help="Fecha inicio (YYYY-MM-DD)")
    list_parser.add_argument("--end", help="Fecha fin (YYYY-MM-DD)")

    add_parser = subparsers.add_parser("add", help="Agregar evento")
    add_parser.add_argument("--calendar", help="Calendario")
    add_parser.add_argument("--summary", required=True, help="Título")
    add_parser.add_argument("--description", default="", help="Descripción")
    add_parser.add_argument("--dtstart", required=True, help="Inicio (YYYY-MM-DD HH:MM)")
    add_parser.add_argument("--dtend", help="Fin (YYYY-MM-DD HH:MM)")
    add_parser.add_argument("--location", default="", help="Ubicación")
    add_parser.add_argument("--priority", type=int, default=0, help="Prioridad")

    mod_parser = subparsers.add_parser("modify", help="Modificar evento por UID")
    mod_parser.add_argument("uid", help="UID del evento")
    mod_parser.add_argument("--calendar", help="Calendario")
    mod_parser.add_argument("--summary", help="Nuevo título")
    mod_parser.add_argument("--description", help="Nueva descripción")
    mod_parser.add_argument("--dtstart", help="Nuevo inicio")
    mod_parser.add_argument("--dtend", help="Nuevo fin")
    mod_parser.add_argument("--location", help="Nueva ubicación")
    mod_parser.add_argument("--priority", type=int, help="Nueva prioridad")

    del_parser = subparsers.add_parser("delete", help="Eliminar evento por UID")
    del_parser.add_argument("uid", help="UID del evento")
    del_parser.add_argument("--calendar", help="Calendario")

    show_parser = subparsers.add_parser("show", help="Mostrar evento por UID")
    show_parser.add_argument("uid", help="UID del evento")
    show_parser.add_argument("--calendar", help="Calendario")

    search_parser = subparsers.add_parser("search", help="Buscar eventos por filtros")
    search_parser.add_argument("--calendar", help="Nombre del calendario")
    search_parser.add_argument("--date", help="Fecha (YYYY-MM-DD)")
    search_parser.add_argument("--text", help="Texto en título o descripción")
    search_parser.add_argument("--location", help="Ubicación")
    search_parser.add_argument("--time", help="Hora (HH:MM)")

    delete_filter_parser = subparsers.add_parser("delete-filter", help="Eliminar eventos por filtros")
    delete_filter_parser.add_argument("--calendar", help="Nombre del calendario")
    delete_filter_parser.add_argument("--date", help="Fecha (YYYY-MM-DD)")
    delete_filter_parser.add_argument("--text", help="Texto en título o descripción")
    delete_filter_parser.add_argument("--location", help="Ubicación")
    delete_filter_parser.add_argument("--time", help="Hora (HH:MM)")
    delete_filter_parser.add_argument("--force", action="store_true", help="Eliminar sin confirmar si hay múltiples")

    modify_filter_parser = subparsers.add_parser("modify-filter", help="Modificar eventos por filtros")
    modify_filter_parser.add_argument("--calendar", help="Nombre del calendario")
    modify_filter_parser.add_argument("--date", help="Fecha (YYYY-MM-DD)")
    modify_filter_parser.add_argument("--text", help="Texto en título o descripción")
    modify_filter_parser.add_argument("--location", help="Ubicación")
    modify_filter_parser.add_argument("--time", help="Hora (HH:MM)")
    modify_filter_parser.add_argument("--summary", help="Nuevo título")
    modify_filter_parser.add_argument("--description", help="Nueva descripción")
    modify_filter_parser.add_argument("--dtstart", help="Nuevo inicio (YYYY-MM-DD HH:MM)")
    modify_filter_parser.add_argument("--dtend", help="Nuevo fin (YYYY-MM-DD HH:MM)")
    modify_filter_parser.add_argument("--set-location", help="Nueva ubicación")
    modify_filter_parser.add_argument("--priority", type=int, help="Nueva prioridad")

    args = parser.parse_args()

    # Ejecutar la acción correspondiente y mostrar el resultado
    if args.comando == "calendars":
        print(listar_calendarios())

    elif args.comando == "list":
        print(listar_eventos(args.calendar, args.start, args.end))

    elif args.comando == "add":
        evento = {
            'summary': args.summary,
            'description': args.description,
            'location': args.location,
            'priority': args.priority,
        }
        if args.dtstart:
            evento['dtstart'] = parsear_fecha_hora(args.dtstart)
        if args.dtend:
            evento['dtend'] = parsear_fecha_hora(args.dtend)
        uid, msg = agregar_evento(args.calendar, evento)
        print(msg)

    elif args.comando == "modify":
        kwargs = {}
        for key in ['summary', 'description', 'dtstart', 'dtend', 'location']:
            val = getattr(args, key)
            if val is not None:
                if key in ['dtstart', 'dtend']:
                    kwargs[key] = parsear_fecha_hora(val)
                else:
                    kwargs[key] = val
        if args.priority is not None:
            kwargs['priority'] = args.priority
        ok, msg = modificar_evento(args.uid, args.calendar, **kwargs)
        print(msg)

    elif args.comando == "delete":
        ok, msg = eliminar_evento(args.uid, args.calendar)
        print(msg)

    elif args.comando == "show":
        print(mostrar_evento(args.uid, args.calendar))
    
    elif args.comando == "search":
        filtros = {}
        if args.date:
            filtros["fecha"] = args.date
        if args.text:
            filtros["texto"] = args.text
        if args.location:
            filtros["ubicacion"] = args.location
        if args.time:
            filtros["hora"] = args.time
        eventos = buscar_eventos(args.calendar, **filtros)
        if not eventos:
            print("No se encontraron eventos con esos criterios.")
        else:
            print(f"Se encontraron {len(eventos)} eventos:")
            for i, ev in enumerate(eventos, 1):
                dtstart = ev['dtstart'].strftime("%Y-%m-%d %H:%M") if isinstance(ev.get('dtstart'), datetime) else "Sin fecha"
                ubic = f" (Ubicación: {ev.get('location', 'N/A')})" if ev.get('location') else ""
                print(f"{i}. {ev['summary']} - {dtstart}{ubic}")

    elif args.comando == "delete-filter":
        filtros = {}
        if args.date:
            filtros["fecha"] = args.date
        if args.text:
            filtros["texto"] = args.text
        if args.location:
            filtros["ubicacion"] = args.location
        if args.time:
            filtros["hora"] = args.time
        ok, msg, coincidencias = eliminar_por_filtro(args.calendar, filtros)
        if not ok and coincidencias:
            print(msg)
            for i, ev in enumerate(coincidencias, 1):
                dtstart = ev['dtstart'].strftime("%Y-%m-%d %H:%M") if isinstance(ev.get('dtstart'), datetime) else "Sin fecha"
                print(f"{i}. {ev['summary']} - {dtstart}")
            if args.force:
                print("Forzando eliminación de todos...")
                for ev in coincidencias:
                    ok2, msg2 = eliminar_evento(ev['uid'], args.calendar)
                    print(f"  {ev['summary']}: {msg2}")
            else:
                print("Usa --force para eliminar todos o ejecuta delete por UID para uno específico.")
        else:
            print(msg)

    elif args.comando == "modify-filter":
        filtros = {}
        if args.date:
            filtros["fecha"] = args.date
        if args.text:
            filtros["texto"] = args.text
        if args.location:
            filtros["ubicacion"] = args.location
        if args.time:
            filtros["hora"] = args.time

        cambios = {}
        if args.summary:
            cambios["summary"] = args.summary
        if args.description:
            cambios["description"] = args.description
        if args.dtstart:
            cambios["dtstart"] = parsear_fecha_hora(args.dtstart)
        if args.dtend:
            cambios["dtend"] = parsear_fecha_hora(args.dtend)
        if args.set_location:
            cambios["location"] = args.set_location
        if args.priority is not None:
            cambios["priority"] = args.priority
        if not cambios:
            print("Error: no se especificaron cambios.")
            return
        ok, msg, coincidencias = modificar_por_filtro(args.calendar, filtros, cambios)
        if not ok and coincidencias:
            print(msg)
            for i, ev in enumerate(coincidencias, 1):
                dtstart = ev['dtstart'].strftime("%Y-%m-%d %H:%M") if isinstance(ev.get('dtstart'), datetime) else "Sin fecha"
                print(f"{i}. {ev['summary']} - {dtstart}")
            print("El CLI no soporta modificación interactiva. Usa el agente o modifica por UID.")
        else:
            print(msg)

    else:
        print(f"Comando no reconocido: {args.comando}")

if __name__ == "__main__":
    main()