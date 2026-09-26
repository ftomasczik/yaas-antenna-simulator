# Antenna Simulator

AntSim es un simulador de antenas basado en Python, PyNEC y NEC2++,
orientado inicialmente a Windows y diseñado para radioaficionados.

El proyecto mantiene separados el modelo de dominio, el motor de
simulación y las interfaces. Actualmente dispone de una interfaz de
línea de comandos; una futura interfaz gráfica utilizará el mismo
núcleo.

## Estado

Proyecto en desarrollo activo.

Capacidades disponibles:

- Modelado de antenas mediante conductores rectos.
- Simulación de impedancia y ROE.
- Barridos lineales de frecuencia.
- Cálculo aproximado de resonancia, ROE mínima y ancho de banda.
- Proyectos JSON versionados con extensión `.antsim`.
- Exportación de barridos a CSV.
- Exportación de proyectos al formato NEC.
- Interfaz de línea de comandos en español e inglés.
- Ejecutable independiente para Windows mediante PyInstaller.
- Suite automatizada de pruebas.
- Importación de mediciones Touchstone S1P.
- Conversión de S11 a impedancia y ROE.
- Diagnóstico de rangos de medición incompletos.
- Comparación de barridos simulados con mediciones Touchstone.

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

Instalar el proyecto y sus herramientas de desarrollo:

```powershell
python -m pip install -e ".[dev]"
```

Comprobar el entorno:

```powershell
antsim doctor
```

## Idioma

AntSim detecta el idioma del entorno y también permite seleccionarlo
explícitamente:

```powershell
antsim --language es doctor
antsim --language en doctor
```

Los nombres de comandos, opciones, archivos y campos del formato
`.antsim` no se traducen.

## Proyectos `.antsim`

Un proyecto contiene:

- Metadatos.
- Versión del esquema.
- Conductores.
- Fuente de tensión.
- Frecuencia principal.
- Impedancia de referencia.
- Configuración del barrido.

Existe un proyecto de ejemplo en:

```text
examples/dipole-20m.antsim
```

Validarlo:

```powershell
antsim validate .\examples\dipole-20m.antsim
```

Simular su frecuencia principal:

```powershell
antsim simulate .\examples\dipole-20m.antsim
```

Ejecutar su barrido:

```powershell
antsim sweep .\examples\dipole-20m.antsim
```

Exportar el barrido a CSV:

```powershell
antsim sweep `
    .\examples\dipole-20m.antsim `
    --output .\dipole-20m.csv
```

## Exportación NEC

Exportar la simulación de frecuencia única:

```powershell
antsim export-nec `
    .\examples\dipole-20m.antsim `
    .\dipole-20m.nec
```

Exportar el barrido configurado en el proyecto:

```powershell
antsim export-nec `
    --sweep `
    .\examples\dipole-20m.antsim `
    .\dipole-20m-sweep.nec
```

La exportación actual genera las tarjetas:

- `CM`
- `CE`
- `GW`
- `GE`
- `EX`
- `FR`
- `EN`

La exportación de frecuencia única fue validada con 4nec2 5.9.3. Para
el dipolo de referencia a 14.150 MHz se obtuvieron:

| Motor | Impedancia | ROE |
|---|---:|---:|
| AntSim / PyNEC | 67.43 - j31.25 ohm | 1.83 |
| 4nec2 | 67.4 - j31.3 ohm | 1.84 |

## Mediciones Touchstone y NanoVNA

AntSim puede leer archivos Touchstone de un puerto (`.s1p`):

```powershell
antsim inspect-s1p `
    .\examples\wifi-2.4ghz-example.s1p
```

## Comparación con mediciones

AntSim puede simular el barrido configurado en un proyecto y
compararlo con una medición Touchstone sobre una impedancia de
referencia común:

```powershell
antsim compare `
    .\examples\dipole-20m.antsim `
    .\medicion.s1p `
    --reference-impedance 50
```

`--reference-impedance` es obligatorio: no existe un valor por
defecto, para no ocultar una elección incorrecta de Z₀ (ver
`docs/decisions/0005-sweep-comparison.md`).

Exportar la comparación a CSV:

```powershell
antsim compare `
    .\examples\dipole-20m.antsim `
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

## Comandos de referencia

Los comandos iniciales continúan disponibles para diagnóstico y
comparación:

```powershell
antsim simulate-dipole
antsim sweep-dipole
```

Ejemplo de barrido configurable:

```powershell
antsim sweep-dipole `
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

## Ejecutable para Windows

Construir y verificar el ejecutable:

```powershell
.\scripts\build_windows.ps1
```

El resultado se genera en:

```text
dist\antsim.exe
```

El script ejecuta pruebas de humo sobre el ejecutable, incluyendo
idiomas, simulación, barridos, proyectos, CSV, exportación NEC y
comparación con mediciones.

## Limitaciones actuales

- Solo se modelan conductores rectos.
- Se admite una única fuente de tensión.
- Las simulaciones actuales se realizan en espacio libre.
- No hay todavía configuración de suelo.
- No se calculan diagramas de radiación.
- No existe todavía una interfaz gráfica.
- La edición de proyectos se realiza manualmente como JSON.
- No se importan archivos NEC.
- Solo se importan archivos Touchstone de un puerto (`.s1p`).
- Todavía no se admiten archivos multipuerto como `.s2p`.
- La comparación con mediciones (`antsim compare`) no extrapola fuera
  del rango simulado ni genera gráficos todavía.
- El formato `.antsim` dispone actualmente de una única versión de
  esquema.

## Desarrollo previsto

- Interfaz gráfica con PySide6.
- Visualización de la geometría.
- Diagramas de radiación.
- Configuración de suelo.
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
