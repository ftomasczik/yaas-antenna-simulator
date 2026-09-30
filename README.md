# YAAS — Yet Another Antenna Simulator

[![Tests](https://github.com/ftomasczik/yaas-antenna-simulator/actions/workflows/tests.yml/badge.svg)](https://github.com/ftomasczik/yaas-antenna-simulator/actions/workflows/tests.yml)

YAAS es un simulador abierto de antenas basado en NEC2++/PyNEC,
orientado inicialmente a CLI y radioaficionados.

El proyecto mantiene separados el modelo de dominio, el motor de
simulación y las interfaces. Actualmente dispone de una interfaz de
línea de comandos; una futura interfaz gráfica utilizará el mismo
núcleo.

> AntSim fue el nombre de desarrollo utilizado antes de la primera
> publicación pública. Desde YAAS 0.3.0, la identidad técnica y
> pública es YAAS. Ver `docs/decisions/0008-rename-to-yaas.md` para
> el detalle completo del cambio.

## Estado

**YAAS 0.3.0** es la última versión estable publicada, y la primera
en publicarse bajo esta identidad: agrega tierra real homogénea
mediante el método Sommerfeld-Norton (`RealGroundEnvironment`) sobre
el modelo de entorno de simulación ya existente desde 0.2.0 (espacio
libre y tierra perfectamente conductora), completo de punta a punta
sobre PyNEC/NEC2++, capaz de simular, comparar contra mediciones
reales e importar proyectos de MMANA-GAL. Ver `CHANGELOG.md` y
`docs/releases/0.3.0.md` para el detalle de esa versión y sus
limitaciones conocidas.

La rama `main` está actualmente en desarrollo como **0.4.0.dev0**
(ver la sección `[Unreleased]` de `CHANGELOG.md`). Este ciclo
incorpora el cálculo de patrones de radiación a una frecuencia, su
configuración opcional en el esquema `.yaas` 4, el comando `yaas
pattern` (resumen y exportación CSV) y la exportación NEC con tarjeta
`RP` (`yaas export-nec --pattern`); todavía no hay gráficos ni
interfaz gráfica para patrones.

`docs/releases/0.2.0.md` documenta el hito anterior (publicado bajo
el nombre de desarrollo AntSim), que agregó el primer entorno con
tierra (tierra perfectamente conductora) sobre el MVP de línea de
comandos ya existente desde 0.1.0.

Capacidades disponibles:

- Modelado de antenas mediante conductores rectos.
- Simulación de impedancia y ROE.
- Barridos lineales de frecuencia.
- Cálculo aproximado de resonancia, ROE mínima y ancho de banda.
- Proyectos JSON versionados con extensión `.yaas`.
- Exportación de barridos a CSV.
- Exportación de proyectos al formato NEC.
- Interfaz de línea de comandos en español e inglés.
- Ejecutable independiente para Windows mediante PyInstaller.
- Suite automatizada de pruebas.
- Importación de mediciones Touchstone S1P.
- Conversión de S11 a impedancia y ROE.
- Diagnóstico de rangos de medición incompletos.
- Comparación de barridos simulados con mediciones Touchstone.
- Importación de proyectos MMANA-GAL (`.maa`) como proyectos `.yaas`.
- Entorno de simulación: espacio libre, tierra perfectamente
  conductora y tierra real homogénea (Sommerfeld-Norton), con
  exportación NEC coherente para los tres.
- Formato `.yaas` con cuatro versiones de esquema: lectura compatible
  de las versiones 1 (espacio libre), 2 (espacio libre o tierra
  perfecta) y 3 (agrega tierra real), y escritura en la versión 4
  (agrega una configuración opcional de patrón de radiación).
- Cálculo de patrones de radiación (ganancia total en dBi) a una
  frecuencia (`yaas pattern`), con exportación a CSV y a NEC con
  tarjeta `RP`; por ahora sin gráficos.

## Stack

- Python 3.13
- PyNEC
- NEC2++
- NumPy
- pytest
- GNU gettext y Babel
- PyInstaller
- Git

## Requisitos de desarrollo

- Windows de 64 bits
- Python 3.13
- Git
- Visual C++ Build Tools
- PowerShell

## Instalación para desarrollo

Crear el entorno virtual:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instalar el proyecto y sus herramientas de desarrollo (distribución
`yet-another-antenna-simulator`, módulo importable `yaas`):

```powershell
python -m pip install -e ".[dev]"
```

Comprobar el entorno:

```powershell
yaas doctor
```

## Idioma

YAAS detecta el idioma del entorno y también permite seleccionarlo
explícitamente:

```powershell
yaas --language es doctor
yaas --language en doctor
```

Los nombres de comandos, opciones, archivos y campos del formato
`.yaas` no se traducen.

## Proyectos `.yaas`

Un proyecto contiene:

- Metadatos.
- Versión del esquema.
- Conductores.
- Fuente de tensión.
- Frecuencia principal.
- Impedancia de referencia.
- Entorno de simulación (espacio libre, tierra perfecta o tierra
  real).
- Configuración del barrido.
- Configuración opcional de un patrón de radiación (solo en el
  esquema 4).

Existen cuatro proyectos de ejemplo:

```text
examples/dipole-20m.yaas
examples/monopole-20m-perfect-ground.yaas
examples/dipole-20m-real-ground.yaas
examples/dipole-20m-radiation-pattern.yaas
```

El primero usa el esquema 1 (espacio libre, sin declarar entorno
explícitamente), el segundo usa el esquema 2 (con
`"environment": {"kind": "perfect_ground"}`) y el tercero usa el
esquema 3 (con `"environment": {"kind": "real_ground", "model":
"sommerfeld_norton", "relative_permittivity": 13.0,
"conductivity_s_per_m": 0.005}`). El cuarto usa el esquema 4: es el
mismo dipolo del primero, con un corte vertical de su patrón de
radiación (ver "Patrones de radiación" más abajo). Los tres primeros
ejemplos conservan deliberadamente sus versiones originales. Un archivo del esquema 1, 2
o 3 sigue cargando sin cambios, interpretado según su propio contrato
(el esquema 2 solo admite espacio libre o tierra perfecta; tierra
real requiere esquema 3 o posterior); al guardarlo con la versión
actual de YAAS queda migrado al esquema 4 automáticamente.

El esquema 4 admite, además, una configuración opcional de patrón de
radiación dentro de `simulation`. Declara solamente los ejes angulares
`theta` y `phi`, en grados; el patrón usa la frecuencia principal y el
entorno del proyecto:

```json
"radiation_pattern": {
  "theta": {"start_deg": 0.0, "count": 181, "step_deg": 1.0},
  "phi": {"start_deg": 0.0, "count": 1, "step_deg": 0.0}
}
```

Si no se declara, el proyecto simplemente no tiene patrón. Con
cualquier plano de tierra, `theta` no puede superar 90 grados; los
esquemas 1, 2 y 3 rechazan esta clave. Ver
[`docs/decisions/0009-add-radiation-pattern-schema-v4.md`](docs/decisions/0009-add-radiation-pattern-schema-v4.md)
(ADR 0009) para el contrato completo y su compatibilidad, y la
sección "Patrones de radiación" para calcularlo y exportarlo.

Ver
`docs/phases/phase-7a-perfect-ground.md` y
`docs/phases/phase-7b-real-ground.md` para el detalle completo del
entorno de simulación, y
`docs/validation/monopole-perfect-ground-4nec2.md` /
`docs/validation/real-ground-dipole-4nec2.md` para sus validaciones
cruzadas contra teoría de imágenes y 4nec2.

Los barridos con tierra real crean un contexto NEC2++ nuevo por cada
frecuencia, en vez de reutilizar uno solo como hacen espacio libre y
tierra perfecta (ver `docs/research/nec-real-ground.md`): un barrido
de 81 puntos puede tardar varios segundos.

Validarlo:

```powershell
yaas validate .\examples\dipole-20m.yaas
```

Simular su frecuencia principal:

```powershell
yaas simulate .\examples\dipole-20m.yaas
```

Ejecutar su barrido:

```powershell
yaas sweep .\examples\dipole-20m.yaas
```

Exportar el barrido a CSV:

```powershell
yaas sweep `
    .\examples\dipole-20m.yaas `
    --output .\dipole-20m.csv
```

## Exportación NEC

Exportar la simulación de frecuencia única:

```powershell
yaas export-nec `
    .\examples\dipole-20m.yaas `
    .\dipole-20m.nec
```

Exportar el barrido configurado en el proyecto:

```powershell
yaas export-nec `
    --sweep `
    .\examples\dipole-20m.yaas `
    .\dipole-20m-sweep.nec
```

La exportación actual genera las tarjetas:

- `CM`
- `CE`
- `GW`
- `GE`
- `GN` (solo para tierra perfecta o tierra real; espacio libre
  conserva `GE 0` sin ninguna tarjeta `GN`)
- `EX`
- `FR`
- `RP` (solo con `--pattern`, ver "Patrones de radiación")
- `EN`

La exportación de frecuencia única fue validada con 4nec2 5.9.3. Para
el dipolo de referencia a 14.150 MHz se obtuvieron:

| Motor | Impedancia | ROE |
|---|---:|---:|
| YAAS / PyNEC | 67.43 - j31.25 ohm | 1.83 |
| 4nec2 | 67.4 - j31.3 ohm | 1.84 |

## Patrones de radiación

Un proyecto del esquema 4 puede declarar un patrón de radiación en
`simulation.radiation_pattern` (ver "Proyectos `.yaas`"). Calcularlo a
la frecuencia principal del proyecto:

```powershell
yaas pattern .\examples\dipole-20m-radiation-pattern.yaas
```

```text
Calculando patrón de radiación: Dipolo de 20 metros - patrón de radiación
Frecuencia: 14.150 MHz
Grilla: 181 x 1 (181 puntos)
Puntos válidos: 180
Nulos: 1
Ganancia máxima: 2.12 dBi
Dirección del máximo: theta=0.00 grados, phi=0.00 grados
```

`theta` se mide desde +Z y `phi` desde +X, en sentido antihorario
visto desde +Z (ver `docs/validation/radiation-patterns-4nec2.md`).
Los nulos son las direcciones en que NEC no informa una ganancia
representable (por ejemplo, a lo largo del eje del dipolo); nunca se
cuentan como ganancia. Ante un empate, la dirección del máximo es la
primera en el orden theta externo / phi interno. Si todos los puntos
son nulos, el comando termina correctamente e indica que no hay
ganancia máxima finita.

Guardar además el mismo resultado como CSV (el patrón se calcula una
sola vez):

```powershell
yaas pattern `
    .\examples\dipole-20m-radiation-pattern.yaas `
    --csv .\patron.csv
```

El CSV tiene una fila por dirección, con las columnas
`frequency_mhz`, `theta_deg`, `phi_deg` y `gain_db` (en dBi), en el
orden theta externo / phi interno. Un nulo se escribe como campo
`gain_db` vacío, nunca como `-999.99`.

Exportar el patrón a NEC, con su tarjeta `RP` después de `FR` (no
ejecuta ninguna simulación):

```powershell
yaas export-nec `
    --pattern `
    .\examples\dipole-20m-radiation-pattern.yaas `
    .\patron.nec
```

`--pattern` y `--sweep` no pueden combinarse. Un proyecto sin
`radiation_pattern` se rechaza en ambos comandos, con código de
salida 2 y sin crear ningún archivo. Todavía no hay gráficos ni
interfaz gráfica para patrones.

## Mediciones Touchstone y NanoVNA

YAAS puede leer archivos Touchstone de un puerto (`.s1p`):

```powershell
yaas inspect-s1p `
    .\examples\wifi-2.4ghz-example.s1p
```

## Comparación con mediciones

YAAS puede simular el barrido configurado en un proyecto y
compararlo con una medición Touchstone sobre una impedancia de
referencia común:

```powershell
yaas compare `
    .\examples\dipole-20m.yaas `
    .\medicion.s1p `
    --reference-impedance 50
```

`--reference-impedance` es obligatorio: no existe un valor por
defecto, para no ocultar una elección incorrecta de Z₀ (ver
`docs/decisions/0005-sweep-comparison.md`).

Exportar la comparación a CSV:

```powershell
yaas compare `
    .\examples\dipole-20m.yaas `
    .\medicion.s1p `
    --reference-impedance 50 `
    --output .\comparacion.csv
```

La comparación se calcula sobre las frecuencias medidas que caen
dentro del rango simulado. Cuando una frecuencia medida coincide
exactamente con una frecuencia simulada se usa esa muestra; en caso
contrario, la resistencia y la reactancia simuladas se interpolan
linealmente entre las dos frecuencias simuladas adyacentes, y la ROE
se recalcula después de interpolar la impedancia. No se extrapola:
las mediciones fuera del rango simulado se excluyen y el resumen
informa cuántas.

Cabeceras principales del CSV (no se traducen):

- `frequency_mhz`
- `simulated_resistance_ohm`, `simulated_reactance_ohm`
- `measured_resistance_ohm`, `measured_reactance_ohm`
- `simulated_swr`, `measured_swr`
- `resistance_difference_ohm`, `reactance_difference_ohm`,
  `swr_difference` (medición menos simulación)
- `interpolated`

Ver las decisiones registradas en
`docs/decisions/0005-sweep-comparison.md` (contrato de comparación,
política de Z₀, interpolación y ausencia de extrapolación) y en
`docs/decisions/0006-finite-resonance-candidates.md` (candidatos
finitos de resonancia, aplicable también a los barridos comparados).

## Importación de proyectos MMANA-GAL

YAAS puede importar un archivo MMANA-GAL (`.maa`) y convertirlo en
un proyecto `.yaas`:

```powershell
yaas import-mmana `
    .\antena.maa `
    .\antena.yaas `
    --sweep-start 13.5 `
    --sweep-stop 15.5 `
    --sweep-points 81 `
    --swr-limit 2.0
```

El resultado del comando es siempre un proyecto `.yaas`, nunca una
simulación directa: una vez creado puede validarse, simularse,
exportarse a NEC o compararse con una medición igual que cualquier
otro proyecto.

`--sweep-start`, `--sweep-stop`, `--sweep-points` y `--swr-limit` son
obligatorios. El formato MMANA-GAL no incluye ninguna definición de
barrido, así que YAAS nunca inventa un barrido por defecto: hay que
indicar los cuatro valores explícitamente.

`--legacy-encoding cp1251|cp1252` solo es necesario cuando el archivo
no es UTF-8 y su codificación resulta genuinamente ambigua entre
Windows-1251 y Windows-1252 (ningún byte del archivo permite
resolverla automáticamente). Sin esta opción, ese caso puntual se
rechaza con un error en vez de adivinarse.

`--force` sobrescribe el archivo de destino si ya existe; sin `--force`
el comando se niega a sobrescribir un `.yaas` existente y no toca su
contenido.

### Segmentación NEC

Los conductores importados usan una densidad de segmentación uniforme
de `lambda/160` (ver
`docs/decisions/0007-use-uniform-nec-segmentation.md`), en vez del
tapering (segmentos de longitud variable, concentrados hacia los
extremos) que usa MMANA-GAL internamente. Esta densidad reproduce con
buena precisión geometrías cercanas a resonancia, pero **no reproduce
el tapering de MMANA-GAL**: es una aproximación deliberada y
documentada, no una conversión exacta de la malla original.

### Restricciones del MVP

Un archivo `.maa` se importa solo si:

- tiene exactamente una fuente, centrada en su conductor y sin
  desplazamiento de pulso;
- no contiene ninguna carga concentrada (`Load`);
- su entorno es espacio libre (ni tierra perfecta ni tierra real);
- todos sus conductores usan `segment_override=-1` (el único modo de
  segmentación por conductor observado en la práctica y aceptado por
  YAAS; ver `docs/research/mmana-format-characterization.md`);
- su geometría no depende de una impedancia de alimentación cercana a
  un circuito abierto (`|gamma|` próximo a 1): esos modelos quedan
  fuera de la garantía experimental de `lambda/160` (ver
  `docs/research/nec-segmentation-convergence.md`).

Un archivo que no cumple estas restricciones **se rechaza con un
error** (código de salida 2, con el detalle de cada problema
encontrado); nunca se ignora en silencio ni se importa parcialmente.

## Comandos de referencia

Los comandos iniciales continúan disponibles para diagnóstico y
comparación:

```powershell
yaas simulate-dipole
yaas sweep-dipole
```

Ejemplo de barrido configurable:

```powershell
yaas sweep-dipole `
    --start 13.5 `
    --stop 15.5 `
    --points 81 `
    --swr-limit 2
```

## Pruebas

Ejecutar la suite completa:

```powershell
python -m pytest
```

Las pruebas cubren:

- Validaciones del dominio.
- Cálculo de ROE.
- Modelos de simulación y barrido.
- Integración con PyNEC.
- Lectura y escritura de proyectos.
- Versiones del esquema.
- Internacionalización.
- Interfaz de línea de comandos.
- Exportación CSV.
- Exportación NEC.
- Comparación de simulaciones con mediciones y su exportación a CSV.
- Importación de archivos MMANA-GAL: parser estructural,
  compatibilidad, conversión, escritura atómica de proyectos y comando
  de CLI (español e inglés).
- Modelo de entorno (espacio libre, tierra perfecta y tierra real
  Sommerfeld-Norton): validación de conductores contra el plano de
  tierra, validación de permitividad/conductividad/modelo, motor
  PyNEC (incluida la estrategia de barrido de contexto nuevo por
  frecuencia para tierra real), exportación NEC y compatibilidad de
  esquema `.yaas` v1/v2/v3/v4.
- Patrones de radiación: modelos de dominio, cálculo con PyNEC
  (incluidos el orden de llamadas y los fallos de la salida nativa),
  configuración `radiation_pattern` del esquema 4, exportación CSV y
  NEC (`RP`), y los comandos `pattern` y `export-nec --pattern` (en
  español e inglés).

## Integración continua

La suite completa de pruebas se ejecuta automáticamente en cada
`push`/`pull request` hacia `main` (y también puede dispararse
manualmente), sobre tres plataformas independientes: **Windows**,
**Ubuntu 22.04** y **Ubuntu 24.04**. Ver
`.github/workflows/tests.yml` para el detalle exacto de cada job.

Sobre Ubuntu 24.04, además, se construye y prueba de manera
**efímera** un ejecutable experimental de Linux (`dist/yaas`): ese
job no publica ningún artefacto ni lo adjunta a ninguna release. Ver
`docs/building-linux.md` para reproducir ese mismo build de forma
local.

## Ejecutable para Windows

Construir y verificar el ejecutable:

```powershell
.\scripts\build_windows.ps1
```

El resultado se genera en:

```text
dist\yaas.exe
```

El script ejecuta pruebas de humo sobre el ejecutable, incluyendo
idiomas, simulación, barridos, proyectos, CSV, exportación NEC,
comparación con mediciones e importación de archivos MMANA-GAL
(en español e inglés, con validación posterior del proyecto
generado), además de comprobar los cuatro proyectos de ejemplo —
esquema 1 (espacio libre), esquema 2 (tierra perfecta), esquema 3
(tierra real, Sommerfeld-Norton) y esquema 4 (patrón de radiación) —,
incluidas las tarjetas NEC `GE`/`GN` esperadas en cada caso (validando
la tarjeta `GN` de tierra real campo por campo, no solo por
subcadena) y, para el patrón, su resumen, su CSV y la tarjeta `RP`.

## Ejecutable para Linux (experimental)

Construir y verificar el ejecutable experimental de Linux:

```bash
bash scripts/build_linux.sh
```

El resultado se genera en `dist/yaas`. El script ejecuta las mismas
pruebas y verificaciones de humo que su equivalente de Windows sobre
los cuatro proyectos de ejemplo (esquema 1, 2, 3 y 4), incluidas las
tarjetas `GE`/`GN` esperadas y, para el patrón de radiación, su
resumen, su CSV y la tarjeta `RP`.

Este ejecutable es **local y experimental**: se construye y prueba de
manera efímera en CI (job `build-linux`, Ubuntu 24.04), sin publicarse
ni adjuntarse a ninguna release. Ver `docs/building-linux.md` para el
procedimiento completo de instalación y build local, incluida la
solución de problemas.

## Limitaciones actuales

- Solo se modelan conductores rectos.
- Se admite una única fuente de tensión.
- Las simulaciones admiten espacio libre, tierra perfectamente
  conductora y tierra real homogénea mediante Sommerfeld-Norton; el
  método rápido de tierra real por coeficiente de reflexión (Fresnel)
  todavía no está implementado.
- Los patrones de radiación se calculan solo a una frecuencia, un
  patrón por proyecto: no hay barridos de patrón, gráficos ni
  interfaz gráfica, ni polarización o componentes de campo.
- No hay radiales, pantallas de tierra ni conductores enterrados,
  para ningún tipo de tierra.
- Los barridos con tierra real crean un contexto NEC2++ nuevo por
  frecuencia y no ofrecen progreso ni cancelación: un barrido de 81
  puntos puede tardar varios segundos.
- No existe todavía una interfaz gráfica.
- La edición de proyectos se realiza manualmente como JSON.
- No se importan archivos NEC.
- Solo se importan archivos Touchstone de un puerto (`.s1p`).
- Todavía no se admiten archivos multipuerto como `.s2p`.
- La importación MMANA-GAL sigue rechazando cualquier entorno que no
  sea espacio libre, incluidas tierra perfecta y tierra real.
- La comparación con mediciones (`yaas compare`) no extrapola fuera
  del rango simulado ni genera gráficos todavía.
- El formato `.yaas` admite cuatro versiones de esquema (1, 2, 3 y
  4); los archivos de la versión 1 se interpretan como espacio libre,
  los de la versión 2 admiten espacio libre o tierra perfecta (nunca
  tierra real), solo la versión 4 admite `radiation_pattern`, y los de
  las versiones 1, 2 y 3 se migran a la versión 4 al guardarse
  nuevamente.

## Desarrollo previsto

- Interfaz gráfica con PySide6.
- Visualización de la geometría.
- Gráficos de patrones de radiación y barridos de patrón por
  frecuencia.
- Método rápido de tierra real por coeficiente de reflexión (Fresnel).
- Radiales, pantallas de tierra y conductores enterrados.
- Soporte de tierra perfecta y tierra real en la importación
  MMANA-GAL.
- Progreso y cancelación para barridos largos (en particular, los de
  tierra real).
- Nuevos tipos de geometría y cargas.
- Importación NEC.
- Gráficos de comparación entre simulaciones y mediciones.
- Importación de archivos Touchstone multipuerto.

## Documentación

Las decisiones arquitectónicas se encuentran en:

```text
docs/decisions
```

Los cierres de fase se encuentran en:

```text
docs/phases
```

Las validaciones de interoperabilidad se encuentran en:

```text
docs/validation
```

## Licencia

YAAS se distribuye bajo **GPL-3.0-only**.

Copyright (C) 2026 Federico Tomasczik.

- Texto completo de la licencia: [`LICENSE`](LICENSE).
- Inventario de dependencias de terceros y sus licencias:
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
- Decisión de licencia y su evidencia:
  [`docs/decisions/0004-project-license.md`](docs/decisions/0004-project-license.md)
  (ADR 0004).
- Política para una futura distribución binaria:
  [`docs/packaging/windows-release-compliance.md`](docs/packaging/windows-release-compliance.md).

Por ahora, la publicación pública prevista es únicamente del
**código fuente** de este repositorio: `dist\yaas.exe` no se
distribuirá como descarga pública hasta completar el paquete de
cumplimiento reproducible descrito en la política de distribución
binaria enlazada arriba.
