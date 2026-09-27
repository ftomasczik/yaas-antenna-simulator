# Fase 7A — Modelo de entorno: espacio libre y tierra perfecta

## Estado

Completada.

## 1. Objetivo

Agregar un modelo de entorno de simulación a AntSim, con soporte
inicial de espacio libre (comportamiento ya existente, preservado
byte a byte) y tierra perfectamente conductora, propagado de punta a
punta: dominio, esquema de proyecto `.antsim`, motor PyNEC/NEC2++,
exportación NEC, un proyecto de ejemplo real y validación cruzada
contra teoría de imágenes y 4nec2.

## 2. Alcance implementado

- **`FreeSpaceEnvironment`** y **`PerfectGroundEnvironment`**
  (`src/antsim/domain/models.py`): dataclasses inmutables, sin
  herencia compartida (mismo patrón ya usado por
  `MmanaResistiveLoad`/`MmanaLcqLoad`), unidas por el alias
  `Environment`. Se propagan sin cambios a través de
  `SimulationRequest`, `SweepRequest` y `AntennaProject`.
- **Validación de conductores respecto de z=0**: cuando el entorno no
  es espacio libre, `SimulationRequest`/`SweepRequest` rechazan
  cualquier conductor con un extremo en `z < 0` (cruza o queda bajo
  el plano de tierra) o con ambos extremos en `z = 0` (quedaría
  contenido en el plano; eso es un radial de pantalla de tierra, no
  un conductor común). Reemplaza el `RuntimeError: Unknown exception`
  opaco que NEC2++ produce en ese caso por un `ValueError` claro, con
  el tag del conductor.
- **`PyNecEngine` con `GE`/`GN`**: `geometry_complete(1)` +
  `gn_card(1, 0, 0, 0, 0, 0, 0, 0)` para tierra perfecta;
  `geometry_complete(0)` + `gn_card(-1, ...)` sin cambios para
  espacio libre. Selección exhaustiva por tipo; un entorno
  desconocido produce un error explícito, nunca una caída silenciosa
  a espacio libre.
- **Esquema `.antsim` versión 2**: `simulation.environment` pasa a
  ser obligatorio, con dos formas válidas exactas —
  `{"kind": "free_space"}` o `{"kind": "perfect_ground"}` —, sin
  claves adicionales ni valores de `kind` desconocidos.
- **Lectura compatible de v1**: un archivo `schema_version: 1` (sin
  `simulation.environment`) sigue cargando sin cambios, se interpreta
  siempre como `FreeSpaceEnvironment`, y el objeto en memoria conserva
  `schema_version == 1`.
- **Escritura/migración a v2**: `project_to_dict`/`save_project`
  siempre escriben `schema_version: 2` y siempre incluyen
  `simulation.environment`, sin importar el `schema_version` del
  objeto en memoria. Guardar un proyecto leído de un archivo v1 lo
  migra a v2 automáticamente; la función no modifica el objeto
  `AntennaProject` recibido (es un dataclass inmutable).
- **Exportación NEC**: espacio libre conserva exactamente
  `GE 0` sin ninguna tarjeta `GN` (salida histórica, verificada byte
  a byte contra la ya validada con 4nec2); tierra perfecta agrega
  `GE 1` seguida de `GN 1 0 0 0 0 0 0 0`, siempre después de la
  última `GW` y antes de `EX`/`FR`.
- **Ejemplo de monopolo**: `examples/monopole-20m-perfect-ground.antsim`
  (schema 2, conductor vertical de z=0 a z=5.03 m, 38 segmentos,
  alimentado en la base, `perfect_ground`).
- **Validación contra teoría de imágenes y 4nec2**: ver sección 5.
- **Smoke tests del ejecutable Windows** (`scripts/build_windows.ps1`):
  el ejecutable PyInstaller real valida, simula, barre y exporta a
  NEC tanto el proyecto histórico v1 (espacio libre) como el nuevo
  ejemplo v2 (tierra perfecta), verificando en ambos casos las
  tarjetas `GE`/`GN` esperadas.

## 3. Decisiones

- **No crear `RealGroundEnvironment` todavía.** Se define como tipo
  únicamente en la investigación previa
  (`docs/research/nec-ground-configuration.md`) como referencia de
  diseño; no existe en el dominio ni en ningún motor o exportador.
  Queda para la fase 7B.
- **Esquema 2 en vez de extender ambiguamente el esquema 1.** Aunque
  `swr_limit` ya había mostrado que un campo opcional puede agregarse
  a un esquema existente sin bump de versión, `environment` se
  consideró suficientemente central (afecta la física de la
  simulación, no solo la presentación) como para justificar una
  versión de esquema explícita, con autorización previa
  (ver `docs/decisions`, y la autorización explícita para esta tarea
  concreta).
- **Los proyectos v1 se interpretan como espacio libre**, nunca como
  un valor por defecto ambiguo: es el único entorno que el formato
  v1 pudo haber representado alguna vez, ya que no tenía ningún campo
  de entorno.
- **El escritor siempre genera v2.** No existe una opción para seguir
  escribiendo v1; cualquier proyecto guardado con el código actual
  queda en v2, incluida su migración automática si se cargó de un
  archivo v1.
- **Espacio libre conserva `GE 0` sin `GN`** en la exportación, en
  vez de agregar `GN -1 ...` por simetría con `PyNecEngine`: hacerlo
  habría cambiado un archivo ya validado externamente con 4nec2 sin
  necesidad real.
- **Tierra perfecta usa `GE 1` seguido por `GN 1 ...`**, replicando
  exactamente el orden y los argumentos ya usados por `PyNecEngine`,
  verificados empíricamente antes de escribir el exportador (ver
  `docs/research/nec-ground-configuration.md`).

## 4. Compatibilidad

- Los proyectos v1 existentes (por ejemplo,
  `examples/dipole-20m.antsim`) continúan cargando sin cambios.
- Al guardarse, cualquier proyecto pasa a v2 automáticamente.
- El objeto `AntennaProject` recién leído conserva el
  `schema_version` con el que fue leído (1 o 2) mientras esté en
  memoria; solo al guardarlo se reescribe como 2.
- Guardar un proyecto (`project_to_dict`/`save_project`) no muta el
  objeto `AntennaProject` recibido.

## 5. Validación numérica

Monopolo cuarto de onda sobre tierra perfecta (mismo brazo de 5.03 m
que el dipolo de referencia), a 14.150 MHz, 38 segmentos:

| Fuente | Impedancia | ROE (50 ohm) |
|---|---:|---:|
| Predicción por teoría de imágenes | 33.72 - j15.63 ohm | — |
| AntSim / PyNEC | 33.79 - j15.62 ohm | 1.72 |
| 4nec2 V5.9.3 | 33.8 - j15.6 ohm | 1.72 |

Detalle completo en
`docs/validation/monopole-perfect-ground-4nec2.md`.

Verificación de la fase: 522 pruebas automatizadas pasan; el build de
Windows (`scripts/build_windows.ps1`) y sus smoke tests, incluidos
los del proyecto v1 histórico y del nuevo ejemplo v2, se ejecutaron
correctamente contra el ejecutable PyInstaller real.

## 6. Barrido del ejemplo

Barrido del monopolo, 13.500-15.500 MHz, 81 puntos:

- Resonancia aproximada: 14.450 MHz.
- ROE mínima: 1.38, a 14.500 MHz.
- Ancho de banda para ROE <= 2.00: 14.025-15.050 MHz.
- Ningún resultado (resonancia, ROE mínima ni ancho de banda) quedó
  truncado por los límites del barrido.

## 7. Límites

- No hay tierra real (con pérdidas, Sommerfeld o Fresnel).
- La importación MMANA-GAL sigue rechazando cualquier entorno que no
  sea espacio libre, incluida tierra perfecta: la equivalencia de
  convención de altura entre MMANA-GAL y AntSim para ese caso no se
  investigó en esta fase (ver `docs/phases/phase-6-mmana-import.md`).
- No hay radiales ni pantallas de tierra (mallas de puesta a tierra).
- No hay conductores enterrados (bajo el plano de tierra); esa
  geometría se rechaza explícitamente.
- Esta fase no valida patrones de radiación ni ganancia: solo
  impedancia de entrada.
- La interfaz gráfica queda fuera de alcance, como en todas las fases
  anteriores.

## 8. Próxima fase 7B

- Tierra real homogénea: permitividad relativa y conductividad como
  parámetros de `RealGroundEnvironment`.
- Selección documentada del método NEC2 correspondiente
  (aproximación por reflexión de Fresnel frente al método asintótico
  de Sommerfeld/Norton), con su costo computacional relativo.
- Validación cruzada con 4nec2, con la misma disciplina de esta fase
  (observación empírica separada de documentación y de decisiones de
  AntSim).
- Todavía sin prometer importación automática de MMANA-GAL con
  tierra real ni perfecta: esa aceptación es una decisión aparte,
  posterior, condicionada a confirmar la equivalencia de convención
  de altura mencionada en la sección 7.

## 9. Commits de la fase

Obtenidos de `git log`, en orden cronológico:

```text
4086321 research: verify PyNEC ground API
16e943a feat: add environment domain model
01755fc feat: validate wires against ground plane
6c58f78 feat: support perfect ground in PyNecEngine
c0b42cc feat: add environment to project schema v2
9f145b2 feat: export perfect ground to NEC
fe3e2c3 feat: add perfect-ground monopole example
480788d docs: validate monopole over perfect ground
b846ff4 build: test perfect-ground executable
```

## 10. Criterios de aceptación

| Criterio | Estado |
|---|---|
| `FreeSpaceEnvironment`/`PerfectGroundEnvironment` en el dominio | Cumplido |
| Validación de conductores contra z=0 | Cumplido |
| `PyNecEngine` con `GE`/`GN` | Cumplido |
| Esquema `.antsim` v2, con lectura compatible de v1 | Cumplido |
| Escritura siempre en v2, sin mutar el objeto en memoria | Cumplido |
| Exportación NEC de ambos entornos, espacio libre sin cambios | Cumplido |
| Proyecto de ejemplo v2 | Cumplido |
| Validación contra teoría de imágenes y 4nec2 | Cumplido |
| Smoke tests del ejecutable Windows (v1 y v2) | Cumplido |
| Suite de pruebas completa en verde | Cumplido (522 pruebas) |

## Deuda documental detectada

No existe todavía un documento de referencia del formato `.antsim`
que se mantenga siempre actualizado (`docs/phases/phase-2-projects.md`
es un cierre de fase histórico, no una referencia viva del formato).
El contrato completo de los esquemas 1 y 2 —incluido
`simulation.environment`— queda registrado en las secciones 2 y 4 de
este documento, pero no en un lugar dedicado y fácil de encontrar por
formato. Si el formato vuelve a crecer (por ejemplo, con tierra real
en la fase 7B), conviene crear ese documento de referencia entonces,
en vez de seguir acumulando el contrato entre varios cierres de fase.

## Documentos relacionados

- `docs/research/nec-ground-configuration.md` — investigación
  empírica de la API `GE`/`GN` de PyNEC previa a esta fase.
- `docs/validation/monopole-perfect-ground-4nec2.md` — validación
  cruzada completa (teoría de imágenes, AntSim/PyNEC, 4nec2).
- `examples/monopole-20m-perfect-ground.antsim` — proyecto de
  ejemplo v2 usado en la validación.
- `docs/decisions/0002-use-nec2plusplus.md` — ADR de adopción de
  PyNEC/NEC2++, con el resultado de referencia del dipolo usado aquí
  como base de la predicción por teoría de imágenes.
- `docs/validation/nec-export-4nec2.md` — validación original de
  exportación NEC en espacio libre, cuya salida byte a byte se
  preserva en esta fase.

## Resultado

AntSim puede representar, en el dominio, en el esquema de proyecto,
en el motor de simulación y en la exportación NEC, tanto espacio
libre (sin cambios respecto de las fases anteriores) como tierra
perfectamente conductora, con un ejemplo real validado de forma
independiente contra teoría de imágenes y contra 4nec2.
