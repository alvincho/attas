# Retis Financial Intelligence Workspace

## Traducciones

- [English](README.md)
- [繁體中文](README.zh-Hant.md)
- [简体中文](README.zh-Hans.md)
- [Español](README.es.md)
- [Français](README.fr.md)
- [Italiano](README.it.md)
- [Deutsch](README.de.md)
- [日本語](README.ja.md)
- [한국어](README.ko.md)

El objetivo de `attas` es respaldar una red mundial de profesionales financieros conectados. Cada participante puede operar su propio agente, compartir experiencia a través de ese agente y al mismo tiempo proteger su propiedad intelectual. En este modelo, los prompts privados, la lógica de flujo de trabajo, los algoritmos y otros métodos internos permanecen dentro del agente de su propietario. Los demás participantes consumen los resultados y servicios producidos, en lugar de recibir directamente la lógica subyacente.

## Estado

Este repositorio se está desarrollando activamente y sigue evolucionando. Las APIs, los formatos de configuración y los flujos de ejemplo pueden cambiar a medida que los proyectos se dividan, se estabilicen o se empaqueten de forma más formal.

Dos áreas se encuentran especialmente en una fase temprana y es probable que cambien rápidamente mientras están bajo desarrollo activo:

- `prompits.teamwork`
- `phemacast` `BossPulser`

El repositorio público está destinado a:

- desarrollo local
- evaluación
- flujos de trabajo de prototipos
- exploración de arquitectura

Aún no es un producto terminado listo para usar ni una implementación de producción con un solo comando.

## Dónde encaja `attas` para los desarrolladores

Este repositorio tiene tres capas de producto:

- `prompits` es el entorno de ejecución multiagente genérico y la capa de coordinación de Plaza.
- `phemacast` es la capa reutilizable de colaboración de contenido construida sobre `prompits`.
- `attas` es la capa de aplicación financiera construida sobre ambas.

Para los desarrolladores, `attas` es donde debe vivir el trabajo específico de finanzas. Incluye cosas como:

- definiciones, mapeos, catálogos y ejemplos de validación de `Pulse` financieros
- configuraciones de agentes orientadas a finanzas, flujos de agentes personales y orquestación de workflows
- briefings, plantillas de informes y comportamiento del producto para analistas, equipos de tesorería y workflows de inversión
- branding específico de finanzas, valores predeterminados y conceptos orientados al usuario

Si un cambio es reutilizable para la colaboración de contenido en general, probablemente pertenezca a `phemacast`. Si es infraestructura multiagente genérica, probablemente pertenezca a `prompits`. Evite resolver la reutilización importando `attas` en esas capas inferiores.

![attas-3-layers-diagram-1.png](static/images/attas-3-layers-diagram-1.png)

## Dónde encaja `phemacast` para los desarrolladores

`phemacast` es la capa reutilizable de colaboración de contenido entre `prompits` y `attas`. Convierte entradas dinámicas en salidas de contenido estructurado mediante un pequeño conjunto de conceptos de pipeline:

- `Pulse`: una carga útil de entrada dinámica o una instantánea de datos usada durante la generación de contenido. En `phemacast`, un pulse es el dato que llena un binding, una sección o un espacio de plantilla.
- `Pulser`: un agente que obtiene, calcula o expone datos de pulse. Un pulser anuncia los pulses que puede servir y expone endpoints de practice como `get_pulse_data`.
- `Phema`: un plano de contenido estructurado. Describe qué debe producirse, cómo se organiza la salida y qué bindings de pulse son necesarios.
- `Phemar`: un agente que resuelve un `Phema` en una carga útil estática reuniendo datos de pulse de los pulsers e integrando esos datos en la estructura de `Phema`.

El flujo habitual de `phemacast` es:

1. Un creador define o selecciona un `Phema`.
2. Un `Pulser` proporciona las entradas de pulse requeridas por ese `Phema`.
3. Un `Phemar` integra esos valores de pulse en el plano y produce un resultado estructurado.
4. Un `Castr` o un renderizador posterior convierte ese resultado en markdown, JSON, texto, páginas, diapositivas u otros formatos orientados a la audiencia.

Para los desarrolladores, `phemacast` es la capa adecuada para workflows de contenido reutilizables impulsados por pulse, lógica de renderizado compartida, mapeo de contenido respaldado por diagramas y agentes de contenido no específicos de finanzas. Si el concepto es específico de contratos de datos financieros, catálogos financieros o comportamiento de producto financiero, manténgalo en `attas`.

## Conceptos fundamentales del runtime

El modelo multiagente de nivel inferior vive en `prompits` y es reutilizado por `phemacast` y `attas`.

- `Pit`: la unidad de identidad más pequeña. Contiene metadatos como nombre, descripción e información de dirección. En la práctica, los agentes de runtime comparten este modelo de identidad.
- `Practice`: una capacidad montada en un agente. Una practice puede exponer rutas HTTP, admitir ejecución local y publicar metadatos para su descubrimiento.
- `Pool`: el límite de persistencia de un agente. Los pools almacenan elementos como credenciales de Plaza, metadatos de practices descubiertas, memoria local y otros estados persistentes de runtime.
- `Plaza`: el plano de coordinación. Los agentes se registran en Plaza, reciben y renuevan credenciales, publican tarjetas buscables, envían heartbeats, descubren pares y retransmiten mensajes.

Las conexiones entre agentes suelen funcionar así:

1. Un agente comienza con uno o más pools y monta sus practices.
2. Si no es el propio Plaza, se registra en Plaza y recibe un `agent_id` estable, una `api_key` persistente y un bearer token de corta duración.
3. El agente almacena esas credenciales en su pool principal y aparece en el directorio buscable de Plaza.
4. Otros agentes lo encuentran mediante la búsqueda de Plaza usando campos como nombre, rol o practice anunciada.
5. Los agentes se comunican entonces enviando mensajes a través del relay de Plaza y endpoints tipo buzón, o invocando directamente una practice remota con verificación del llamante.

## Inicio rápido de un nuevo clon

Desde un checkout totalmente nuevo:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
bash scripts/public_clone_smoke.sh
```

El script smoke clona el estado del repo confirmado en un directorio temporal, crea su propio virtualenv, instala las dependencias y ejecuta una suite de pruebas enfocada hacia el público. Esta es la aproximación más cercana a lo que un usuario de GitHub descargará realmente.

Si en su lugar desea probar sus últimos cambios locales no confirmados, use:
```bash
attas_smoke --worktree
```

Ese modo copia el árbol de trabajo actual, incluyendo los cambios sin confirmar y los archivos no rastreados que no están ignorados, en el directorio de prueba temporal.

Desde la raíz del repositorio, también puede ejecutar:
```bash
bash attas_smoke
```

Desde cualquier subdirectorio dentro del árbol del repositorio, puede ejecutar:
```bash
bash "$(git rev-parse --show-toplevel)/attas_smoke"
```

Ese lanzador encuentra la raíz del repositorio e inicia el mismo flujo de smoke test. Si creas un enlace simbólico de `attas_smoke` en un directorio de tu `PATH`, también puedes llamarlo como un comando reutilizable desde cualquier lugar y, opcionalmente, configurar `FINMAS_REPO_ROOT` cuando trabajes fuera del árbol del repositorio.

## Inicio rápido local-first

La ruta local más segura hoy en día es el stack de ejemplo de Prompits. No requiere Supabase u otra infraestructura privada, y ahora cuenta con un flujo de arranque local de un solo comando para el stack de escritorio base. El lanzador de Python funciona de forma nativa en Windows, Linux y macOS. Use `python3` en macOS/Linux y `py -3` en Windows:
```bash
python3 -m prompits.cli up desk
```

Esto inicia:

- Plaza en `http://127.0.0.1:8211`
- el worker de referencia en `http://127.0.0.1:8212`
- la interfaz de usuario para el navegador en `http://127.0.0.1:8214/`

También puedes usar el script de envoltura:
```bash
bash run_plaza_local.sh
```

Útiles comandos de seguimiento:
```bash
python3 -m prompits.cli status desk
python3 -m prompits.cli down desk
```

Si necesita el flujo manual antiguo para depurar un solo servicio a la vez:
```bash
python3 -m prompits.create_agent --config prompits/examples/plaza.agent
python3 -m prompits.create_agent --config prompits/examples/worker.agent
python3 -m prompits.create_agent --config prompits/examples/user.agent
```

Si desea la configuración antigua de Plaza con respaldo de Supabase, apunte `PROMPITS_AGENT_CONFIG` a
`attas/configs/plaza.agent` y proporcione las variables de entorno requeridas.

## Política y Auditoría de Práctica Remota

Prompits ahora admite una capa ligera de política y auditoría entre agentes para las llamadas remotas a `UsePractice(...)`. El contrato reside en el JSON de configuración del agente en el nivel superior y solo se consume dentro de `prompits`:
```json
{
  "remote_use_practice_policy": {
    "outbound_default": "allow",
    "inbound_default": "allow",
    "outbound": {
      "deny": [
        { "practice_id": "get_pulse_data", "target_address": "http://127.0.0.1:9999" }
      ]
    },
    "inbound": {
      "allow": [
        { "practice_id": "get_pulse_data", "caller_agent_id": "plaza" }
      ]
    }
  },
  "remote_use_practice_audit": {
    "enabled": true,
    "persist": true,
    "emit_logs": true,
    "table_name": "cross_agent_practice_audit"
  }
}
```

Notas de la política:

- Las reglas `outbound` coinciden con el destino utilizando `practice_id`, `target_agent_id`, `target_name`, `target_address`, `target_role` y `target_pit_type`.
- Las reglas `inbound` coinciden con el llamante utilizando `practice_id`, `caller_agent_id`, `caller_name`, `caller_address`, `auth_mode` y `plaza_url`.
- Las reglas de denegación tienen prioridad; si existe una lista de permitidos, una llamada remota debe coincidir con ella o será rechazada con un error `403`.
- Las filas de auditoría se registran y, cuando el agente tiene un pool, se añaden a la tabla de auditoría configurada con un `request_id` compartido para la correlación entre los eventos de solicitud y resultado.

## Diseño del repositorio
```text
attas/       Capa de aplicación financiera: catálogos de Pulse, briefings, flujos de agentes personales y configuraciones orientadas a finanzas
ads/         Data-service agents, workers, and normalized dataset pipelines
docs/        Project notes and architecture documents
deploy/      Deployment helpers
mcp_servers/ Local MCP server implementations
phemacast/   Dynamic content generation pipeline
prompits/    Core multi-agent runtime and Plaza coordination layer
scripts/     Local helper scripts, including public-clone smoke checks
tests/       Cross-project tests and fixtures
```

## Orientación

- Comience con `prompits/README.md` para el modelo de tiempo de ejecución principal.
- Lea `docs/CONCEPTS_AND_CLASSES.md` para conocer `Pit`, `Practice`, `Pool`, `Plaza` y los detalles del flujo remoto entre agentes.
- Lea `phemacast/README.md` para la capa de canalización de contenido.
- Lea `attas/README.md` para el marco de la red financiera y conceptos de alto nivel.
- Lea `ads/README.md` para los componentes del servicio de datos.

## Estado de los Componentes

| Área | Estado Público Actual | Notas |
| --- | --- | --- |
| `prompits` | Mejor punto de partida | Los ejemplos con enfoque local-first y el runtime principal son el punto de entrada público más sencillo. El paquete `prompits.teamwork` aún está en una fase temprana y puede cambiar rápidamente. |
| `attas` | Público temprano | Los conceptos principales y el trabajo de user-agent son públicos, pero algunos componentes inacabados están ocultos intencionadamente del flujo predeterminado. |
| `phemacast` | Público temprano | El código del pipeline principal es público; algunos componentes de reporte/renderizado aún se están depurando y estabilizando. `BossPulser` todavía está en desarrollo activo. |
| `ads` | Avanzado | Útil para desarrollo e investigación, pero algunos flujos de trabajo de datos requieren una configuración adicional y no son una ruta de primera ejecución. |
| `deploy/` | Solo ejemplos | Los ayudantes de despliegue dependen del entorno y no deben considerarse como una solución de despliegue público pulida. |
| `mcp_servers/` | Código fuente público | Las implementaciones locales de servidores MCP forman parte del árbol de código fuente público. |

## Limitaciones conocidas

- Algunos flujos de trabajo aún asumen variables de entorno opcionales o servicios de terceros.
- `tests/storage/` contiene fixtures útiles, pero todavía mezcla datos de prueba deterministas con un estado de estilo local más mutable de lo que sería un conjunto de fixtures públicos ideal.
- Los scripts de despliegue son ejemplos, no una plataforma de producción compatible.
- El repositorio está evolucionando rápidamente, por lo que algunas configuraciones y límites de módulos pueden cambiar.

## Hoja de ruta

La hoja de ruta pública a corto plazo se encuentra en `docs/ROADMAP.md`.

Las capacidades planificadas de `prompits` incluyen llamadas `UsePractice(...)` autenticadas y con permisos entre agentes, con negociación de costes y gestión de pagos antes de la ejecución.

Las capacidades planificadas de `phemacast` incluyen representaciones de inteligencia humana `Phemar` más ricas, formatos de salida `Castr` más amplios y el refinamiento de `Pulse` generado por IA basado en la retroalimentación, la eficiencia y el coste, además de un soporte de diagramas más amplio en `MapPhemar`.

Las capacidades planificadas de `attas` incluyen flujos de trabajo de inversión y tesorería más colaborativos, modelos de agentes ajustados para profesionales financieros y el mapeo automático de endpoints de API a `Pulse` para proveedores y prestadores de servicios.

## Notas del Repositorio Público

- Se espera que los secretos provengan de variables de entorno y configuraciones locales, no de archivos confirmados.
- Las bases de datos locales, los artefactos del navegador y las instantáneas temporales se excluyen intencionadamente del control de versiones.
- El código fuente actualmente se orienta más a flujos de trabajo de desarrollo local, evaluación y prototipado que a un empaquetado pulido para el usuario final.

## Contribuir

Este es actualmente un repositorio público con un único mantenedor principal. Las Issues y los pull requests son bienvenidos, pero la hoja de ruta y las decisiones de fusión siguen estando dirigidas por el mantenedor por ahora. Consulte `CONTRIBUTING.md` para conocer el flujo de trabajo actual.

## Licencia

Este repositorio está bajo la licencia Apache License 2.0. Consulte `LICENSE` para obtener el texto completo.
