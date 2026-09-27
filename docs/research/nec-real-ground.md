# Tierra real en PyNEC/NEC2++: investigación previa a la fase 7B

Este documento registra la investigación realizada **antes** de
diseñar `RealGroundEnvironment`. No se agregó ningún código de
producción, no se creó `RealGroundEnvironment`, no se modificó el
dominio, el esquema, el motor, el exportador ni ninguna prueba del
repositorio. Toda la evidencia empírica se obtuvo con dos scripts
descartables, ejecutados fuera del repositorio contra el PyNEC ya
instalado en `.venv`; esos scripts no se incorporaron al proyecto.

Se aplica el mismo criterio que
`docs/research/nec-ground-configuration.md` (fase 7A): separar
explícitamente **documentación primaria**, **observación empírica** y
**decisión propuesta para AntSim** (todavía no tomada, solo
propuesta).

## Entorno y versiones probadas

- Python: 3.13.15
- PyNEC: 2.3.4 (la misma versión ya usada en toda la fase 7A)
- Plataforma: Windows 11 x64
- Geometría base: monopolo vertical de (0,0,0) a (0,0,5.03) m, radio
  0.001 m, 38 segmentos, alimentado en el segmento 1 — la misma
  geometría ya validada en la fase 7A
  (`examples/monopole-20m-perfect-ground.antsim`).
- Suelo de prueba: permitividad relativa 13.0, conductividad
  0.005 S/m (valores de "tierra promedio" ya sugeridos en la
  consigna, y coincidentes con los valores de referencia habituales
  en la literatura de NEC2 para suelo agrícola promedio).
- Todas las corridas relevantes se repitieron con un contexto nuevo
  (`nec_context()` recién creado) para confirmar reproducibilidad; se
  indica explícitamente en cada caso.

## Fuentes primarias consultadas

- [Ground Parameters (GN)](https://www.nec2.org/part_3/cards/gn.html)
  — tarjeta `GN`, campos y valores de `ground_type`.
- [Geometry End (GE)](https://www.nec2.org/part_3/cards/ge.html) —
  tarjeta `GE`, significado de `gpflag` (0, 1, -1).
- [SOMNEC input for Sommerfeld/Norton ground method](https://www.nec2.org/part_3/somnec.html)
  — generación de las tablas de interpolación y el archivo `TAPE21`.
- [NEC-2 Manual, Part III: User's Guide](https://www.nec2.org/other/nec2prt3.pdf)
  (manual histórico completo, como respaldo de las páginas
  individuales anteriores).
- [python-necpp `nec_context.i`](https://github.com/tmolteno/python-necpp/blob/master/PyNEC/interface_files/nec_context.i)
  — firma exacta de `gn_card`/`geometry_complete` tal como las expone
  PyNEC (confirma que coincide con la tarjeta NEC2 clásica, sin
  reinterpretación propia de esta capa Python).
- [necpp (tmolteno), repositorio del motor C++ que usa PyNEC](https://github.com/tmolteno/necpp)
  — para verificar si Sommerfeld/Norton está incorporado
  internamente o requiere un archivo `TAPE21` externo (ver hallazgo
  empírico más abajo: no se encontró documentación concluyente sobre
  esto en el propio repositorio, así que se resolvió empíricamente).
- ["A Ground Is Just a Ground" (W4RNL)](http://www.antentop.org/w4rnl.001/amod11.html)
  — guía práctica sobre los límites de validez del método de
  coeficiente de reflexión frente a Sommerfeld-Norton.
- [OpenNEC issue #14](https://github.com/maurymarkowitz/OpenNEC/issues/14)
  ("All GN grounds silently produce free-space results on the
  sequential path") — de un fork distinto (OpenNEC, no
  tmolteno/necpp), pero motivó específicamente la prueba de
  `ground_type` desconocido de la sección 6, que confirmó un problema
  análogo en la instalación de PyNEC de este proyecto (ver más
  abajo).

## Matriz de métodos

| Método | `ground_type` (I1 de `GN`) | Documentación | Archivo externo requerido | Observado en esta instalación |
|---|---:|---|---|---|
| Espacio libre | `-1` | Anula la tierra; usado ya en fase 7A | No | Ya validado (fase 7A) |
| Tierra perfecta | `1` | Conductor perfecto, sin pérdidas | No | Ya validado (fase 7A) |
| Tierra finita, coeficiente de reflexión | `0` | Aproximación rápida de Fresnel en campo cercano | No | **Probada; ver limitación crítica abajo** |
| Tierra finita, Sommerfeld-Norton | `2` | Solución más exacta, más lenta | Según el manual histórico de NEC2, sí (`TAPE21`, generado por `SOMNEC`) | **Se ejecutó sin ningún archivo externo** (ver hallazgo) |

## Hallazgo clave: `TAPE21`/`SOMNEC` no fue necesario

**Documentación.** El manual histórico de NEC2 (Fortran) indica que
el método Sommerfeld/Norton requiere un archivo `TAPE21` generado
previamente por el programa separado `SOMNEC`.

**Observación empírica.** Se llamó a `gn_card(2, 0, 13.0, 0.005, 0.0,
0.0, 0.0, 0.0)` sin crear ni referenciar ningún archivo `TAPE21`, y
la simulación se ejecutó y devolvió un resultado numérico sin ningún
error relacionado con archivos faltantes.

**Interpretación (no confirmada por el código fuente).** NEC2++ (o
esta versión de PyNEC) parece calcular las tablas de Sommerfeld-Norton
internamente, sin depender de un archivo externo — un comportamiento
ya documentado para el port `nec2c` (que incorporó `SOMNEC`
directamente como función interna). No se confirmó esto leyendo el
código fuente de `necpp` línea por línea; queda como pregunta abierta
si esta instalación específica de PyNEC usa la misma estrategia u otra
equivalente. Lo que sí es una observación firme: **no hace falta que
AntSim gestione ningún archivo `TAPE21` ni invoque `SOMNEC`
externamente** para obtener un resultado de `gn_card(2, ...)` en esta
instalación.

## Experimentos y resultados

Todos los valores fueron reproducidos dos veces (contexto nuevo cada
vez) con resultado idéntico, salvo que se indique lo contrario.

### 1. Monopolo — tierra perfecta (control)

```python
context.geometry_complete(1)
context.gn_card(1, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
```

```text
33.78666408428509 - 15.623641070043119j ohm
```

Coincide exactamente con el valor ya documentado en la fase 7A.
Confirma que el script reproduce correctamente el comportamiento ya
validado antes de introducir tierra real.

### 2. Monopolo — tierra finita, coeficiente de reflexión (`ground_type=0`)

```python
context.geometry_complete(1)
context.gn_card(0, 0, 13.0, 0.005, 0.0, 0.0, 0.0, 0.0)
```

```text
299.7466157684757 - 1541.8057944205052j ohm
```

**Esto es fisicamente sospechoso.** Un monopolo sobre tierra real con
estos parámetros debería tener una resistencia de entrada más alta
que sobre tierra perfecta (pérdidas de tierra), pero del orden de
decenas u pocas centenas de ohm, no una reactancia de más de mil
ohm. Ver la limitación crítica más abajo: el conductor está
alimentado exactamente en `z=0`, y la documentación (sección
siguiente) advierte que el método de coeficiente de reflexión pierde
validez cerca del suelo.

### 3. Monopolo — Sommerfeld-Norton (`ground_type=2`)

```python
context.geometry_complete(1)
context.gn_card(2, 0, 13.0, 0.005, 0.0, 0.0, 0.0, 0.0)
```

```text
243.37543597947933 - 455.3675552763634j ohm  (~32 ms, frente a ~2 ms de los demás métodos)
```

Una resistencia de entrada mucho más alta que sobre tierra perfecta
(243 Ω contra 34 Ω) es consistente con un hecho ya conocido en la
práctica radioaficionada: un monopolo sin un sistema de radiales
sobre tierra con pérdidas tiene una resistencia de pérdida de tierra
considerable en el punto de alimentación. Esto es **más plausible
físicamente** que el resultado del método de coeficiente de
reflexión de la sección 2.

**Tiempo de cómputo:** Sommerfeld-Norton fue consistentemente ~15-20
veces más lento que los otros métodos (30-55 ms contra 1-6 ms) en
esta instalación, para una sola frecuencia. Confirma la documentación
("más exacto, pero más lento").

### 4. Varias frecuencias en un mismo contexto (barrido)

Los tres métodos con tierra (perfecta, reflexión, Sommerfeld-Norton)
se ejecutaron sin error dentro de un único contexto con
`fr_card(0, 5, 13.5, 0.5)` (5 puntos, 13.5 a 15.5 MHz).

**Hallazgo importante:** al comparar cada punto del barrido con una
simulación independiente de un solo punto a esa misma frecuencia:

- **Coeficiente de reflexión (`ground_type=0`):** coincide
  exactamente en los 5 puntos. El método no depende de tablas
  precalculadas por frecuencia, así que no hay ningún riesgo de
  "frecuencia congelada".
- **Sommerfeld-Norton (`ground_type=2`):** coincide exactamente solo
  en el **primer** punto del barrido (13.5 MHz); en los cuatro
  puntos siguientes, el valor del barrido y el valor independiente
  **difieren** (por ejemplo, a 14.0 MHz: barrido
  246.30 - j466.60 ohm contra punto independiente
  245.69 - j465.68 ohm; diferencia de ~0.6 Ω en resistencia y ~0.9 Ω
  en reactancia, creciendo levemente hacia el final del barrido).

Esto sugiere que las tablas de Sommerfeld-Norton podrían calcularse
una sola vez (probablemente a partir de la primera frecuencia del
`FR`) y reutilizarse o interpolarse para las frecuencias siguientes
del mismo barrido, en vez de recalcularse exactamente en cada una. No
se confirmó la causa exacta leyendo el código fuente; es una
observación empírica con una diferencia numérica pequeña pero real,
no despreciable si se necesita precisión estricta por punto.

### 5. Llamadas repetidas con contextos nuevos

Confirmado: tanto el coeficiente de reflexión como Sommerfeld-Norton
dieron resultados idénticos entre dos contextos `nec_context()`
recién creados, con los mismos parámetros. No hay estado global
compartido entre contextos que afecte la reproducibilidad.

### 6. Parámetros inválidos

| Caso | Resultado |
|---|---|
| `epsr = 0.0` | `RuntimeError: Unknown exception` (NEC2++ lo rechaza) |
| `epsr = -1.0` | **Sin excepción**; devuelve un resultado numérico (1342.64 - j1856.76 ohm) sin ninguna advertencia |
| `sigma = -0.005` | **Sin excepción**; devuelve un resultado numérico. Es la codificación documentada de "constante dieléctrica compleja EPSR - \|SIG\|", no un error, pero cambia el significado de los parámetros sin ningún aviso |
| `epsr = nan` | **Sin excepción**; devuelve `nan+nanj` (propaga el NaN en silencio) |
| `sigma = inf` | **Sin excepción**; devuelve `nan+nanj` |
| `ground_type = 3` (desconocido) | **Sin excepción; devuelve exactamente el mismo valor que tierra perfecta** (`33.78666408428509 - 15.623641070043119j`) |
| `ground_type = 99` (desconocido) | Igual que el anterior: mismo valor que tierra perfecta |
| `ground_type = -2` (desconocido) | Igual que el anterior: mismo valor que tierra perfecta |

**Este último hallazgo es el más importante de toda la investigación
para el diseño de AntSim.** Un `ground_type` no reconocido no produce
ningún error: PyNEC/NEC2++ cae en silencio a un comportamiento
equivalente al de tierra perfecta. Esto coincide con un problema
reportado de forma independiente en otro fork de NEC2
(`OpenNEC issue #14`, citado arriba), aunque en un repositorio
distinto al que usa PyNEC. **AntSim no puede confiar en que PyNEC
rechace un `ground_type` inválido**: la validación debe hacerse en el
dominio de AntSim, mediante una **selección exhaustiva** (un `Enum`
cerrado con exactamente los valores conocidos y válidos, nunca un
entero crudo pasado sin validar a `gn_card`), antes de llamar a
PyNEC.

De la misma forma, `epsr<=0`, `sigma<0` y valores no finitos deben
validarse en el dominio: PyNEC solo rechaza `epsr=0` (con una
excepción nativa sin mensaje útil, igual que el `RuntimeError` ya
documentado en la fase 7A para geometría inválida); todo lo demás
pasa sin aviso.

### Radiales (`rad_wire_count`, exploración parcial, no concluyente)

Con `rad_wire_count=4` y radios de pantalla/hilo en cero (valores
degenerados), el resultado fue `nan+nanj` (silencioso, sin
excepción). Con `rad_wire_count=4`, radio de pantalla 10 m y radio de
hilo 0.001 m (valores razonables), el resultado fue **exactamente
igual** al de tierra perfecta sin radiales (`33.78666408428509 -
15.623641070043119j`), con `ground_type=0` (coeficiente de
reflexión). Esto podría ser el comportamiento documentado de una
"pantalla de radiales" (aproximar la tierra como un reflector
perfecto dentro del radio de la pantalla, una práctica real en
antenas verticales de radioaficionado), pero **no se confirmó** con
una fuente primaria dedicada ni con más de un caso de prueba. Los
radiales quedan explícitamente fuera del alcance de esta
investigación (ver AGENTS.md: "no hay radiales/mallas" ya listado
como límite de la fase 7A, y se mantiene igual aquí).

### `geometry_complete(-1)`: no es lo que parecía

La documentación de la tarjeta `GE` distingue tres valores para
`gpflag`, no dos:

- `0`: sin plano de tierra.
- `1`: plano de tierra presente; **la corriente en los segmentos que
  tocan el suelo se interpola hacia su imagen** (esto es exactamente
  lo que ya usa `PyNecEngine` desde la fase 7A, y coincide con el
  mensaje ya observado de 4nec2: *"WHERE WIRE ENDS TOUCH GROUND,
  CURRENT WILL BE INTERPOLATED TO IMAGE"*, ver
  `docs/validation/monopole-perfect-ground-4nec2.md`).
- `-1`: plano de tierra presente, pero **la corriente en los
  segmentos que tocan el suelo va a cero en el suelo**, sin
  interpolación hacia la imagen.

Al probar `geometry_complete(-1)` con el monopolo (alimentado
exactamente en el segmento que toca tierra), el resultado fue
`49.79 - j14796.06 ohm` — el mismo valor sin sentido físico ya
observado en la fase 7A para la combinación incorrecta `GE(0)` +
`GN(1)`. **Esto no es un error ni una limitación de PyNEC**: es el
uso incorrecto de `-1` para un caso donde el conductor está
justamente *alimentado* en el punto que toca tierra, y forzar la
corriente a cero ahí es física y numéricamente inválido para ese
caso. `geometry_complete(-1)` describe un escenario distinto (un
conductor que solo *toca* el suelo sin estar alimentado ahí, por
ejemplo un mástil de soporte), que no aplica a los modelos de AntSim.
**Conclusión: para AntSim, `geometry_complete(1)` sigue siendo la
única opción correcta cuando hay un plano de tierra**, tal como ya se
decidió en la fase 7A; `-1` no debe usarse.

## Segundo modelo sensible al suelo: dipolo horizontal

Se usó el mismo dipolo de referencia ya validado (brazo de 5.03 m,
101 segmentos, alimentado en el segmento 51, 14.15 MHz), pero
elevado a una altura `h` sobre el plano de tierra (`z = h` en ambos
extremos), en vez de en `z=0`. Se probaron dos alturas, justificadas
por el umbral documentado de validez del método de coeficiente de
reflexión ("pierde precisión por debajo de aproximadamente 0.2
longitudes de onda"): a 14.15 MHz, `lambda ~= 21.19` m, por lo que
`0.2 lambda ~= 4.24` m.

- **Altura alta: 10 m** (`~0.47 lambda`, muy por encima del umbral).
- **Altura baja: 1 m** (`~0.047 lambda`, muy por debajo del umbral).

| Entorno | h = 10 m | h = 1 m |
|---|---:|---:|
| Espacio libre (control) | 67.43 - j31.25 ohm | (no aplica; sin tierra) |
| Tierra perfecta | 68.38 - j48.67 ohm | 4.70 - j35.10 ohm |
| Tierra real, coeficiente de reflexión | 66.69 - j41.55 ohm | 39.57 - j11.61 ohm |
| Tierra real, Sommerfeld-Norton | 66.57 - j41.36 ohm | 56.80 - j19.45 ohm |

**A 10 m**, el coeficiente de reflexión y Sommerfeld-Norton coinciden
razonablemente entre sí (diferencia de 0.12 Ω en resistencia, 0.19 Ω
en reactancia) — consistente con la documentación, que dice que el
método rápido es adecuado por encima del umbral.

**A 1 m**, el coeficiente de reflexión y Sommerfeld-Norton
**difieren notablemente** entre sí (17.23 Ω en resistencia, 7.84 Ω en
reactancia) — una confirmación directa, con la propia geometría de
AntSim, de la advertencia documentada: el método rápido se degrada
por debajo de `~0.2 lambda`, y Sommerfeld-Norton es la referencia más
confiable en ese régimen.

**Esto demuestra una diferencia real y medible entre los tres
entornos** (espacio libre, tierra perfecta, tierra real por ambos
métodos), no solo un cambio de forma en el número — cumple el
objetivo de esta sección sin pretender validar todavía patrones de
radiación ni ganancia.

## Tarjetas NEC correspondientes (documentación, no implementación)

Para un futuro exportador (no implementado en esta tarea):

```text
# Tierra real, coeficiente de reflexión (aproximación rápida)
GE 1
GN 0 0 0 0 13.0 0.005 0 0 0 0

# Tierra real, Sommerfeld-Norton
GE 1
GN 2 0 0 0 13.0 0.005 0 0 0 0
```

Mismo orden ya establecido en la fase 7A (`GE` antes de `GN`, ambas
después de la última `GW` y antes de `EX`/`FR`). La tarjeta `GN`
completa tiene **cuatro campos enteros (I1-I4)** seguidos de **seis
campos flotantes (F1-F6)**: I1=tipo de tierra, I2=cantidad de
radiales, I3 e I4 reservados/en blanco, F1=permitividad relativa,
F2=conductividad, F3-F6=0 (sin pantalla de radiales ni segundo medio)
para el caso homogéneo simple que se investiga aquí. Esto difiere de
la firma de `gn_card()` en PyNEC, que solo recibe ocho argumentos
posicionales (`ground_type, rad_wire_count, F1, F2, F3, F4, F5, F6`,
sin I3/I4): la llamada Python y la tarjeta NEC de texto no tienen el
mismo número de campos, y no deben confundirse una con la otra.

## Limitaciones de esta investigación

- No se leyó el código fuente de `necpp` línea por línea para
  confirmar mecánicamente por qué Sommerfeld-Norton no requirió
  `TAPE21`, ni por qué el barrido de Sommerfeld-Norton no coincide
  exactamente con puntos independientes: son observaciones empíricas
  consistentes, no explicaciones verificadas en el código.
- Los radiales (`rad_wire_count`, F3/F4 de `GN`) se probaron de forma
  mínima y no concluyente; quedan fuera del alcance de esta
  investigación y de la propuesta de la sección siguiente.
- No se investigó el "segundo medio" de `GN` (F3-F6 alternativos:
  constante dieléctrica, conductividad, distancia de unión y
  profundidad de un segundo medio) ni tierras estratificadas.
- No se comparó todavía ningún resultado de tierra real contra 4nec2
  (a diferencia de la fase 7A, que sí tuvo esa validación externa);
  eso queda explícitamente para cuando se implemente 7B.
- Solo se probó una combinación de permitividad/conductividad
  ("tierra promedio"); no se exploró cómo cambian los resultados con
  otros valores típicos (tierra muy seca, agua de mar, etc.).

## Riesgos identificados

1. **El método de coeficiente de reflexión puede dar resultados sin
   sentido físico para un conductor alimentado exactamente en
   `z=0`** (el caso más simple y más probable de probar primero: un
   monopolo). Ofrecerlo sin una advertencia explícita sería
   engañoso.
2. **Un `ground_type` inválido no produce ningún error**: cae en
   silencio a un resultado idéntico al de tierra perfecta. Si AntSim
   no valida esto por su cuenta, un error de programación interno (no
   del usuario) podría pasar completamente desapercibido.
3. **Sommerfeld-Norton en un barrido de varias frecuencias no siempre
   coincide exactamente con el resultado de cada frecuencia evaluada
   de forma independiente.** Este hallazgo se marcó originalmente como
   un **bloqueador** porque afecta directamente el patrón ya existente
   de `PyNecEngine.simulate_sweep` (un único contexto reutilizado para
   todo el barrido), y porque para el monopolo alimentado en z=0
   (sección 4 de "Experimentos y resultados") la discrepancia fue
   sistemática y no despreciable (~0.6-0.9 Ω). La validación externa
   con 4nec2 y la re-medición con el dipolo a 10 m, ya registradas en
   "Validación externa con 4nec2" más abajo, mostraron en cambio una
   discrepancia del orden de 1e-7-1e-8 Ω (ruido de punto flotante) para
   esa geometría elevada — es decir, la magnitud del efecto depende de
   la geometría, no es un bloqueador uniforme. Aun así, **ya se tomó
   una decisión de arquitectura** (contexto NEC nuevo por frecuencia
   para Sommerfeld-Norton, sin excepciones por geometría) precisamente
   para no depender de esa variabilidad; ver esa misma sección para el
   razonamiento completo.
4. **Costo computacional de Sommerfeld-Norton**: 15-20 veces más
   lento que tierra perfecta o coeficiente de reflexión, incluso para
   una sola frecuencia. Un barrido de muchos puntos con
   Sommerfeld-Norton podría volverse notablemente lento, y más aún si
   la estrategia de contexto nuevo por frecuencia del punto anterior
   resulta necesaria.
5. **`sigma<0`, `NaN` e `Inf` no se rechazan de forma confiable en
   PyNEC** (y `epsr<=0` solo se rechaza parcialmente: PyNEC rechaza
   `epsr=0` pero acepta valores negativos sin aviso): la validación de
   dominio es obligatoria, no opcional, igual que ya lo es la
   validación de geometría contra el plano de tierra (fase 7A). La
   regla exacta para `conductivity=0` queda deliberadamente pendiente
   (ver la sección de validaciones propuestas más abajo).

## Recomendación de alcance para la fase 7B

De las cuatro alternativas planteadas, se recomienda la
**alternativa 2: soportar únicamente Sommerfeld-Norton en la primera
implementación de 7B**, dejando el método de coeficiente de reflexión
como trabajo posterior. Razones:

1. **Resultados no físicos para el monopolo alimentado en `z=0`.**
   Este es, dentro de AntSim, el caso más simple y más probable de
   probarse primero (un monopolo vertical alimentado en la base, la
   misma geometría ya usada en toda la fase 7A), y es exactamente
   donde el coeficiente de reflexión dio un resultado sin sentido
   físico (sección 2: 299.75 - j1541.81 ohm). Ofrecer ese método como
   parte de la primera entrega de 7B arriesga que el primer resultado
   que vea el usuario con tierra real sea directamente engañoso.
2. **Pérdida de validez cerca del suelo, documentada y observada.**
   La documentación primaria (W4RNL, antentop.org) ya advierte que el
   coeficiente de reflexión pierde precisión por debajo de
   `~0.2 lambda`, y esta investigación lo confirmó empíricamente con
   la geometría propia de AntSim (dipolo horizontal a 1 m, sección
   "Segundo modelo sensible al suelo": divergencia de 17.23 Ω en
   resistencia frente a Sommerfeld-Norton).
3. **Necesidad futura de definir restricciones de altura.** Ofrecer
   el coeficiente de reflexión de forma responsable requeriría antes
   decidir una regla de validación de dominio (por ejemplo, advertir
   o rechazar conductores por debajo de cierta altura eléctrica sobre
   el plano de tierra, ver pregunta abierta 5 más abajo) — una
   decisión de diseño que todavía no se tomó y que no debería
   bloquear la primera entrega de 7B.

Sommerfeld-Norton, en cambio, dio resultados físicamente plausibles
tanto para el monopolo como para el dipolo a ambas alturas probadas,
y se ejecutó sin depender de ningún archivo externo (`TAPE21`) en
esta instalación. Su costo es mayor (15-20 veces más lento) y tiene el
bloqueador de barrido ya señalado en "Riesgos identificados", que debe
resolverse (o al menos mitigarse con un contexto por frecuencia) antes
de dar por cerrada la primera implementación de 7B.

El coeficiente de reflexión no se descarta de forma permanente: queda
como una extensión razonable para una fase posterior, una vez que
AntSim tenga una regla de validación de altura mínima bien
fundamentada y, probablemente, sea ofrecido solo para geometrías que
la cumplan.

## Propuesta para `RealGroundEnvironment` (sin implementar)

Lo siguiente es una **propuesta**, no una decisión tomada ni código
agregado.

### Estructura sugerida

Siguiendo el mismo patrón que `FreeSpaceEnvironment` y
`PerfectGroundEnvironment` (dataclass inmutable, sin herencia
compartida):

```python
@dataclass(frozen=True)
class RealGroundEnvironment:
    relative_permittivity: float
    conductivity_s_per_m: float
    method: RealGroundMethod  # enum: REFLECTION_COEFFICIENT | SOMMERFELD_NORTON
```

`method` como un `Enum` explícito (no un booleano ni un string suelto)
para que la selección entre ambos métodos sea un valor de dominio
propio, no un detalle de la tarjeta NEC filtrado hacia arriba.

### Validaciones sugeridas

- `relative_permittivity`: finito y estrictamente positivo (rechaza
  `<=0`, coherente con que PyNEC rechaza `0` con una excepción nativa
  y acepta silenciosamente valores negativos sin sentido).
- `conductivity_s_per_m`: la regla exacta para el límite inferior
  queda **deliberadamente pendiente** de documentación primaria y
  prueba adicional; este documento no afirma todavía que
  `conductivity=0` deba rechazarse. `sigma=0` podría representar
  legítimamente un dieléctrico homogéneo sin pérdidas (un caso límite
  válido de la formulación física, distinto de "no hay tierra"), pero
  eso no se investigó ni se confirmó en esta tarea — queda como
  pregunta abierta (ver más abajo) a resolver con una fuente primaria
  o una prueba dedicada antes de fijar la validación de dominio.
  Lo que sí se recomienda rechazar desde ahora, sin ambigüedad:
  - **`conductivity < 0`**: aunque PyNEC lo acepta como una
    codificación especial documentada (constante dieléctrica compleja
    `EPSR - |SIG|`), AntSim no debe reexponer ese atajo sin una
    decisión propia y deliberada al respecto;
  - **`NaN` e `Inf`**: PyNEC los propaga en silencio a un resultado
    `nan+nanj` sin ninguna advertencia (sección "Parámetros
    inválidos"), así que el dominio debe rechazarlos explícitamente,
    sea cual sea la decisión final sobre `conductivity=0`.
- `method`: solo los dos valores del enum; cualquier otro valor debe
  ser imposible de construir (ventaja de un `Enum` de Python sobre un
  entero crudo).
- Mantener, sin cambios, la validación ya existente de conductores
  contra el plano `z=0` (fase 7A): un entorno con tierra real activa
  esa misma restricción, igual que tierra perfecta.

### Representación JSON: se propone esquema v3, no extender v2

A diferencia de una versión anterior de este documento, se propone
ahora crear un **nuevo `schema_version = 3`**, en vez de extender v2,
manteniendo la misma progresión ya establecida por AGENTS.md y el
roadmap del proyecto:

- **v1**: espacio libre implícito (sin clave `environment`; se
  interpreta siempre como `free_space` al leer, tal como ya funciona
  hoy).
- **v2**: `simulation.environment` obligatorio, con
  `kind: "free_space"` o `kind: "perfect_ground"` — el esquema ya
  implementado en la fase 7A, sin cambios.
- **v3** (propuesto): agrega `kind: "real_ground"` con sus propios
  campos adicionales:

```json
"environment": {
    "kind": "real_ground",
    "relative_permittivity": 13.0,
    "conductivity_s_per_m": 0.005,
    "method": "reflection_coefficient"
}
```

o con `"method": "sommerfeld_norton"`.

Motivo del cambio de criterio respecto de la propuesta original de
extender v2: `real_ground` no es una variante más del mismo objeto
`environment` con los mismos supuestos de todos los `kind` ya
existentes (ambos sin parámetros numéricos propios); introduce
parámetros físicos con su propia validación y un método de cálculo
seleccionable, lo bastante distinto como para justificar una versión
de esquema propia, siguiendo la misma cautela que AGENTS.md ya exige
para cualquier cambio de esquema ("explicit authorization; a
documented schema-version decision; backward-compatibility analysis;
migration or compatibility tests").

El lector debería aceptar `schema_version` 1, 2 y 3; un escritor
nuevo (una vez implementado 7B) emitiría siempre 3, migrando
automáticamente proyectos v1 y v2 al guardarlos de nuevo, exactamente
con el mismo patrón de migración transparente ya usado entre v1 y v2
en la fase 7A.

Esto sigue siendo una **propuesta**, no una decisión: requeriría la
misma autorización explícita, análisis de compatibilidad hacia atrás
y pruebas de migración que ya se pidieron y se dieron para crear el
esquema v2 en la fase 7A.

### Compatibilidad con proyectos v1 y v2 existentes

Ningún proyecto v1 o v2 ya guardado se vería afectado: seguirían
leyéndose exactamente igual (v1 como espacio libre implícito; v2 con
`free_space` o `perfect_ground` explícitos). Un lector que todavía no
reconozca `schema_version = 3` ni `kind: "real_ground"` (por ejemplo,
antes de que `RealGroundEnvironment` esté implementado) debería
rechazar esa versión o esa clave como "no soportada", igual que ya
rechaza cualquier `schema_version` o `kind` desconocido hoy — nunca
interpretarlos silenciosamente como espacio libre o tierra perfecta.

### Errores esperados

Siguiendo el mismo estilo ya usado en la fase 7A:

- `ValueError` de dominio para `relative_permittivity<=0`,
  `conductivity_s_per_m<=0`, o valores no finitos, con el mensaje
  identificando el campo inválido — **antes** de llamar a PyNEC,
  dado que la investigación confirmó que PyNEC no rechaza estos casos
  de forma confiable.
- `ProjectFormatError` para un `kind` desconocido o campos faltantes
  en `simulation.environment` al leer un archivo `.antsim`, igual que
  ya existe para `free_space`/`perfect_ground`.
- Un error explícito (todavía sin decidir si `ValueError` o una
  excepción propia) si se intentara usar `RealGroundEnvironment` con
  `PyNecEngine` antes de que el motor lo soporte — análogo al
  `ValueError` que hoy ya lanza `_create_context` para un tipo de
  entorno no reconocido.

### Modelo de referencia sugerido para validar contra 4nec2 (fase 7B)

Se recomienda usar el **dipolo horizontal a 10 m de altura** ya
probado en esta investigación (brazo de 5.03 m, 101 segmentos,
alimentado en el segmento 51, 14.15 MHz, `epsr=13.0`,
`sigma=0.005 S/m`) como primer modelo de validación de tierra real,
**no** el monopolo alimentado en la base: el monopolo es exactamente
el caso donde el método de coeficiente de reflexión dio un resultado
sospechoso (sección 2), así que no sería un punto de partida limpio
para una primera validación cruzada con 4nec2. El dipolo a 10 m ya
mostró, en esta misma investigación, que ambos métodos de tierra real
coinciden razonablemente entre sí (66.69 - j41.55 contra
66.57 - j41.36 ohm), lo que da una expectativa clara y verificable
para comparar contra 4nec2 en la próxima fase.

No se proponen perfiles predefinidos de suelo ("tierra húmeda",
"tierra seca", "agua de mar", etc.) en este documento: harían falta
fuentes y validación propias antes de fijar esos valores, y la
consigna de esta tarea pide explícitamente no hacerlo todavía. Puede
sugerirse como trabajo posterior, una vez que el modelo básico de
permitividad/conductividad esté implementado y validado.

## Preguntas abiertas

1. ¿Por qué el barrido de Sommerfeld-Norton no coincide exactamente
   con las simulaciones de un solo punto en la misma frecuencia?
   ¿Tablas calculadas una sola vez, interpolación, u otra causa? (Ver
   la hipótesis principal en "Riesgos identificados", marcada como
   bloqueador de implementación, y el plan de verificación en
   "Próxima investigación" más abajo.)
2. ¿Esta instalación de PyNEC calcula Sommerfeld-Norton internamente
   (como `nec2c`), o usa algún mecanismo de caché/archivo temporal no
   visible desde Python? ¿Es igual en otras versiones de PyNEC/NEC2++?
3. ¿Qué significa exactamente `conductivity_s_per_m=0` en cada
   método, y debería admitirse? Se documentó como posible dieléctrico
   sin pérdidas (ver "Validaciones sugeridas"), pero la regla exacta
   sigue pendiente de una fuente primaria o una prueba dedicada.
4. ¿Cómo se comporta realmente una pantalla de radiales
   (`rad_wire_count>0` con F3/F4 válidos) frente a los dos métodos de
   tierra real? La observación de la sección de radiales no fue
   concluyente.
5. ¿Vale la pena, en el futuro (cuando se retome el coeficiente de
   reflexión, ya pospuesto), restringirlo a geometrías cuya altura
   mínima sobre tierra supere un umbral, validado en el dominio (por
   ejemplo, advertir o rechazar si algún conductor queda por debajo
   de `~0.2 lambda` con ese método)? Esta investigación sugiere que
   sería una protección razonable, pero no se diseñó todavía.
6. ¿4nec2 muestra el mismo comportamiento de barrido para
   Sommerfeld-Norton (reconstrucción o reutilización de datos por
   frecuencia), o es una particularidad de esta instalación de
   PyNEC/NEC2++? Sigue sin confirmarse: la validación externa
   registrada en "Validación externa con 4nec2" comparó valores
   puntuales de PyNEC (contexto fresco) contra 4nec2, no el barrido de
   contexto único de PyNEC contra un barrido nativo de 4nec2, así que
   esta pregunta puntual permanece abierta.

## Próxima investigación recomendada (antes de escribir dominio)

Antes de implementar cualquier código de `RealGroundEnvironment`, se
recomienda una segunda ronda de investigación, todavía sin escribir
dominio, enfocada en resolver el bloqueador de barrido y en preparar
la validación externa de 7B:

1. Comparar en 4nec2 el dipolo horizontal a 10 m (el modelo de
   referencia ya elegido arriba) contra los valores de esta
   investigación, para tierra perfecta, coeficiente de reflexión y
   Sommerfeld-Norton.
2. Comparar, dentro de PyNEC, cálculos puntuales independientes en
   varias frecuencias del mismo rango ya usado (13.5-15.5 MHz) contra
   los valores de barrido, ampliando la muestra de 5 puntos usada en
   esta investigación.
3. Comparar explícitamente barrido nativo (`fr_card` de varios puntos
   en un mismo contexto) frente a cálculos independientes por punto,
   para cuantificar la discrepancia de Sommerfeld-Norton con más
   resolución que la ya observada.
4. Medir tiempos de cómputo para barridos de 11, 81 y 201 puntos (los
   tamaños de barrido ya usados en proyectos existentes de AntSim, ver
   `SweepSettings`), tanto con un único contexto como con la
   estrategia candidata de un contexto nuevo por frecuencia, para
   cuantificar el costo real de mitigar el bloqueador.
5. Confirmar si 4nec2 también reconstruye o reutiliza datos de
   Sommerfeld-Norton por frecuencia dentro de un mismo barrido, o si
   recalcula exactamente en cada punto — esto ayudaría a decidir si la
   discrepancia observada es una particularidad de PyNEC/NEC2++ o un
   comportamiento esperado del método en general.

## Validación externa con 4nec2

Como continuación directa del punto 1 de "Próxima investigación
recomendada", se ejecutó manualmente 4nec2 5.9.3 sobre el modelo de
referencia ya elegido en esta investigación (dipolo horizontal a
10 m, 101 segmentos, alimentado en el segmento 51, tierra
Sommerfeld-Norton con permitividad relativa 13.0 y conductividad
0.005 S/m). Los valores de PyNEC usados en esta comparación son los
de contexto fresco por frecuencia
(`real-ground-independent-points.csv`, generado fuera del
repositorio), no los del barrido de contexto único, siguiendo desde
ya la estrategia que esta misma sección termina recomendando.

Ver `docs/validation/real-ground-dipole-4nec2.md` para el detalle
completo (geometría, tarjeta GN exacta, instrucciones de
reproducción y limitaciones); aquí se resume solo lo necesario para
la decisión de arquitectura.

### Validación puntual a 14.15 MHz

| Motor | Z (ohm) | ROE (50 ohm) |
|---|---|---:|
| PyNEC (contexto fresco) | 66.565039 - j41.357407 | 2.125991 |
| 4nec2 5.9.3 | 66.6 - j41.4 | 2.13 |

Diferencia (PyNEC menos 4nec2, con la precisión que 4nec2 reporta):
~0.035 Ω en R, ~-0.04 Ω en X. 4nec2 redondea R y X a un decimal y la
ROE a dos, así que la diferencia observada está dentro de esa
resolución de redondeo — no se puede afirmar, con estos datos, que
sea una discrepancia real entre motores en vez de un efecto de
redondeo de la lectura.

### Validación de barrido en tres frecuencias

| Frecuencia (MHz) | PyNEC R (Ω) | PyNEC X (Ω) | PyNEC ROE | 4nec2 R (Ω) | 4nec2 X (Ω) | 4nec2 ROE | diff R (Ω) | diff X (Ω) | diff ROE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13.5 | 60.299987 | -106.764239 | 5.638466 | 60.2981 | -106.78 | 5.64002 | 0.0019 | 0.0158 | -0.0016 |
| 14.5 | 69.958082 | -6.052230 | 1.420242 | 69.9534 | -6.0735 | 1.4203 | 0.0047 | 0.0213 | -0.0001 |
| 15.5 | 81.799524 | 97.183728 | 4.325267 | 81.7964 | 97.1602 | 4.32414 | 0.0031 | 0.0235 | 0.0011 |

Todas las diferencias son del orden de 0.002-0.024 Ω, consistentes
con la resolución de redondeo con que 4nec2 reporta sus resultados
(4-5 cifras significativas) y con las diferencias normales esperables
entre dos implementaciones independientes de NEC2 (PyNEC/necpp frente
al motor usado por 4nec2). **Esto confirma, con una fuente externa
independiente, que la llamada `gn_card(2, 0, 13.0, 0.005, 0.0, 0.0,
0.0, 0.0)` de PyNEC calcula Sommerfeld-Norton correctamente para este
modelo de referencia** — no solo que produce un número plausible,
como ya se sospechaba pero no se había podido confirmar en la
investigación original.

### Hallazgo de rendimiento (re-medido junto con esta validación)

- Aproximadamente 42 ms por punto en promedio, para el dipolo a 10 m
  con Sommerfeld-Norton.
- 11 puntos: ~0.45-0.50 s en total.
- 81 puntos: ~3.4 s en total.
- 201 puntos: ~8.5 s en total.
- **Crear un contexto NEC nuevo por frecuencia no es significativamente
  más lento que reutilizar un único contexto para todo el barrido**:
  en las mediciones repetidas la diferencia entre ambas estrategias
  estuvo dentro del ruido de medición (a veces una fue más rápida, a
  veces la otra). El tiempo está dominado por el cálculo de
  Sommerfeld-Norton en sí (~40 ms/punto), no por el costo de crear el
  contexto.

### Decisión de arquitectura para `RealGroundEnvironment`

**Decisión:** cuando `PyNecEngine.simulate_sweep` reciba una solicitud
con `RealGroundEnvironment` usando el método Sommerfeld-Norton, debe
crear un contexto NEC independiente por cada frecuencia del barrido,
en vez de reutilizar un único contexto con
`fr_card(0, points, start, step)` como ya hace hoy para espacio libre
y tierra perfecta.

Esta decisión prioriza la **consistencia** por sobre un posible ahorro
de rendimiento que, de todos modos, esta investigación no encontró: el
costo de contexto nuevo por frecuencia resultó equivalente al de
contexto único (sección anterior). Es una decisión deliberadamente
conservadora: aunque el dipolo a 10 m (el modelo de referencia de esta
fase, y el mismo validado aquí contra 4nec2) no mostró discrepancias
relevantes entre ambas estrategias de barrido (diferencias del orden
de 1e-7-1e-8 Ω, ruido de punto flotante), el monopolo alimentado en
z=0 estudiado antes en esta misma investigación sí mostró una
discrepancia sistemática y no despreciable (~0.6-0.9 Ω) entre el
barrido de contexto único y el cálculo independiente por frecuencia.
Como AntSim no puede garantizar que todo conductor con tierra real
quedará siempre lejos del plano de tierra (un monopolo alimentado en
la base, tocando z=0, es un caso de uso legítimo y esperado), la
estrategia de contexto nuevo por frecuencia se adopta de forma
general para Sommerfeld-Norton, no solo para las geometrías elevadas
que, como este dipolo, no la necesitarían.

## Plan incremental propuesto (sin comprometerse a fechas)

1. ~~Investigación cruzada con 4nec2~~ — hecha (ver "Validación
   externa con 4nec2" arriba y
   `docs/validation/real-ground-dipole-4nec2.md`), para el modelo de
   referencia (dipolo a 10 m) y Sommerfeld-Norton. Sigue pendiente
   validar externamente el coeficiente de reflexión (pospuesto, ver
   "Recomendación de alcance para la fase 7B") y confirmar si 4nec2
   reproduce el mismo comportamiento de barrido observado para el
   monopolo (pregunta abierta 6).
2. ~~Definir la política de barrido para Sommerfeld-Norton~~ — hecho:
   contexto nuevo por frecuencia, siempre (ver "Decisión de
   arquitectura" arriba).
3. Implementar `RealGroundEnvironment` en el dominio, con las
   validaciones ya propuestas arriba (incluida la decisión ya tomada
   sobre `conductivity=0`, si para entonces ya se resolvió esa
   pregunta abierta), sin tocar todavía `PyNecEngine` ni el
   exportador (mismo patrón ya usado en la fase 7A: dominio primero,
   motor después).
4. Diseñar y crear el `schema_version = 3` propuesto, con sus
   pruebas de migración y compatibilidad hacia v1/v2.
5. Extender `PyNecEngine` para simulación puntual con
   Sommerfeld-Norton.
6. Extender `PyNecEngine` para barrido, aplicando la política
   definida en el paso 2.
7. Extender el exportador NEC con las tarjetas `GN`/`GE`
   correspondientes.
8. Crear un ejemplo de proyecto y validarlo externamente con 4nec2,
   replicando el mismo rigor ya aplicado en
   `docs/validation/monopole-perfect-ground-4nec2.md`.
9. Ejecutar `scripts/build_windows.ps1` y el resto del checklist de
   release ya usado en fases anteriores, antes de dar por cerrada la
   fase 7B.

El coeficiente de reflexión, y los perfiles predefinidos de suelo, se
consideran explícitamente trabajo posterior a este plan, no parte de
la primera entrega de 7B (ver "Recomendación de alcance para la fase
7B").
