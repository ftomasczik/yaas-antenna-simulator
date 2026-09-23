# Fase 2 — Proyectos AntSim

## Estado

Completada.

## Objetivo

Incorporar un formato de proyecto propio y permitir que la CLI valide,
simule y realice barridos sin depender de geometrías incorporadas
directamente en el código.

## Capacidades implementadas

### Formato de proyecto

- Archivos JSON con extensión `.antsim`.
- Versión de esquema explícita.
- Metadatos con nombre y descripción.
- Geometría formada por conductores.
- Fuente de tensión.
- Frecuencia de simulación.
- Impedancia de referencia.
- Configuración de barrido.
- Lectura y escritura con codificación UTF-8.
- Validación del contenido al cargar el archivo.

### API de proyectos

El modelo `AntennaProject` puede convertirse en:

- `SimulationRequest` mediante `to_simulation_request()`.
- `SweepRequest` mediante `to_sweep_request()`.

La capa de proyectos permanece separada del motor PyNEC.

### Comandos de la CLI

Validación:

```text
antsim validate proyecto.antsim