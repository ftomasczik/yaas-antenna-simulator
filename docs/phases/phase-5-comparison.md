# Fase 5 — Comparación de simulaciones y mediciones

## Estado

Completada.

## Objetivo

Comparar un barrido simulado (`SweepResult`) con una medición
Touchstone (`MeasurementSweep`) sobre una impedancia de referencia
común, con una única implementación reutilizable tanto por la CLI
como por una futura interfaz gráfica.

## Arquitectura

- `src/antsim/domain/comparison.py`: `ComparisonPoint`,
  `SweepComparison` y `compare_sweeps`. Depende solo del dominio; no
  conoce proyectos, motores de simulación ni presentación.
- `src/antsim/application/comparison.py`: `compare_project_measurement`
  y `ComparisonRequestError`. Orquesta proyecto → `SweepRequest` →
  `engine.simulate_sweep(...)` → `compare_sweeps(...)`. Puede importar
  modelos del dominio, `compare_sweeps`, el protocolo
  `SimulationEngine` y modelos de proyecto (`AntennaProject`); no
  importa `argparse`, `gettext`, módulos de la CLI ni un motor
  concreto como `PyNecEngine`.
- `src/antsim/exporters/comparison_csv.py`: `export_comparison_csv`,
  exporta un `SweepComparison` ya calculado sin recalcular
  diferencias.
- `src/antsim/cli/main.py`: comando `antsim compare`. Solo construye
  el motor concreto (`PyNecEngine`), llama a la capa `application` y
  presenta el resultado; no contiene la orquestación ni la lógica de
  comparación.

La CLI y una futura interfaz gráfica deben reutilizar
`antsim.application.comparison`; ninguna debe reimplementar la
orquestación proyecto/motor/comparación.

## Política de Z₀ (ADR 0005)

`compare_sweeps` exige `reference_impedance` como argumento nombrado,
obligatorio, resistivo, positivo y finito, sin valor por defecto.
Convierte el S11 medido usando la impedancia de referencia original de
cada punto medido y recalcula ambas ROE (simulada y medida) desde la
impedancia con la referencia común solicitada. No utiliza la ROE ya
almacenada en `SweepResult` ni intenta inferir una referencia perdida.

## Interpolación

La grilla de comparación es la de las frecuencias medidas que caen
dentro del rango simulado, incluidos sus extremos. Cuando una
frecuencia medida coincide exactamente con una frecuencia simulada se
usa esa muestra tal cual. En cualquier otro caso, se interpolan
linealmente la resistencia y la reactancia simuladas por separado
entre las dos muestras simuladas adyacentes; la ROE se calcula
después de interpolar la impedancia, nunca interpolando la ROE
directamente.

## Ausencia de extrapolación

No se extrapola fuera del rango simulado. Una medición cuya frecuencia
queda fuera de ese rango se excluye sin lanzar error, y
`SweepComparison.excluded_measurement_points` informa cuántas se
excluyeron. Si ninguna medición cae dentro del rango simulado,
`compare_sweeps` rechaza la solicitud.

## Convención de diferencias

`ComparisonPoint.impedance_difference` y `ComparisonPoint.swr_difference`
se definen como **medición menos simulación**. Se rechaza cualquier
valor no finito en cualquier punto del cálculo: impedancias de
entrada, impedancia interpolada, ROE recalculada o diferencias. Un
circuito abierto o una ROE infinita no se comparan silenciosamente.

## Comando CLI

```powershell
antsim compare `
    .\examples\dipole-20m.antsim `
    .\medicion.s1p `
    --reference-impedance 50 `
    --output .\comparacion.csv
```

`--reference-impedance` es obligatorio, sin valor por defecto, según
el ADR 0005. `--output` es opcional; sin él, el comando solo imprime
el resumen bilingüe (proyecto, archivo de medición, impedancia de
referencia, puntos comparados, puntos excluidos, puntos interpolados y
la mayor diferencia absoluta de ROE).

## CSV

`export_comparison_csv` escribe una fila por punto comparado usando
las propiedades ya calculadas de `ComparisonPoint`, sin recalcular
diferencias en la CLI ni en el exportador. Cabeceras principales (no
se traducen):

- `frequency_mhz`
- `simulated_resistance_ohm`, `simulated_reactance_ohm`
- `measured_resistance_ohm`, `measured_reactance_ohm`
- `simulated_swr`, `measured_swr`
- `resistance_difference_ohm`, `reactance_difference_ohm`,
  `swr_difference`
- `interpolated`

## Errores controlados

- Proyecto inválido → código de salida 2 (`Invalid project: ...` /
  `Proyecto inválido: ...`).
- Medición Touchstone inválida → código de salida 2
  (`Invalid measurement: ...` / `Medición inválida: ...`).
- `ComparisonRequestError` (impedancia de referencia inválida, sin
  solapamiento medido, valores no finitos) → código de salida 2
  (`Invalid comparison: ...` / `Comparación inválida: ...`).
- Un error propio del motor de simulación (por ejemplo, un fallo de
  PyNEC) nunca se reclasifica como error de entrada: se propaga sin
  cambios, porque `compare_project_measurement` solo envuelve el
  `ValueError` producido por `compare_sweeps`, nunca una excepción de
  `engine.simulate_sweep(...)`.

## Pruebas

- `tests/unit/test_comparison.py`: contrato de `compare_sweeps` (Z₀
  común, interpolación, exclusión sin extrapolación, rechazo de
  valores no finitos).
- `tests/unit/test_comparison_workflow.py`: `compare_project_measurement`
  con un motor de prueba; demuestra que un `RuntimeError` y un
  `ValueError` propios del motor se propagan sin cambios, y que solo
  el `ValueError` de `compare_sweeps` se convierte en
  `ComparisonRequestError` (con la causa original preservada).
- `tests/unit/test_comparison_csv.py`: cabecera y filas del CSV,
  usando las propiedades ya calculadas de `ComparisonPoint`.
- `tests/test_cli.py`: comando `compare` en español e inglés, CSV
  opcional, y los errores controlados con código de salida 2,
  incluida la conversión específica de `ComparisonRequestError`.
- `scripts/build_windows.ps1`: prueba de humo del comando `compare`
  sobre el ejecutable, en español e inglés, con verificación de la
  cabecera y del contenido del CSV generado.

## Limitaciones

- Solo compara frecuencias medidas dentro del rango simulado; no
  extrapola.
- No compara resonancia ni ancho de banda entre simulación y
  medición; el criterio de candidatos finitos de resonancia (ADR
  0006) sigue aplicándose por separado a cada `SweepResult` y
  `MeasurementSweep`, no a la comparación en sí.
- No corrige calibración ni longitud de cable.
- No genera gráficos de comparación.
- No agrega comandos de CLI más allá de `compare`.

## Resultado

AntSim puede simular el barrido de un proyecto y compararlo con una
medición real sobre una impedancia de referencia común, con una
única implementación reutilizable desde la CLI y, en el futuro, desde
la interfaz gráfica.
