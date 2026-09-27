# Configuración de tierra en PyNEC/NEC2++ (investigación previa a la fase 7A)

Este documento registra la investigación empírica realizada antes de
implementar código de dominio para la fase 7A (modelo de entorno con
espacio libre y tierra perfecta). No se agregó ningún código de
producción como parte de este documento; solo se ejecutó un script
descartable, fuera del repositorio, contra el PyNEC ya instalado en
`.venv`, para verificar hipótesis sobre la API de tierra antes de
diseñar sobre ellas a ciegas.

Se aplica aquí el mismo criterio que
`docs/research/mmana-format-characterization.md` usa para MMANA-GAL:
separar explícitamente qué es **observación empírica** (lo que este
script demostró, en esta instalación concreta), qué es
**comportamiento documentado de NEC2** (lo que surge de la tarjeta
estándar `GN`/`GE`, sin verificación propia más allá de lo ya
observado) y qué es una **decisión pendiente de AntSim** (una
elección de alcance o de diseño, no una propiedad de NEC2 ni de
PyNEC).

## Entorno de la investigación

- Python: 3.13.15
- PyNEC: 2.3.4
- Plataforma: Windows 11 x64 (`Windows-11-10.0.26100-SP0`)
- Las llamadas usadas (`geometry.wire`, `context.geometry_complete`,
  `context.gn_card`, `context.fr_card`, `context.ex_card`,
  `context.xq_card`, `context.get_input_parameters(...).get_impedance()`)
  son las mismas ya utilizadas por
  `src/antsim/engines/pynec.py::PyNecEngine._create_context` para
  espacio libre; esta investigación solo agrega argumentos distintos
  a `geometry_complete`/`gn_card`, no API nueva.

Todas las corridas de este documento se repitieron dos veces de forma
independiente y dieron resultados idénticos (mismos valores exactos
de impedancia), confirmando que no hay variabilidad entre ejecuciones
en esta instalación.

## 1. Dipolo de referencia en espacio libre

**Observación empírica.** Reproduciendo exactamente la configuración
ya validada del dipolo de referencia (`docs/decisions/0002-use-nec2plusplus.md`,
`docs/phases/phase-1-core.md`): conductor de -5.03 a 5.03 m en el eje
X, radio 0.001 m, 101 segmentos, alimentado en el segmento 51, a
14.15 MHz, con `geometry_complete(0)` y
`gn_card(-1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)` (espacio libre, la
misma llamada que ya usa `PyNecEngine` hoy):

```text
Impedancia: 67.433387067669 - 31.254106612963753j ohm
```

Coincide, dentro del redondeo ya documentado, con el valor de
referencia existente (67.43 - j31.25 ohm). No es un hallazgo nuevo;
se incluye como control de que el script de esta investigación
reproduce correctamente el comportamiento ya validado antes de variar
la configuración de tierra.

## 2. Predicción por teoría de imágenes

**Comportamiento documentado (electromagnetismo, no específico de
NEC2 ni de PyNEC).** Un monopolo vertical cuarto de onda, alimentado
en su base contra un plano de tierra perfectamente conductor, es
eléctricamente equivalente a la mitad superior de un dipolo de media
onda: la corriente de imagen en el plano de tierra reproduce
exactamente la mitad inferior que el dipolo tendría en espacio libre.
La teoría de imágenes predice que la impedancia de entrada del
monopolo es exactamente la **mitad** de la del dipolo equivalente en
espacio libre (parte real y parte imaginaria, ambas a la mitad). Esta
es una propiedad exacta de la electrostática/electrodinámica de
planos conductores infinitos, independiente de qué motor NEC se use
para calcularla.

A partir del valor de la sección 1:

```text
Predicción: 33.7166935338345 - 15.627053306481876j ohm
```

## 3. Monopolo con GE(1) + GN(1)

**Observación empírica.** Conductor vertical de (0,0,0) a (0,0,5.03)
m — mismo largo de brazo y mismo radio que el dipolo de referencia —,
alimentado en el segmento 1 (el que toca el plano de tierra, z=0), a
14.15 MHz, con:

```python
context.geometry_complete(1)
context.gn_card(1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
```

Resultado:

```text
Impedancia: 33.78666408428509 - 15.623641070043119j ohm  (38 segmentos)
```

Diferencia contra la predicción de la sección 2: 0.07 ohm en
resistencia, 0.004 ohm en reactancia — coincide dentro de un margen
comparable al ya observado entre AntSim/PyNEC y 4nec2 en otras
validaciones de este proyecto (`docs/validation/nec-export-4nec2.md`,
`docs/validation/mmana-hentenna-nec2.md`).

Sensibilidad a la cantidad de segmentos (misma geometría, variando
solo `segment_count` en `geometry.wire(...)`):

| Segmentos | Impedancia |
|---:|---|
| 38 | 33.78666408428509 - 15.623641070043119j ohm |
| 39 | 33.78446157535037 - 15.620826712788702j ohm |
| 51 | 33.76538684694917 - 15.594231749065179j ohm |
| 101 | 33.7367861760678 - 15.54109041160777j ohm |

Los cuatro valores son prácticamente idénticos entre sí (variación
menor a 0.05 ohm en resistencia y 0.09 ohm en reactancia entre 38 y
101 segmentos), consistente con la estabilidad ya documentada por el
estudio de convergencia de segmentación (ADR 0007) para geometrías
representativas — aunque ese estudio se hizo enteramente en espacio
libre; esta observación es la primera evidencia de que la misma
densidad se comporta razonablemente también con tierra perfecta
activada, para esta única geometría vertical simple.

**Comportamiento documentado.** `ground_type=1` en la tarjeta `GN`
corresponde, según la documentación estándar de NEC2, a tierra
perfectamente conductora (sin pérdidas); `rad_wire_count=0` indica
que no se agrega una pantalla de radiales; los seis parámetros
restantes (constante dieléctrica, conductividad, y los de una
pantalla de radiales o un segundo medio) no se usan para este tipo de
tierra. `geometry_complete(1)` corresponde a la tarjeta `GE` con el
indicador de plano de tierra activado: NEC2 aplica el método de
imágenes a la estructura declarada (que debe quedar enteramente en
`z >= 0`; ver sección 5).

## 4. Control incorrecto: GE(0) con GN(1)

**Observación empírica.** Misma geometría y alimentación que la
sección 3, pero con:

```python
context.geometry_complete(0)   # sin plano de tierra
context.gn_card(1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # tierra perfecta
```

Resultado:

```text
Impedancia: 49.79498731137288 - 14796.057035467822j ohm
```

Un valor sin sentido físico como monopolo sobre tierra (reactancia de
miles de ohm), muy distinto tanto de la predicción de la sección 2
como del resultado coherente de la sección 3.

**Comportamiento documentado / interpretación.** Esta observación
confirma que **`GE` (`geometry_complete`) es quien realmente activa
el método de imágenes**; `GN` (`gn_card`) por sí solo, sin
`GE`/`geometry_complete` con el indicador de plano de tierra
activado, no acopla ningún plano de tierra a la impedancia de
entrada. Es la razón concreta por la que `GE` y `GN` deben
configurarse de forma consistente entre sí: `GN` describe **qué tipo**
de tierra hay, pero es `GE` quien decide **si** hay alguna.

## 5. Conductores válidos, cruzando el plano de tierra y bajo tierra

**Observación empírica.** Con `geometry_complete(1)` +
`gn_card(1, 0, ...)` fijos, se varió únicamente la geometría del
único conductor (21 segmentos, alimentado en el segmento 11):

| Geometría (z1 a z2) | Resultado |
|---|---|
| 0 a 5.03 (monopolo normal, toca el plano en un extremo) | Se calcula sin error: 64.91998524365601 - 29.37772814080748j ohm |
| -2 a 3 (cruza el plano de tierra) | `RuntimeError: Unknown exception` |
| -5 a -1 (completamente bajo tierra) | `RuntimeError: Unknown exception` |
| 2 a 5 (flota sobre el plano, sin tocar z=0) | Se calcula sin error: 6.692613625500065 - 1618.466617070528j ohm (geometría válida, pero eléctricamente distinta: no es un monopolo alimentado contra tierra) |

**Comportamiento documentado.** NEC2 exige que, cuando el plano de
tierra está activo (`GE` con el indicador correspondiente), toda la
estructura quede en `z >= 0`; un conductor que cruza o queda por
debajo del plano no es válido. Esta observación confirma que NEC2++
efectivamente detecta y rechaza ambos casos inválidos, aunque lo haga
mediante una excepción nativa sin mensaje descriptivo
(`RuntimeError: Unknown exception`, idéntica para ambos casos, sin
distinguir "cruza" de "está debajo").

También se observa que un conductor que **no toca** el plano de
tierra (flota por encima) es aceptado sin error — es una
configuración electromagnéticamente distinta (una antena elevada
sobre el plano, no conectada a él), no un error de geometría. No se
probó en esta investigación un conductor con ambos extremos
exactamente en `z=0` (un radial de pantalla de tierra, mecanismo
aparte de un `GW` común, vía el parámetro `rad_wire_count` de `GN`);
queda como decisión pendiente (ver más abajo), no como observación.

## 6. Orden de las tarjetas en un archivo NEC exportado

**Comportamiento documentado (convención estándar de un archivo de
entrada NEC2, no verificado contra un archivo `.nec` real en esta
investigación).** La sección de comentarios y geometría de un archivo
NEC2 se cierra con la tarjeta `GE` (fin de geometría, con el
indicador de plano de tierra); la tarjeta `GN` (tipo de tierra) va
**después** de `GE`, no antes. Esto es consistente con el orden ya
usado por las llamadas de `PyNecEngine._create_context`
(`geometry_complete(...)` se invoca antes que `gn_card(...)`, ver
secciones 3 y 4 arriba): en un futuro exportador NEC que agregue
soporte de tierra, la tarjeta `GE` debe escribirse antes que la
tarjeta `GN`, en ese orden, para reflejar la misma secuencia lógica
que ya usa el motor.

El exportador NEC actual (`src/antsim/exporters/nec.py`) no emite
ninguna tarjeta `GN` hoy (solo `"GE 0"` fijo, para espacio libre);
agregar `GN` para tierra queda para la implementación de la fase 7A,
no de este documento.

## Decisiones pendientes de AntSim (no resueltas por esta investigación)

Estas son elecciones de alcance o de diseño para AntSim, no
propiedades de NEC2 ni de PyNEC observadas o documentadas arriba:

- Si un conductor con ambos extremos exactamente en `z=0` (radial de
  pantalla de tierra) debe rechazarse explícitamente por AntSim, o
  simplemente no soportarse por ahora sin una validación dedicada
  (esta investigación no determinó cómo se comporta NEC2 en ese caso
  exacto).
- Si AntSim debe validar la restricción de la sección 5
  (conductores en `z >= 0` cuando hay tierra) en el dominio, antes de
  llamar a PyNEC, para reemplazar el `RuntimeError: Unknown exception`
  nativo por un error claro — esta investigación demuestra que hace
  falta hacerlo (el error nativo no distingue causas ni da un mensaje
  útil), pero el mensaje y el punto exacto de validación quedan para
  la implementación.
- Si la densidad de segmentación uniforme `lambda/160` (ADR 0007),
  validada originalmente solo en espacio libre, se acepta también
  para geometrías con tierra perfecta sin un estudio de convergencia
  dedicado, apoyándose únicamente en la estabilidad observada en la
  sección 3 (una sola geometría vertical simple), o si se considera
  insuficiente y se pide un estudio propio antes de aceptarlo con
  carácter general.
- Cómo representar en el dominio y en el esquema `.antsim` el entorno
  de simulación (espacio libre / tierra perfecta / tierra real), y
  cómo validar la geometría en consecuencia — **fuera del alcance de
  este documento**, que es puramente de investigación; no se agrega
  aquí ningún código de dominio.
