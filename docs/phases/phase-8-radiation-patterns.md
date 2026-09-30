# Fase 8 — Patrones de radiación

## Estado

Completada.

## 1. Objetivo

Incorporar patrones de radiación reproducibles de punta a punta,
desde el dominio hasta la CLI: investigación previa de la API de
PyNEC, validación externa contra 4nec2, modelo de dominio, cálculo en
`PyNecEngine`, persistencia en el esquema `.yaas` 4, exportación NEC
(tarjeta `RP`) y CSV, y un comando de CLI bilingüe. Sin introducir
todavía visualización gráfica.

## 2. Investigación previa

Detalle completo en
[`docs/research/nec-radiation-patterns.md`](../research/nec-radiation-patterns.md).
Resultados que condicionaron la implementación:

- **`rp_card()`** de PyNEC 2.3.4 recibe **13 argumentos**: separa el
  campo `XNDA` de la tarjeta de texto en cuatro enteros
  (`output_format`, `normalization`, `D`, `A`). `rp_card()` ya ejecuta
  el cálculo; no hace falta `xq_card()`.
- **`get_gain()`** devuelve una matriz con forma `(n_theta, n_phi)`:
  el primer eje es `theta` y el segundo `phi`. En los arrays planos
  (`get_gain_tot()`), `theta` varía más rápido. Se verificó con una
  grilla no cuadrada de 19×37.
- **Conteos negativos** de `theta`/`phi` provocan un `segmentation
  fault` del proceso Python, no una excepción.
- **Dominio angular seguro**: `0 <= theta <= 180` en espacio libre;
  `0 <= theta <= 90` con cualquier plano de tierra. Con tierra,
  `theta > 90` devolvió valores no reproducibles entre llamadas
  idénticas, incluidos números subnormales; la evidencia es compatible
  con estado nativo no inicializado, pero la causa no se confirmó.
- **`-999.99`** es el valor centinela de NEC2 para una ganancia nula o
  no representable, no una ganancia física.
- **Tierra real**: los patrones también requieren un contexto NEC2++
  nuevo por frecuencia, igual que la impedancia (con un contexto
  reutilizado y una geometría que toca z=0 se observó una discrepancia
  de ~0.013 dB).
- **Orden de llamadas**: el orden interno verificado para la API de
  PyNEC (`fr_card -> ex_card -> rp_card`) es distinto del orden textual
  portable de un archivo NEC (`EX` antes que `FR`); son preguntas
  distintas y no se mezclaron.

## 3. Validación externa

Detalle completo en
[`docs/validation/radiation-patterns-4nec2.md`](../validation/radiation-patterns-4nec2.md).

| Modelo | PyNEC | 4nec2 |
|---|---:|---:|
| Dipolo en espacio libre, máximo | 2.1233 dBi | 2.12 dBi |
| Monopolo sobre tierra perfecta, máximo (`theta=90`) | 5.1334 dBi | 5.13 dBi |
| Dipolo a 10 m sobre tierra real, máximo (`theta=43`) | 0.0944 dBi | 0.09 dBi |
| Array asimétrico, máximo (`phi=90`) | 6.6311 dBi | 6.63 dBi |

Convención angular definitiva, resuelta con el array asimétrico cuyo
lóbulo apunta físicamente hacia +Y:

- `theta` se mide desde +Z (0 = +Z, 90 = plano XY, 180 = -Z);
- `phi=0` es +X y `phi=90` es +Y;
- `phi` crece en sentido antihorario visto desde +Z.

PyNEC y 4nec2 coinciden dentro de la resolución de dos decimales que
muestra 4nec2; los nulos aparecen en las mismas direcciones.

## 4. Dominio

En `src/yaas/domain/models.py`, todas como dataclasses `frozen`:

- **`AngularSweep`** (`start_deg`, `count`, `step_deg`): eje angular
  regular, con `stop_deg` y `angles_deg` derivados. `count` debe ser un
  `int` positivo (nunca `bool`), `step_deg >= 0` y positivo si hay más
  de un ángulo; los ángulos no se normalizan ni se envuelven.
- **`RadiationPatternRequest`**: conductores, entorno, fuente,
  frecuencia y los ejes `theta`/`phi`. Reutiliza las validaciones de
  `SimulationRequest` y agrega el dominio angular por entorno (con una
  selección exhaustiva: un entorno desconocido se rechaza).
- **`RadiationPatternSample`**: una dirección y su ganancia.
- **`RadiationPatternResult`**: frecuencia, ángulos y la matriz
  `gain_db[theta_index][phi_index]`, con forma `(n_theta, n_phi)`,
  `shape` y `samples` (theta en el lazo externo, phi en el interno).

`None` representa un nulo explícito. Todos los tipos, rangos y formas
se validan en el dominio, antes de llegar a PyNEC; el dominio no
conoce el centinela `-999.99`.

## 5. Motor

`SimulationEngine.simulate_radiation_pattern()` y su implementación en
`PyNecEngine` (`src/yaas/engines/pynec.py`):

- un contexto NEC2++ nuevo por solicitud;
- secuencia: geometría y entorno (`_create_context`) -> `fr_card` ->
  `ex_card` -> `rp_card` -> `get_radiation_pattern(0)` (un único
  patrón por contexto);
- sin `xq_card()`;
- `get_gain()` se consume directamente, sin reconstruir la matriz;
- solo el centinela `-999.99` (tolerancia absoluta de 1e-6 dB) se
  convierte en `None`; un `NaN` o infinito devuelto por PyNEC es un
  error, nunca un nulo;
- controles defensivos con `RuntimeError` descriptivo: patrón ausente,
  forma inesperada de la matriz, conteos de ángulos distintos de los
  solicitados, ángulos no finitos y datos nativos no convertibles.

## 6. Esquema v4

Decisión registrada en
[ADR 0009](../decisions/0009-add-radiation-pattern-schema-v4.md):

- `simulation.radiation_pattern` opcional, con ejes `theta` y `phi`
  regulares (`start_deg`, `count`, `step_deg` exactos, sin
  `stop_deg`); la frecuencia y el entorno se toman de `simulation`;
- el lector acepta los esquemas 1, 2, 3 y 4 y conserva la versión
  original; los esquemas 1, 2 y 3 rechazan `radiation_pattern`;
- el escritor siempre emite el esquema 4; guardar un proyecto
  anterior lo migra sin patrón y sin mutar el objeto cargado;
- un patrón incoherente con el entorno falla en `load_project()`, no
  al simular;
- los tres ejemplos históricos (v1, v2 y v3) no se modificaron.

## 7. Exportaciones

### NEC

`radiation_pattern_request_to_nec()` y
`export_radiation_pattern_nec()` (`src/yaas/exporters/nec.py`)
agregan una tarjeta `RP` de texto con cuatro enteros y seis
flotantes, con `I4` escrito como el token único `0000`:

```text
RP 0 181 1 0000 0 0 1 0 0 0
```

Orden textual: `GW -> GE/GN -> EX -> FR -> RP -> EN`, sin `XQ`. Las
demás tarjetas son idénticas a las de la exportación puntual
equivalente, y las salidas puntuales y de barrido existentes no
cambiaron byte a byte. La tarjeta de texto no copia los 13 argumentos
de `PyNEC.rp_card()`.

### CSV

`radiation_pattern_to_csv()` y `export_radiation_pattern_csv()`
(`src/yaas/exporters/radiation_pattern_csv.py`):

- columnas `frequency_mhz,theta_deg,phi_deg,gain_db`;
- una fila por dirección, theta en el lazo externo y phi en el
  interno;
- un nulo se escribe como campo vacío, nunca como `-999.99`;
- precisión nativa de `float` (la representación más corta que
  reproduce el valor exacto), independiente del locale;
- UTF-8 y fin de línea CRLF, igual que los CSV existentes.

## 8. CLI

```text
yaas pattern PROYECTO
yaas pattern PROYECTO --csv SALIDA.csv
yaas export-nec PROYECTO SALIDA.nec --pattern
```

- `pattern` muestra la frecuencia, la grilla, los puntos válidos y
  nulos, la ganancia máxima y su dirección. Con `--csv` guarda el
  mismo resultado, sin volver a ejecutar el motor.
- Si todos los puntos son nulos, el comando termina correctamente e
  informa que no hay ganancia máxima finita.
- `export-nec --pattern` no ejecuta PyNEC y es mutuamente excluyente
  con `--sweep` (error traducido, código 2).
- Un proyecto sin `radiation_pattern` se rechaza en ambos comandos con
  código 2 y sin crear archivos; un error del motor devuelve código 1.
- Mensajes en inglés (idioma fuente) y español.

**Máximo determinista.** La dirección del máximo es la primera muestra
en el orden theta externo / phi interno entre las ganancias
empatadas, con una **tolerancia absoluta de 1e-9 dB** (`rel_tol=0.0`).
Motivación: en Ubuntu 24.04, `theta=0` (2.1232781085185755 dBi) y
`theta=180` (2.123278108518579 dBi) del dipolo en espacio libre
difieren en ~3.6e-15 dB de ruido de punto flotante, y una comparación
estricta informaba `theta=180`; en Windows, `theta=0` es levemente
mayor. La tolerancia solo estabiliza la dirección informada: no
redondea ni modifica ningún valor del resultado.

## 9. Ejemplo

`examples/dipole-20m-radiation-pattern.yaas`, generado con
`save_project()`:

- esquema 4, el mismo dipolo de `examples/dipole-20m.yaas`, espacio
  libre, 14.15 MHz;
- `theta` de 0 a 180 en 181 puntos (paso 1) y `phi` en 0;
- resultado: máximo de 2.12 dBi en `theta=0`, un único nulo en
  `theta=90` (el eje del conductor) y simetría respecto del horizonte.

## 10. Build y CI

- **Windows** (`scripts/build_windows.ps1`) y **Linux**
  (`scripts/build_linux.sh`, Ubuntu 24.04): smoke tests del ejecutable
  sobre el ejemplo v4 (`validate`, `pattern`, `pattern --csv` y
  `export-nec --pattern`), incluidos el encabezado y el nulo del CSV y
  el orden `EX < FR < RP < EN` sin `XQ`.
- **CI** (`.github/workflows/tests.yml`): suite completa en Windows,
  Ubuntu 22.04 y Ubuntu 24.04, más el build efímero del ejecutable de
  Linux. No se publica ningún artefacto.
- **Estado final en `main`** (`7358e09`): **1081 pruebas** en verde
  localmente, y los cuatro jobs de CI exitosos (run `36705951169`).
- **Hallazgo multiplataforma**: el run `36704238171`, sobre el commit
  de la CLI en su rama, falló solo en `Tests (ubuntu-24.04)` por el
  empate numérico descrito en la sección 8 (Windows y Ubuntu 22.04
  pasaron; el build de Linux quedó omitido). La corrección
  `7358e09` estabilizó la selección sin cambiar los valores esperados.

## 11. Compatibilidad

- La simulación puntual y los barridos no cambiaron.
- Las salidas NEC puntuales y de barrido existentes son idénticas byte
  a byte; `RP` solo aparece con `--pattern`.
- Los CSV de barrido y de comparación no cambiaron.
- Los ejemplos v1, v2 y v3 no se modificaron y siguen cargando con su
  versión original.
- Todo proyecto válido de los esquemas 1, 2 y 3 sigue cargando; al
  guardarse se migra al esquema 4.

## 12. Límites

- Un patrón por proyecto, a una única frecuencia.
- Una grilla angular regular por eje.
- Solo ganancia total (ganancia de potencia, sin normalización).
- Sin API pública de polarización ni componentes `E_theta`/`E_phi`.
- Sin patrones multifrecuencia.
- Sin gráficos 2D ni 3D.
- Sin interfaz gráfica.
- Sin importación de tarjetas `RP`.
- Sin modelo de pérdidas de conductores.
- La causa nativa de los valores no reproducibles con `theta > 90` y
  tierra sigue sin confirmar.

## 13. Próximos pasos

Opciones posibles, sin una decisión irreversible tomada:

1. Visualización 2D de cortes (vertical y de azimut).
2. Patrones multifrecuencia (con contexto nuevo por frecuencia para
   tierra real).
3. API de polarización y componentes de campo.
4. Diseño formal de la interfaz gráfica (PySide6).
5. Pérdidas de conductores u otras funciones NEC.

Recomendación: como siguiente trabajo, una investigación o prototipo
pequeño de visualización 2D de cortes junto con la arquitectura de la
GUI, para decidir dónde vive el trazado sin acoplarlo al dominio; no
se implementa en esta fase.

## 14. Criterios de aceptación

| Criterio | Estado |
|---|---|
| Investigación de la API de patrones de PyNEC | Cumplido |
| Validación externa contra 4nec2, incluido el sentido de `phi` | Cumplido |
| Modelo de dominio inmutable con validación antes de PyNEC | Cumplido |
| Cálculo en `PyNecEngine`, sin `XQ`, con controles defensivos | Cumplido |
| Centinela `-999.99` representado como `None` | Cumplido |
| Esquema `.yaas` v4 con ADR 0009, lectura compatible de v1-v3 | Cumplido |
| Exportación NEC con tarjeta `RP` de 10 campos | Cumplido |
| Exportación CSV con nulos como celda vacía | Cumplido |
| CLI `pattern` (`--csv`) y `export-nec --pattern`, en inglés y español | Cumplido |
| Máximo determinista entre plataformas | Cumplido |
| Ejemplo v4 versionado | Cumplido |
| Smoke tests de Windows y Linux | Cumplido |
| Salidas históricas y ejemplos v1-v3 intactos | Cumplido |
| CI en verde en Windows, Ubuntu 22.04 y Ubuntu 24.04 | Cumplido |

## 15. Commits de la fase

Obtenidos de `git log` sobre `main`, en orden cronológico:

```text
2ee1094 research: characterize NEC radiation patterns
c99f89f research: correct ground pattern angular domain
c204a2b docs: validate radiation patterns with 4nec2
88df531 feat: add radiation pattern domain models
276a982 feat: calculate radiation patterns with PyNEC
63e96f7 feat: add radiation pattern project schema v4
6e042a0 feat: export radiation patterns to NEC
b16eab5 feat: export radiation patterns to CSV
8421204 feat: add radiation pattern CLI
7358e09 fix: stabilize radiation pattern maximum selection
```

## Documentos relacionados

- [`docs/research/nec-radiation-patterns.md`](../research/nec-radiation-patterns.md)
- [`docs/validation/radiation-patterns-4nec2.md`](../validation/radiation-patterns-4nec2.md)
- [`docs/decisions/0009-add-radiation-pattern-schema-v4.md`](../decisions/0009-add-radiation-pattern-schema-v4.md)
- [`docs/phases/phase-7b-real-ground.md`](phase-7b-real-ground.md)

## Resultado

YAAS calcula, persiste, exporta y muestra por CLI patrones de
radiación de una frecuencia, con una convención angular validada
contra 4nec2, sin gráficos ni interfaz gráfica todavía.
