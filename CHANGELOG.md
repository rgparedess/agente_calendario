# CHANGELOG - agente_calendario

## [3.0.0] - 2026-08-21

### Added
- **Integración con la librería oficial `openai`**: Uso de `tool_calls` para comunicación con `llama.cpp`.
- **Límite de pasos (`MAX_STEPS`)**: Control de iteraciones (por defecto 15).
- **Detección de repetición**: Bloqueo de llamadas repetidas con los mismos argumentos.
- **Manejo de múltiples `tool_calls` en paralelo**: Procesamiento eficiente de varias herramientas en una misma iteración.
- Se corrigió un error que impedía la ejecución del binario en Windows": si hubo un bug específico relacionado con el empaquetado.

### Changed
- **Estructura del agente**: Reemplazo del JSON manual por `tool_calls` de OpenAI.
- **Prompt del sistema**: Acortado y simplificado.
- **Manejo de selección**: Integración con el bucle principal.

### Fixed
- **`return` prematuro en `consultar_llm`**: Ahora el bucle continúa hasta resolver la solicitud.
- **Fechas `None` al agregar eventos**: Corregido el parseo en el backend.

---

## [2.3.0] - 2026-08-17

### Added
- **Prompt del sistema más corto y flexible**: Descripción funcional de acciones en lugar de ejemplos largos.
- **Soporte para `start` y `end` en `buscar` y `contar`**: Consultas con rango de fechas.

### Changed
- **Reestructuración de `ejecutar_accion`**: Uso de diccionario de mapeo de funciones.
- **Mejora en logs**: Mensajes de depuración más claros.

### Fixed
- **Corrección en `eliminar_por_filtro`**: Devuelve diccionario con `mensaje`, `coincidencias` y `accion`.
- **Error de argumentos en `mostrar_evento`**: Ahora usa `uid` en lugar de `fecha`.

---

## [2.2.0] - 2026-08-16

### Added
- **Función `formatear_respuesta()`**: Conversión de resultados técnicos a respuestas conversacionales.
- **Manejo de múltiples coincidencias**: Lista numerada para selección.
- **Soporte para nuevas acciones JSON**: `search`, `delete-filter`, `modify-filter`.
- **Construcción de comandos equivalentes**: Salida textual para depuración.

### Changed
- **Ajuste del prompt del sistema**: Incluye ejemplos de búsqueda y operaciones por filtros.
- **Mejora en `ejecutar_accion`**: Delegación en nuevas funciones de `calendario_ics`.
- **Logging más detallado**: Registro de operaciones avanzadas.

### Fixed
- **Extracción de JSON**: Soporte más robusto para bloques ```json ... ```.
- **Manejo de errores de red**: Mejora en la captura de excepciones.

---

## [2.1.0] - 2026-08-11

### Added
- **Sistema de logging**: Archivos de log y salida en consola con `StreamHandler`.
- **Registro de errores detallado**: `logger.exception()` para errores de red.
- **Reemplazo de `print` por `logger`**: Mensajes unificados.
- **Timeout fijo**: `TIMEOUT_HTTP = 60` para evitar bloqueos en Windows.

---

## [2.0.0] - 2026-08-11

### Added
- **Soporte multiplataforma**: Linux y Windows.
- **Variable de entorno `CALENDARIO_ICS_DIR`** para rutas personalizadas.
- **Eliminación de dependencia `requests`**: Uso de `urllib.request`.

### Changed
- **Reestructuración del agente**: Mejora en la gestión del historial.

---

## [1.0.1] - 2026-08-07

### Fixed
- **Corrección de nombres en PyPI**: Ajuste en `setup.py`.
- **Mejora en la detección de la ruta de KOrganizer**.

---

## [1.0.0] - 2026-08-07

### Added
- **Lanzamiento inicial**: Agente conversacional con LLM (JSON manual).
- **Soporte para acciones básicas**: `list`, `add`, `delete`, `show`, `modify`.
- **Historial de conversación** para mantener contexto.

---

[3.0.0]: https://github.com/rgparedess/agente_calendario/compare/v2.3.0...v3.0.0
[2.3.0]: https://github.com/rgparedess/agente_calendario/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/rgparedess/agente_calendario/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/rgparedess/agente_calendario/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/rgparedess/agente_calendario/compare/v1.0.1...v2.0.0