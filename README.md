# agente_calendario

Agente conversacional para gestionar eventos del calendario.
Conversational agent to manage calendar events.

Utiliza un modelo de lenguaje (LLM) para interpretar instrucciones en lenguaje natural,
It uses a language model (LLM) to interpret natural language instructions,

genera un JSON con la acción y los parámetros, y ejecuta la operación correspondiente
generates a JSON with the action and parameters, and executes the corresponding operation

sobre el archivo ICS de KOrganizer a través del módulo calendario_ics (su backend).
on the KOrganizer ICS file through the calendario_ics module (its backend).

## Instalación / Installation

```bash
pip install agente_calendario
```

### Con script / With script
```bash

# Copiar el script al directorio donde están los .py
chmod +x install.sh
./install.sh
```

## Dependencias / Dependencies

calendario_ics (se instala automáticamente / installed automatically)

Servidor llama.cpp en ejecución / llama.cpp server running

## Uso / Usage

# Iniciar el agente / Start the agent

```bash

# Usando la dirección y puerto por defecto (127.0.0.1:8082)
calendario-agent
```

```bash
# Especificando host y puerto / Specifying host and port
calendario-agent --host 192.168.1.10 --port 8080
```

## Ejemplo de sesión interactiva / Interactive session example

```bash

$ calendario-agent --host 127.0.0.1 --port 8082
======================================================================
AGENTE CONVERSACIONAL PARA EL CALENDARIO KORGANIZER (con LLM)
======================================================================
Servidor LLM: 127.0.0.1:8082
Escribe instrucciones en lenguaje natural.
Ejemplos:
  - 'Lista los eventos de hoy'
  - 'Agrega una reunión mañana desde las 10:00 hasta las 12:45'
  - 'Elimina el evento con UID agente-123'
  - 'Muestra el evento con UID agente-456'
  - 'Modifica el evento con UID agente-789...'

Escribe 'salir' para terminar.

>>> Lista los eventos de hoy
[*] Enviando petición al LLM...
[*] JSON recibido:
{
  "accion": "list",
  "parametros": {
    "start": "2026-08-05",
    "end": "2026-08-05"
  }
}
[*] Comando equivalente: python calendario_ics.py list --start 2026-08-05 --end 2026-08-05
Eventos en Calendario personal:
  UID: agente-1785259076207415.149974 | Reunión con equipo | 2026-08-05 15:00 -> 2026-08-05 18:43

>>> Agrega una reunión mañana a las 10:00 hasta las 11:30 en la oficina
[*] Enviando petición al LLM...
[*] JSON recibido:
{
  "accion": "add",
  "parametros": {
    "summary": "Reunión en oficina",
    "dtstart": "2026-08-06 10:00",
    "dtend": "2026-08-06 11:30",
    "location": "oficina"
  }
}
[*] Comando equivalente: python calendario_ics.py add --summary "Reunión en oficina" --dtstart "2026-08-06 10:00" --dtend "2026-08-06 11:30" --location "oficina"
Evento agregado con UID: agente-1785259076207415.149974

```

### `LICENSE`

MIT License

Copyright (c) 2026 Reinel G. Paredes

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
