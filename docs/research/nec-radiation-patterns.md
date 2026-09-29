# Investigación: patrones de radiación en PyNEC/NEC2++

- Fecha de la investigación: 2026-09-29
- Rama: `research/radiation-patterns`
- Alcance: investigación y documentación únicamente. No se modificó
  código, pruebas, ejemplos, esquema, CLI, versión ni CHANGELOG. Todos
  los scripts experimentales se ejecutaron fuera del repositorio
  (`%TEMP%\yaas-radiation-research\`, eliminado al terminar) y no
  quedó ningún archivo `.py`/`.csv`/`.nec`/binario dentro del árbol
  del proyecto.
- Entorno de la investigación: PyNEC 2.3.4 instalado en `.venv`
  (mismo que usa `src/yaas/engines/pynec.py`), Python 3.13.15,
  Windows AMD64.

## 0. Resumen ejecutivo

PyNEC expone patrones de radiación mediante `rp_card()` +
`get_radiation_pattern(index)`. Se verificó que **`rp_card()` por sí
solo ya dispara la ejecución** en esta API (produce un patrón
recuperable de inmediato, idéntico al que se obtiene si además se
llama a `xq_card(0)`); ver §1.4 para la secuencia exacta probada.
Se verificó experimentalmente, sobre las llamadas de la API de PyNEC
2.3.4 (no sobre un archivo NEC de texto ni sobre otra implementación),
que invertir el orden `RP`/`EX` produce `NaN` silencioso, sin ninguna
excepción — ver §1.4 para la distinción entre lo que esto prueba sobre
la API de PyNEC y lo que **no** prueba sobre el orden de tarjetas de
un archivo NEC portable para otras aplicaciones. El array plano que
devuelven `get_gain_tot()`/`get_gain_horiz()`/`get_gain_vert()`/
`get_e_theta()`/etc. está en **orden columna-mayor (Fortran): theta
varía más rápido que phi** — confirmado por tres fuentes
independientes (documentación primaria de NEC2, código fuente de
NEC2++, y verificación empírica reproducible en este entorno, con
`n_theta=19 != n_phi=37`, ver §1.2). Existe un método de acceso
**`get_gain()`** que devuelve directamente una matriz 2D
`(n_theta, n_phi)` ya orientada correctamente, evitando tener que
razonar sobre el orden de aplanado. Se encontró un **crash real
(segmentation fault) del proceso Python**, no una excepción, al pasar
`n_theta` o `n_phi` negativos a `rp_card()`; se reprodujo únicamente
en subprocesos aislados y nunca debe probarse en el proceso principal
ni incorporarse como test normal de pytest (ver §1.6). YAAS deberá
validar estos parámetros en el dominio antes de llamar a PyNEC,
exactamente igual que ya valida otros parámetros de simulación. Todas
las recomendaciones de §4 son propuestas de diseño sin implementar;
ninguna decisión de esta investigación es definitiva.

## 1. Observaciones

### 1.1. API real de PyNEC 2.3.4 instalada

Métodos públicos relevantes de `PyNEC.nec_context` (listados con
`dir()` sobre una instancia real, no inferidos):

```text
rp_card, xq_card, get_radiation_pattern, get_gain_max, get_gain_min,
get_gain_mean, get_gain_sd, get_gain_lhcp_max/mean/min/sd,
get_gain_rhcp_max/mean/min/sd, get_norm_rx_pattern, get_near_field_pattern
```

Firma real de `rp_card` (vía `help()`, no adivinada):

```python
rp_card(
    calc_mode, n_theta, n_phi, output_format, normalization,
    D, A, theta0, phi0, delta_theta, delta_phi,
    radial_distance, gain_norm,
)
```

Trece argumentos posicionales. Es una diferencia importante frente al
formato de tarjeta NEC2 crudo (`RP I1 I2 I3 I4 F1 F2 F3 F4 F5 F6`,
donde `I4` es un único entero de cuatro dígitos `XNDA`): PyNEC
**desempaqueta `I4` en cuatro parámetros Python separados**
(`output_format`=X, `normalization`=N, `D`=D, `A`=A), igual de
distinto de la tarjeta cruda que ya se documentó para `gn_card()` en
`docs/research/nec-real-ground.md`. No debe reconstruirse manualmente
un entero XNDA de cuatro dígitos al llamar a `rp_card()` desde Python.

`xq_card(itmp1)`: un único entero. `itmp1=0` es el caso ya usado por
`PyNecEngine` (ejecutar sin generar cortes automáticos). `itmp1=1/2/3`
generan automáticamente cortes verticales en el plano XZ o YZ (ver
§1.2); no se investigó ese modo automático en profundidad porque
`rp_card()` ya cubre esos mismos cortes de forma explícita y más
flexible.

`get_radiation_pattern(index)` devuelve un objeto
`PyNEC.nec_radiation_pattern` (o `None` si el índice no tiene datos
válidos, ver §1.4) con estos métodos (listados con `dir()`):

```text
get_ntheta, get_nphi, get_theta_start, get_delta_theta,
get_phi_start, get_delta_phi, get_theta_angles, get_phi_angles,
get_gain, get_gain_tot, get_gain_horiz, get_gain_vert,
get_gain_lhcp_*/get_gain_rhcp_* (vía nec_context, no aquí),
get_e_theta, get_e_phi, get_e_r,
get_pol_axial_ratio, get_pol_tilt, get_pol_sense_index,
get_average_power_gain, get_average_power_solid_angle,
get_normalization_factor, get_rp_normalization, get_rp_output_format,
get_rp_ipd, get_rp_power_average, get_frequency, get_ground, get_range,
get_rp_normalization
```

### 1.2. Forma y orden de los arrays devueltos

- `get_theta_angles()` / `get_phi_angles()`: arrays 1D de longitud
  `n_theta` / `n_phi` respectivamente, en grados, ya expandidos desde
  `theta0`/`delta_theta` y `phi0`/`delta_phi` (no hace falta
  reconstruirlos manualmente).
- `get_gain_tot()`, `get_gain_horiz()`, `get_gain_vert()`,
  `get_e_theta()`, `get_e_phi()`, `get_e_r()`,
  `get_pol_axial_ratio()`, `get_pol_tilt()`, `get_pol_sense_index()`:
  arrays **1D planos** de longitud `n_theta * n_phi`.
- `get_gain()` (sin sufijo): devuelve una matriz **2D** de forma
  `(n_theta, n_phi)`, ya orientada de forma que
  `gain[theta_idx, phi_idx]` es directamente el valor correcto en esa
  dirección. Confirmado con evidencia primaria: el propio archivo de
  pruebas de PyNEC (`tests/test_radiation_pattern.py` en el sdist)
  incluye `test_gain_matrix_shape`, que afirma explícitamente
  `assert gains.ndim == 2` con el comentario "Gain should be a 2D
  matrix with shape (ntheta, nphi)".
- **Experimento decisivo con grilla no cuadrada** (dipolo horizontal
  de §2.1, para que `n_theta` y `n_phi` no puedan confundirse entre
  sí): se llamó a
  `rp_card(calc_mode=0, n_theta=19, n_phi=37, ...,
  delta_theta=10.0, delta_phi=10.0, ...)`. Con esos valores exactos,
  `rp.get_gain().shape` fue **`(19, 37)`** — es decir, el primer eje
  (longitud 19) corresponde a `theta` y el segundo eje (longitud 37) a
  `phi`, coherente con `n_theta=19` y `n_phi=37` tal como se pasaron a
  `rp_card()`. Los ángulos correspondientes se obtuvieron con
  `rp.get_theta_angles()` (longitud 19) y `rp.get_phi_angles()`
  (longitud 37) — nunca reconstruidos manualmente a partir de
  `theta0`/`delta_theta`/`phi0`/`delta_phi`.
- **Orden de aplanado de los arrays 1D**: columna-mayor (estilo
  Fortran), con **theta variando más rápido que phi** en la
  representación aplanada de 1D longitud `19*37=703` que devuelven
  `get_gain_tot()` y equivalentes (distinta de la matriz 2D
  `(19, 37)` de `get_gain()` recién descrita). Es decir:
  `indice_plano = phi_idx * n_theta + theta_idx`. Confirmado por tres
  fuentes independientes:
  1. Documentación primaria de NEC2 (tarjeta RP, nec2.org, ver §5):
     *"When both NTH and NPH are greater than one, the angle theta
     (or Z) will be stepped faster than phi."*
  2. Código fuente de NEC2++ (sdist verificado, ver §5): la clase
     `safe_matrix<T>` (`necpp_src/src/safe_array.h`) implementa
     `check(row, col) = col * _rows + row`, y
     `nec_radiation_pattern::get_power_gain_tot(theta_index,
     phi_index)` accede a `_power_gain_tot(theta_index, phi_index)`
     — es decir, `row=theta_index`, `col=phi_index`, así que el
     índice plano real es `phi_index * n_theta + theta_index`.
  3. Verificación empírica reproducible en este entorno (§2.1): con
     un dipolo horizontal a lo largo del eje X, los únicos nulos
     exactos (`-999.99`, valor centinela de NEC2 para ganancia nula)
     aparecen exactamente en `theta=90°, phi=0°/180°/360°` (las
     direcciones a lo largo del propio conductor) solo si se decodifica
     el índice plano como `phi_idx * n_theta + theta_idx`; la hipótesis
     alternativa (theta-mayor) ubica esos mismos nulos en direcciones
     físicamente incorrectas.
  Se reshapeó `get_gain_tot()` con `.reshape((n_theta, n_phi),
  order='F')` y se comparó elemento a elemento contra `get_gain()`:
  coinciden exactamente (`np.allclose` verdadero).
- **Advertencia sobre el propio ejemplo oficial de PyNEC**
  (`example/radiation_pattern.py` en el sdist): usa
  `.reshape((30,30))` (orden C por defecto) porque en ese ejemplo
  `n_theta == n_phi == 30`; al ser cuadrada, la forma no revela el
  error de orden. **No debe tomarse ese ejemplo como confirmación del
  orden de aplanado** — es ambiguo por construcción. La evidencia
  correcta es la documentación primaria más el código fuente más la
  verificación con nulos exactos de una geometría asimétrica
  (`n_theta != n_phi`), como se hizo aquí.
- **Recomendación de diseño**: usar `get_gain()` (matriz 2D ya
  orientada) en vez de `get_gain_tot()` aplanado, para no tener que
  razonar sobre el orden de aplanado en el motor de YAAS. Si en algún
  caso hiciera falta un array plano (por ejemplo, para exportar CSV
  fila por fila), aplanar explícitamente con `order='C'` desde la
  matriz 2D ya orientada, nunca asumir el orden de
  `get_gain_tot()` directamente.

### 1.3. Convenciones de coordenadas (theta/phi)

- `theta` se mide desde el eje +Z (cenit): `theta=0°` es el cenit
  (arriba), `theta=180°` es el nadir (abajo). **Relación con
  elevación**: `elevación = 90° - theta` (la convención de "elevación
  sobre el horizonte" común en ingeniería de antenas es la
  complementaria de theta, no theta mismo).
- `phi` se mide en el plano XY desde el eje +X (verificado: los nulos
  del dipolo horizontal de §2.1 caen exactamente en `phi=0°/180°`,
  las direcciones a lo largo del eje X). **El sentido de recorrido
  (horario o antihorario visto desde +Z) no quedó verificado por esta
  investigación**: el dipolo de control usado en §2.1 es simétrico
  respecto de una rotación de 180° alrededor de su propio eje, así que
  no permite distinguir si `phi` creciente gira hacia `+Y` o hacia
  `-Y`. La documentación primaria de NEC2 remite a una figura
  ("Figure 18") que no se consultó en esta investigación (solo se
  extrajo el texto plano de la página de la tarjeta RP, ver §5), y
  ningún experimento de este documento usó una geometría asimétrica
  capaz de resolver la ambigüedad. **La suposición de "azimut
  matemático estándar" (antihorario desde +X, con 0° != Norte) es una
  convención común, no una conclusión verificada aquí** — queda como
  pregunta abierta (ver §6). En cualquier caso, YAAS no define todavía
  ninguna convención de orientación geográfica (0°=Norte, etc.).
- Unidades: grados en las tarjetas de entrada (`theta0`, `phi0`,
  `delta_theta`, `delta_phi`) y en los arrays de ángulos devueltos;
  ganancia en dB/dBi (ver §1.5); frecuencia en Hz en
  `get_frequency()` (`14.15` MHz se reportó como `14150000.0`).
- **Advertencia primaria explícita** (tarjeta RP, nec2.org): *"When a
  ground plane has been specified, field points should not be
  requested below the ground (theta greater than 90 degrees...)"*.
  Verificado empíricamente que PyNEC **no impide** esto: con tierra
  perfecta y `theta` pedido hasta 180°, todos los puntos con
  `theta > 90°` devuelven exactamente `0.000` dB (no `-999.99`, no
  NaN, no excepción) — un valor sin significado físico que un
  consumidor ingenuo podría confundir con datos válidos. **YAAS deberá
  validar `theta <= 90°` cuando el entorno no sea espacio libre**,
  igual que ya valida geometría contra el plano de tierra en
  `yaas.domain.models`.

### 1.4. Orden de llamadas/tarjetas — tres conceptos distintos, no uno solo

Es importante no fundir en una sola afirmación tres cosas distintas.
Esta investigación solo verificó experimentalmente la primera; la
segunda es una interpretación razonable pero no probada de forma
independiente; la tercera **no se verificó en absoluto** y no debe
asumirse igual a la primera.

1. **Orden de llamadas de la API de PyNEC 2.3.4 (verificado
   experimentalmente aquí)**: sobre el mismo modelo de control (dipolo
   de media onda en espacio libre a 14.15 MHz), se llamó a los
   métodos Python de `nec_context` en distinto orden y se comparó el
   resultado:

   | Orden de llamadas probado | Resultado |
   |---|---|
   | `geo.wire(...)` → `geometry_complete` → `gn_card` → `fr_card` → `ex_card` → `rp_card` → `xq_card(0)` | Ganancias correctas y físicamente consistentes. |
   | Igual, pero **`rp_card()` antes de `ex_card()`** (con `ex_card`/`xq_card` después) | **Todas las ganancias son `NaN`**, sin ninguna excepción. |
   | Igual, pero **`fr_card()` después de `ex_card()`/`rp_card()`**, antes de `xq_card(0)` | Ejecuta sin error, pero produce **valores distintos e incorrectos** respecto del orden anterior (mismo patrón de nulos, pero magnitudes de ganancia diferentes en cada punto) — un resultado silenciosamente equivocado, no detectable sin un valor de referencia. |

   Conclusión, **limitada estrictamente a esta secuencia de llamadas de
   la API de PyNEC 2.3.4** (no a NEC2++ en general ni a un archivo NEC
   de texto): desviarse de `wire → geometry_complete → gn_card →
   fr_card → ex_card → rp_card → xq_card` produce datos inválidos
   (`NaN`) o silenciosamente incorrectos, nunca un error explícito.
2. **Interpretación sobre el orden de tarjetas que interpreta
   NEC2++**: dado que las llamadas de PyNEC alimentan directamente el
   mismo motor de procesamiento secuencial de tarjetas de NEC2++ (cada
   llamada Python corresponde una a una con una tarjeta NEC), es
   razonable interpretar que el resultado anterior refleja cómo
   NEC2++ interpreta un flujo de tarjetas `GW/GE/GN/FR/EX/RP/XQ` en
   ese mismo orden. **Esto es una interpretación, no una verificación
   independiente**: no se construyó ni se ejecutó ningún archivo `.nec`
   de texto crudo contra NEC2++ como programa de línea de comandos en
   esta investigación.
3. **Orden portable recomendado para un archivo NEC destinado a otras
   aplicaciones (por ejemplo, 4nec2)**: **no se verificó en esta
   investigación**, y la evidencia existente en el propio repositorio
   de YAAS sugiere que puede no coincidir con el orden de llamadas de
   PyNEC del punto 1. El exportador de YAAS
   (`src/yaas/exporters/nec.py`) genera el archivo de texto con las
   tarjetas en el orden `CM, CE, GW, GE, GN, EX, FR, EN` — es decir,
   **`EX` antes que `FR`**, exactamente al revés que el orden interno
   de llamadas que usa `PyNecEngine` para impedancia
   (`fr_card` antes que `ex_card`, ver el docstring de
   `_simulate_single_point` en `src/yaas/engines/pynec.py`) — y ese
   archivo exportado ya fue validado externamente con 4nec2
   (`docs/validation/nec-export-4nec2.md`) sin ningún problema
   reportado. Esto demuestra que **el orden de llamadas de la API de
   PyNEC (punto 1) no puede asumirse igual al orden de tarjetas de un
   archivo de texto portable para otras aplicaciones (punto 3)**: son
   preguntas distintas, con evidencia distinta, y no deben
   presentarse como una sola conclusión. Si en el futuro YAAS exporta
   también tarjetas `RP`/`XQ` a un archivo de texto, su posición
   relativa a `EX`/`FR` en ese archivo debería validarse de forma
   independiente contra 4nec2 (o la aplicación de destino), tal como
   ya se hizo para `GE`/`GN`, en vez de copiar el orden de llamadas de
   PyNEC verificado en el punto 1.

`get_radiation_pattern(index)` con un índice sin datos válidos
(ningún `rp_card` ejecutado, o índice fuera de rango, incluido
negativo) devuelve **`None`** de forma limpia, sin excepción — hay que
comprobar `is None` explícitamente antes de usar el resultado.

**`rp_card()` dispara la ejecución por sí solo, sin necesitar
`xq_card()` después, en esta API.** Se comprobó explícitamente: sobre
el modelo de control, se llamó a `rp_card(...)` y luego,
**sin llamar nunca a `xq_card()`**, se llamó directamente a
`get_radiation_pattern(0)`. El resultado fue un objeto de patrón ya
poblado y válido, con exactamente los mismos valores de ganancia que
el caso de control que sí llama a `xq_card(0)` después de `rp_card()`.
Esto es consistente con la documentación primaria de NEC2 (tarjeta
RP, §5): *"The RP card will initiate program execution..."*. No
obstante, todos los demás experimentos de este documento (incluidos
los de §1.6 y §2) llamaron a `xq_card(0)` después de `rp_card()` por
seguir el mismo patrón ya usado por `PyNecEngine` para impedancia;
esa llamada adicional no cambió ningún resultado observado, pero
tampoco se investigó si podría ser necesaria en configuraciones no
probadas aquí (por ejemplo, múltiples tarjetas `RP` en secuencia).

### 1.5. Ganancia: dB, dBi, potencia vs. directiva, componentes

- `D` (columna 19 del XNDA original, parámetro `D` en Python):
  `D=0` ganancia de potencia (`power gain`), `D=1` ganancia directiva
  (`directive gain`). Para una antena sin pérdidas (los conductores de
  ejemplo de YAAS no declaran conductividad finita, i.e. son
  perfectamente conductores por defecto en NEC2), se verificó que
  `D=0` y `D=1` devuelven **exactamente los mismos valores** — es
  decir, sin pérdidas óhmicas explícitas, ganancia de potencia y
  ganancia directiva coinciden numéricamente, como exige la física
  (eficiencia de radiación = 1). No se investigó el caso con pérdidas
  (cargas óhmicas, `ld_card`): YAAS no tiene todavía esa funcionalidad
  (ver `AGENTS.md`, "Explicitly postponed work").
- `X` (`output_format`): `X=0` → `get_gain()`/`get_gain_tot()` quedan
  poblados junto con "eje mayor/eje menor" (no investigado a fondo,
  relevante solo para polarización elíptica); `X=1` → se pueblan
  además `get_gain_horiz()`/`get_gain_vert()` con la descomposición
  horizontal/vertical. Verificado con un dipolo horizontal puro: con
  `X=1`, `get_gain_horiz() == get_gain_tot()` exactamente y
  `get_gain_vert()` es `-999.99` (nulo) en todos los puntos donde el
  campo es puramente horizontal — coherente con la física de un
  dipolo horizontal linealmente polarizado.
- Todos los valores de ganancia observados están expresados
  directamente en **dBi** (decibelios sobre isotrópico) en unidades
  absolutas, no normalizadas: el máximo observado del dipolo en
  espacio libre fue `2.1233 dBi` (ver §2.1, con el valor teórico
  aproximado de manual, `2.15 dBi`, para contraste), sin ningún
  desplazamiento aparente hacia otra escala.
- **Normalización** (`normalization`/N, `gain_norm`/F6): se probó
  `normalization=5` (ganancia total normalizada) con `gain_norm=0`
  (debería normalizar al máximo). El metadato
  `get_rp_normalization()` reportó correctamente `5`, pero
  `get_gain_tot()` **siguió devolviendo los mismos valores absolutos
  sin normalizar** (el máximo seguía en `~2.12 dBi`, no en `0 dB`).
  **Pregunta abierta** (ver §6): no se identificó qué método de acceso expone
  la ganancia ya normalizada según el modo `N` solicitado; podría ser
  un campo de salida de texto (no expuesto vía la API de objetos
  Python) o requerir otro método no explorado
  (`get_norm_rx_pattern()`, no investigado en profundidad).
- **Polarización**: `get_pol_tilt()` (grados), `get_pol_axial_ratio()`
  (relación axial; `0` para polarización lineal pura) y
  `get_pol_sense_index()` (entero) están disponibles. Se verificó con
  el dipolo horizontal que `pol_axial_ratio == 0` en todos los puntos
  (consistente con polarización estrictamente lineal) y que
  `pol_tilt` alterna entre `0°` y `-90°` según la dirección, lo cual
  es plausible pero **no se encontró documentación primaria que defina
  el significado exacto de `pol_sense_index`** (valores observados: 0
  y 3) — pregunta abierta (ver §6). `get_e_theta()`/`get_e_phi()`
  devuelven los componentes complejos del campo eléctrico lejano
  (V/m relativos, no normalizados a una distancia física salvo que se
  indique `radial_distance` != 0), útiles para reconstruir
  polarización con precisión completa si `pol_tilt`/`pol_axial_ratio`
  no bastaran.
- `get_ground()` dispara una advertencia real de SWIG: *"swig/python
  detected a memory leak of type 'nec_ground *', no destructor
  found"*. **No debe llamarse a `get_ground()` desde código de
  producción de YAAS** hasta que se investigue si esto es un leak real
  o un falso positivo del wrapper (fuera del alcance de esta
  investigación); ninguno de los demás métodos de acceso usados aquí generó
  advertencias.

### 1.6. Errores y límites — comprobado, no asumido

Cada caso se ejecutó en un **subproceso Python separado y aislado**
(`python -u script.py` como proceso hijo independiente, nunca dentro
del proceso principal de esta investigación ni del intérprete que
edita este documento), precisamente porque uno de ellos provoca un
`segmentation fault` que mata el intérprete sin dejar rastro de cuáles
casos posteriores se habrían ejecutado. **Los casos de `n_theta`/
`n_phi` negativos en particular solo deben volver a ejecutarse, si
hace falta reproducirlos, en un subproceso aislado y desechable — nunca
en el proceso principal de una sesión de trabajo, y nunca
incorporados como test normal de `pytest`** (un test de `pytest` que
provoca un `segmentation fault` se lleva por delante el proceso de
`pytest` completo y toda la suite que estuviera corriendo en el mismo
proceso, no solo ese test). Si en el futuro se quisiera cubrir este
caso con una prueba automatizada, tendría que ejecutarse de forma
explícita en un subproceso propio (por ejemplo, con
`subprocess.run([...])` y verificando el código de salida), nunca como
una llamada directa dentro del proceso de `pytest`.

| Caso | Resultado observado |
|---|---|
| `get_radiation_pattern(0)` sin haber llamado nunca a `rp_card()` | Devuelve `None` (sin excepción). |
| `get_radiation_pattern(index)` con índice fuera de rango, incluido negativo | Devuelve `None` (sin excepción). |
| `rp_card(..., n_theta=0, ...)` | Se trata como `n_theta=1` (igual que "en blanco" según la documentación primaria). Sin error. |
| `rp_card(..., n_phi=0, ...)` | Análogo: se trata como `n_phi=1`. Sin error. |
| **`rp_card(..., n_theta=-3, ...)`** | **Segmentation fault del proceso Python** (código de salida 139). No es una excepción de Python: mata el intérprete. |
| **`rp_card(..., n_phi=-3, ...)`** | **Segmentation fault**, igual que el caso anterior. |
| `rp_card(..., delta_theta=0.0, ...)` con `n_theta>1` | Sin error; repite el mismo ángulo `n_theta` veces (grilla degenerada pero válida, sin ningún diagnóstico). |
| `rp_card(..., delta_theta=-10.0, ...)` (paso negativo) | Sin error; recorre los ángulos en sentido decreciente correctamente (`90, 80, 70, ...`). |
| `rp_card(..., theta0=float('nan'), ...)` | Sin error, sin excepción; **todos los ángulos y ganancias resultantes son `NaN`**, propagado silenciosamente. |
| `rp_card(calc_mode=99, ...)` (modo desconocido, solo 0-6 documentados) | Sin error; se comporta como si fuera el modo normal (`0`), sin ningún aviso de modo no reconocido. |
| Puntos de campo por debajo del plano de tierra (`theta > 90°` con `GN` activo) | Sin error, sin `NaN`; devuelve **`0.000` dB** exactamente en cada punto — un valor sin significado físico, indistinguible de un dato válido sin verificación adicional. |

**Causa raíz probable del crash** (a partir del código fuente, no
verificado exhaustivamente): `safe_array::check(row, col)` en
`necpp_src/src/safe_array.h` incluye una comprobación de límites
(`row < 0 || row >= _rows`, etc.) que está condicionada a la macro de
compilación `NEC_ERROR_CHECK`. Es plausible que los wheels binarios
publicados de PyNEC 2.3.4 no se compilen con esa macro activa (por
rendimiento), en cuyo caso un tamaño de dimensión negativo se traduce
directamente en una asignación de memoria o un acceso fuera de rango
sin ninguna protección en tiempo de ejecución. Esto es una hipótesis
razonable a partir de la evidencia del código fuente, no una
confirmación definitiva (no se recompiló PyNEC con `NEC_ERROR_CHECK`
para probarlo).

**Recomendación de diseño con prioridad alta** (propuesta, no
implementada — ver §4): YAAS debería validar `n_theta > 0` y
`n_phi > 0` (y razonablemente, `theta`/`phi`/`delta` finitos) en el
dominio, antes de que cualquier valor llegue a `rp_card()`, con la
misma disciplina que ya aplica `RealGroundEnvironment.__post_init__` a
`relative_permittivity`/`conductivity_s_per_m`. La motivación concreta
es la observada arriba: sin esa validación, quien use YAAS quedaría
expuesto a un `segmentation fault` del intérprete en vez de un error
manejable.

### 1.7. Grillas: cortes, 3D, duplicados en 0°/360°

- Un corte de azimut completo pedido como `n_phi=37, delta_phi=10.0`
  produce ángulos `0, 10, ..., 350, 360` — **incluye 0° y 360° como
  dos muestras separadas con el mismo valor angular** (duplicado
  real, no un error de redondeo).
- El mismo corte pedido como `n_phi=36, delta_phi=10.0` produce
  `0, 10, ..., 350` — **sin duplicado**, cubriendo el círculo completo
  con exactamente `360/delta_phi` muestras.
- Conclusión: **YAAS debe decidir explícitamente** si un "corte de
  azimut completo" en su futura API pide `n_phi = 360/delta_phi`
  (sin duplicar la costura en 0°/360°, recomendado para grillas que se
  graficarán, para no promediar ni contar dos veces esa dirección) o
  `n_phi = 360/delta_phi + 1` (incluye el punto de cierre explícito,
  útil si se quiere una polilínea cerrada literal sin envolver el
  índice). Ambos son válidos en PyNEC; ninguno es automático.
- Grillas con un único punto (`n_theta=1` o `n_phi=1`) funcionan sin
  problema (usado deliberadamente en varias pruebas de este documento
  para aislar un corte).
- Una grilla 3D completa (`n_theta` y `n_phi` ambos `>1`) funciona
  igual, con el mismo orden de aplanado columna-mayor documentado en
  §1.2.

## 2. Resultados numéricos

Todos los modelos usan las mismas geometrías/frecuencia que los
proyectos de ejemplo de YAAS (`examples/dipole-20m.yaas`,
`examples/monopole-20m-perfect-ground.yaas`,
`examples/dipole-20m-real-ground.yaas`), a 14.15 MHz, con la misma
disposición de conductor/segmentos/fuente que esos archivos.

### 2.1. Dipolo horizontal en espacio libre

Geometría: conductor a lo largo del eje X, de -5.03 m a 5.03 m,
101 segmentos, radio 0.001 m, alimentado en el segmento 51 (centro),
`GE 0` (sin `GN`).

- **Valor teórico aproximado** (dipolo de media onda ideal, de manual):
  `2.15 dBi`.
- **Resultado observado** del modelo discretizado (101 segmentos,
  grilla angular de 10°; el valor varía muy levemente con la
  resolución angular, siempre en el rango `2.10-2.13 dBi`): ganancia
  máxima **2.1233 dBi** — razonablemente próxima al valor teórico, sin
  que se haya investigado aquí si la diferencia (`~0.03 dB`) proviene
  de la discretización en segmentos, de la resolución angular de la
  grilla, o de ambas.
- El máximo se repite, sin variación medible, a lo largo de **todo**
  el meridiano `phi=90°` (y `phi=270°`) para cualquier `theta` — es
  decir, la superficie de máxima ganancia es el plano perpendicular al
  conductor, como exige la simetría de rotación alrededor del eje del
  dipolo.
- **Nulos exactos** (`-999.99` dBi, valor centinela): únicamente en
  `theta=90°, phi=0°/180°/360°` — exactamente las dos direcciones a lo
  largo del propio conductor (eje X), como exige la teoría.
- Verificado con `output_format=1`: `get_gain_horiz()` coincide
  exactamente con `get_gain_tot()`, y `get_gain_vert()` es `-999.99`
  en todos los puntos — el dipolo horizontal irradia polarización
  puramente horizontal, sin componente vertical, y
  `get_pol_axial_ratio()` es `0` en todos los puntos (polarización
  lineal pura).

### 2.2. Monopolo vertical sobre tierra perfecta

Geometría: conductor vertical de `(0,0,0)` a `(0,0,5.03)`, 38
segmentos, radio 0.001 m, alimentado en el segmento 1 (base), `GE 1`,
`GN 1 0 0 0 0 0 0 0`.

- **Valor teórico aproximado** (monopolo cuarto de onda ideal sobre
  tierra perfecta, de manual): `5.15 dBi`.
- **Resultado observado** del modelo discretizado (38 segmentos,
  grilla angular de 5°): ganancia máxima **5.1334 dBi**, exactamente
  en el horizonte (`theta=90°`) — razonablemente próxima al valor
  teórico, con la misma salvedad de §2.1 sobre el origen exacto de la
  pequeña diferencia (`~0.02 dB`).
- **Simetría azimutal perfecta**: con `theta=90°` fijo, la ganancia es
  idéntica (`5.13340412417013` exacto, sin variación de redondeo) en
  las ocho direcciones de `phi` probadas (0°, 45°, ..., 315°) — como
  exige la simetría de revolución alrededor del eje vertical.
- **Nulo exacto hacia el cenit**: `theta=0°` da `-999.99` dBi.
- Comportamiento del hemisferio inferior: sin restringir `theta` al
  rango `[0°, 90°]`, el hemisferio inferior (`theta > 90°`, "bajo
  tierra") devuelve `0.000` dB exactamente en cada punto — ver la
  advertencia de §1.3: no debe interpretarse como un valor físico
  real.

### 2.3. Dipolo horizontal a 10 m sobre tierra real (Sommerfeld-Norton)

Geometría idéntica a `examples/dipole-20m-real-ground.yaas`:
conductor horizontal de `(-5.03, 0, 10)` a `(5.03, 0, 10)`, 101
segmentos, radio 0.001 m, alimentado en el segmento 51, `GE 1`,
`GN 2 0 0 0 13 0.005 0 0 0 0`.

- La API de patrón de radiación **funciona correctamente** con
  `gn_card(2, ...)`: no se observó ningún error, `NaN` ni
  comportamiento anómalo distinto de espacio libre/tierra perfecta.
- **Comparación contexto único vs. contexto nuevo por frecuencia**
  (dos frecuencias, 14.000 y 14.300 MHz, misma geometría elevada):
  diferencia máxima de ganancia entre ambas estrategias =
  **exactamente `0.0` dB** en ambos índices de frecuencia. Para esta
  geometría elevada (10 m sobre el plano de tierra), reutilizar un
  único contexto NEC2++ con `fr_card` multipunto es indistinguible de
  crear un contexto nuevo por frecuencia — coherente con lo ya
  encontrado para impedancia en geometrías elevadas
  (`docs/research/nec-real-ground.md`).
- **La misma comparación repetida con una geometría que toca el plano
  de tierra**, con los siguientes parámetros exactos:
  - **Geometría**: monopolo vertical, conductor de `(0,0,0)` a
    `(0,0,5.03)` m, 38 segmentos, radio 0.001 m, alimentado en el
    segmento 1 (base).
  - **Entorno**: tierra real Sommerfeld-Norton
    (`gn_card(2, 0, 13.0, 0.005, 0,0,0,0)`), no tierra perfecta.
  - **Frecuencias**: dos, `14.000 MHz` (índice 0) y `14.300 MHz`
    (índice 1), generadas con un único `fr_card(0, 2, 14.0, 0.3)`.
  - **Grilla de patrón**: `n_theta=10, n_phi=1`,
    `theta0=0°, delta_theta=10°` (corte de elevación único).
  - **Comparación realizada**: **contexto único** (un solo
    `nec_context`, `fr_card` con `nfrq=2`, un solo `rp_card`, patrones
    leídos como `get_radiation_pattern(0)` y `get_radiation_pattern(1)`)
    **frente a contexto independiente** (un `nec_context` nuevo,
    creado y configurado desde cero, por cada una de las dos
    frecuencias, con su propio `fr_card(0, 1, freq, 0.0)`).
  - **Resultado en el índice 0 (14.000 MHz)**: coincide exactamente
    entre ambas estrategias (diferencia de ganancia `0.0` dB).
  - **Resultado en el índice 1 (14.300 MHz)**: difiere entre ambas
    estrategias. **Diferencia máxima de ganancia**: `1.2955 × 10⁻²` dB
    (`0.012955` dB) en la grilla de 10 puntos angulares probada.
    **Diferencia de impedancia** en esa misma frecuencia:
    `Z` contexto único `= 241.808 - j446.036` ohm frente a `Z`
    contexto independiente `= 241.178 - j445.104` ohm — una diferencia
    de módulo `≈ 1.13` ohm.
  - **Interpretación**: la misma magnitud y el mismo patrón (afecta
    solo a frecuencias posteriores a la primera, dentro de un contexto
    reutilizado, y solo para geometrías que tocan el plano de tierra)
    ya documentado para impedancia en `docs/research/nec-real-ground.md`.
    No se asumió esa conclusión previa: se reprodujo de forma
    independiente para patrones de radiación, con su propio
    experimento, su propia geometría y sus propios números, listados
    arriba.
- **Conclusión de diseño**: los barridos de patrón de radiación con
  tierra real deben usar la misma estrategia de contexto nuevo por
  frecuencia que ya usa `PyNecEngine._simulate_sweep_per_frequency`
  para impedancia, por el mismo motivo y con una discrepancia de la
  misma naturaleza (aunque de magnitud distinta, propia de la
  ganancia y no de la impedancia).
- **Rendimiento** (grilla de 10°, hemisferio superior, 370 puntos,
  `min` de 3 repeticiones):
  - dipolo elevado (10 m) sobre tierra real: **~56-61 ms** por
    contexto/frecuencia.
  - monopolo (tocando tierra) sobre tierra real: **~34-38 ms** por
    contexto/frecuencia.
  - (comparación) monopolo sobre tierra perfecta, misma grilla:
    **~3.6-3.8 ms**.
  - (comparación) dipolo en espacio libre, grilla completa de 10°
    (19×37 = 703 puntos): **~9.9-10.1 ms**.
  Con una grilla más fina (5°, 37×73 = 2701 puntos): espacio libre
  **~30-32 ms**; tierra real elevada, hemisferio superior (19×73 =
  1387 puntos): **~65-72 ms**. El costo por punto de grilla angular es
  bajo comparado con el costo fijo de establecer el entorno de tierra
  real (consistente con lo ya encontrado para impedancia: el cálculo
  de Sommerfeld-Norton domina el tiempo, no la geometría angular ni la
  creación del contexto). Un barrido de patrón de radiación con
  contexto nuevo por frecuencia sobre tierra real, para un número de
  frecuencias comparable al de los barridos de impedancia ya
  existentes (21-81 puntos), es del mismo orden de magnitud temporal
  que los barridos de impedancia ya aceptados en YAAS (segundos, no
  minutos).

## 3. Interpretación

- La API de patrones de radiación de PyNEC es funcionalmente
  equivalente, en robustez, a la de impedancia: ambas comparten el
  mismo patrón "llamada de solicitud + (opcionalmente) `xq_card` +
  método de acceso indexado", y ambas fallan de la misma manera
  silenciosa (datos incorrectos, no excepciones) si el orden de
  llamadas de la API de PyNEC no se respeta (§1.4, punto 1). Esto
  refuerza que `PyNecEngine` debe seguir tratando ese orden de
  llamadas como una invariante estructural fija, nunca parametrizable
  desde fuera — sin que esto implique nada sobre el orden de tarjetas
  de un archivo NEC de texto para otras aplicaciones (§1.4, punto 3),
  que es una pregunta distinta y no verificada aquí.
- El hallazgo de que la estrategia de "contexto nuevo por frecuencia"
  para tierra real también aplica a patrones de radiación (no solo a
  impedancia) es la conclusión de diseño más importante de esta
  investigación: significa que **no existe un atajo de rendimiento**
  disponible para patrones de radiación con tierra real que no exista
  ya para impedancia con tierra real — ambos requieren la misma
  estrategia conservadora.
- El crash con `n_theta`/`n_phi` negativos es la única falla de
  seguridad real encontrada (todas las demás son datos inválidos
  silenciosos, no crashes). Es más grave que cualquier caso de error
  ya manejado en YAAS (que hoy siempre produce `ValueError` o
  `ProjectFormatError` controlados) porque un `segmentation fault` no
  puede convertirse en un mensaje de error de la CLI: mata el proceso
  completo. La validación de dominio deberá tratar este caso con la
  misma prioridad que ya trata, por ejemplo, la validación de
  `relative_permittivity <= 0`.
- La existencia de `get_gain()` (matriz 2D ya orientada) hace
  innecesario que YAAS reimplemente lógica de aplanado/reordenado: el
  motor puede consumir directamente esa matriz sin más conversión que
  envolverla en una estructura de dominio propia.
- La falta de una forma clara de obtener la ganancia ya normalizada
  (§1.5) sugiere que, para una primera implementación, YAAS debería
  **normalizar por su cuenta** en el dominio (restando el máximo de
  `get_gain()` a toda la matriz, si se quiere ofrecer una vista
  normalizada) en vez de depender de `normalization`/`gain_norm` de
  `rp_card()`, cuyo efecto sobre los métodos de acceso del objeto no quedó
  claro en esta investigación.

## 4. Decisiones recomendadas (sin implementar)

Estas son propuestas de diseño para una fase futura; nada de esto se
implementó en esta tarea.

### 4.1. Modelos de dominio mínimos

- Un valor inmutable para una única muestra angular:
  `frecuencia_mhz`, `theta_deg`, `phi_deg`, `ganancia_dbi` (total;
  posiblemente `ganancia_horizontal_dbi`/`ganancia_vertical_dbi` como
  campos opcionales si se expone la descomposición de polarización
  desde el principio).
- Un resultado de patrón completo: la grilla de `theta`/`phi` (como
  tuplas ordenadas, ya expandidas, nunca como `start`/`delta`/`count`
  sin resolver) más una matriz de ganancia ya orientada
  `(n_theta, n_phi)`, análoga en espíritu a `SweepResult`/`SweepPoint`
  ya existentes para impedancia.
- Validación de dominio equivalente a la ya existente para
  `RealGroundEnvironment`: `n_theta > 0`, `n_phi > 0`, `theta`/`phi`
  finitos, y — cuando el entorno no sea espacio libre — `theta <= 90°`
  en toda la grilla solicitada (rechazar antes de llegar a PyNEC, no
  después).

### 4.2. API del motor (`PyNecEngine`)

- Un método nuevo, análogo a `simulate`/`simulate_sweep`, que reciba
  una solicitud de patrón (frecuencia única) y devuelva el resultado
  de dominio de §4.1, reutilizando `_create_context`/`_add_source` tal
  como existen hoy (sin duplicar la lógica de geometría/tierra/fuente).
- Insertar la llamada a `rp_card` inmediatamente después de
  `_add_source` (que ya llama a `ex_card`), preservando el orden de
  llamadas de la API de PyNEC verificado en §1.4 (punto 1):
  `fr_card → ex_card → rp_card`. Dado que `rp_card()` ya dispara la
  ejecución por sí solo (§1.4), mantener `xq_card(0)` después es
  opcional pero inofensivo (no cambió ningún resultado en las pruebas
  de este documento) y preserva la simetría con el código de
  impedancia ya existente. **Esto se refiere únicamente al orden de
  llamadas Python dentro de un `nec_context`**, no al orden de
  tarjetas de un futuro archivo NEC de texto exportado (ver §1.4,
  punto 3).
- Para barridos de patrón por frecuencia: reutilizar la misma
  bifurcación ya existente en `simulate_sweep`
  (`isinstance(environment, RealGroundEnvironment)` →
  contexto nuevo por frecuencia; en caso contrario, contexto único),
  ahora confirmada también para patrones de radiación en §2.3 — no
  solo heredada de la conclusión de impedancia sin verificar.
- Usar `get_gain()` (matriz 2D) como método de acceso preferido, no
  `get_gain_tot()` aplanado.

### 4.3. Futura salida CSV

- Una fila por combinación `(theta, phi)`, con columnas explícitas
  `theta_deg`, `phi_deg`, `gain_dbi` (y posiblemente
  `gain_horizontal_dbi`/`gain_vertical_dbi`), sin ninguna columna
  agregada de índice plano ambiguo — el orden de aplanado interno de
  PyNEC (§1.2) es un detalle de implementación que no debería
  filtrarse al formato de exportación de YAAS.
- Decidir explícitamente (y documentar en el ADR correspondiente,
  cuando exista) si un corte de azimut completo exportado a CSV
  incluye o no la fila duplicada en `phi=360°` (ver §1.7); no dejarlo
  implícito en el comportamiento por defecto de PyNEC.

### 4.4. Qué debería quedar fuera de la primera implementación

- Ganancia circular (`get_gain_lhcp_*`/`get_gain_rhcp_*`) y relación
  axial más allá de exponer el dato crudo: no hay todavía un caso de
  uso de YAAS con antenas de polarización circular.
- Modos especiales de `rp_card` (`calc_mode` 1-6: onda de superficie,
  acantilado, pantalla de radiales): ninguno tiene todavía un modelo
  de dominio equivalente en YAAS (no hay radiales ni ondas de
  superficie implementadas — ver `AGENTS.md`, "Explicitly postponed
  work").
- Ganancia normalizada vía `rp_card(normalization=...)`: dado que no
  se pudo confirmar cómo recuperarla de forma fiable (§1.5, §6),
  posponer hasta resolver esa pregunta abierta; normalizar en el
  dominio de YAAS en su lugar si hace falta una vista normalizada.
- Campo cercano (`get_near_field_pattern`, tarjetas `NE`/`NH`): fuera
  del alcance de esta investigación por completo.
- Distancia radial real (`radial_distance`/F5 distinto de cero, con
  el factor `exp(-jkR)/R`): los ejemplos de este documento usan
  siempre `radial_distance=0` (patrón de campo lejano relativo, sin
  atenuación por distancia). Un caso de uso que requiera potencia
  absoluta a una distancia dada necesitaría investigación adicional.

## 5. Fuentes

- NEC2, tarjeta `RP` (Radiation Pattern):
  <https://www.nec2.org/part_3/cards/rp.html> — consultada el
  2026-09-29.
- NEC2, tarjeta `XQ` (Execute):
  <https://www.nec2.org/part_3/cards/xq.html> — consultada el
  2026-09-29.
- Código fuente de NEC2++ / PyNEC 2.3.4 (sdist oficial de PyPI,
  descargado nuevamente para esta investigación y verificado
  bit-a-bit contra el hash ya documentado en
  `docs/decisions/0004-project-license.md`):
  `pynec-2.3.4.tar.gz`, SHA-256
  `d448d038d2bcb4265d511b2440a5d5ce26081269a776d45139fb8bf17a475df4`.
  Archivos inspeccionados directamente:
  `necpp_src/src/nec_radiation_pattern.h`,
  `necpp_src/src/safe_array.h`, `example/radiation_pattern.py`,
  `tests/test_radiation_pattern.py`.
- API real instalada de PyNEC 2.3.4 en el entorno de YAAS
  (`.venv`), inspeccionada con `dir()`/`help()` sobre instancias
  reales de `PyNEC.nec_context`/`PyNEC.nec_radiation_pattern` — no
  inferida de memoria ni de documentación de terceros.
- Investigaciones previas de YAAS reutilizadas como contexto (no como
  fuente de patrones de radiación en sí, que no cubrían):
  `docs/research/nec-ground-configuration.md`,
  `docs/research/nec-real-ground.md`.
- No se usaron foros ni blogs como fuente de especificación en
  ningún punto de este documento.

## 6. Preguntas abiertas

Requieren investigación adicional o validación cruzada antes de
diseñar la API definitiva:

1. **Cómo recuperar la ganancia ya normalizada** cuando
   `rp_card(normalization=N, gain_norm=...)` se solicita explícitamente
   (§1.5): `get_gain_tot()`/`get_gain()` devolvieron siempre valores
   absolutos sin normalizar en las pruebas realizadas, pese a que
   `get_rp_normalization()` reportaba correctamente el modo
   solicitado.
2. **Significado exacto de `get_pol_sense_index()`** (se observaron
   los valores enteros `0` y `3`, sin encontrar documentación primaria
   que enumere su significado completo — probablemente sentido de
   rotación de la polarización, pero no confirmado).
3. **Si el "memory leak" reportado por SWIG al llamar a
   `get_ground()`** es un problema real de gestión de memoria del
   wrapper o solo una advertencia inofensiva de introspección — no
   investigado a fondo; se recomienda evitar esa llamada hasta
   aclararlo.
4. **Validación cruzada con 4nec2** (no realizada en esta tarea,
   deliberadamente fuera de alcance de una investigación de solo
   documentación): los tres modelos de control de §2 deberían
   reproducirse en 4nec2 V5.9.3 (misma versión ya usada para validar
   impedancia en `docs/validation/`) antes de cerrar cualquier futura
   fase de implementación, en particular:
   - el valor exacto de ganancia máxima del dipolo en espacio libre
     (`2.1233 dBi` aquí) y del monopolo sobre tierra perfecta
     (`5.1334 dBi` aquí), comparados contra los mismos modelos en
     4nec2;
   - la forma completa del patrón (no solo el máximo) del dipolo sobre
     tierra real a 10 m de altura, para confirmar que la forma general
     del lóbulo (no solo un valor puntual) coincide con 4nec2;
   - si 4nec2 reporta la misma discrepancia de `~0.013` dB /
     `~1.13` ohm entre contexto único y contexto por frecuencia para el
     monopolo de tierra real, o si esa discrepancia es específica de
     NEC2++/PyNEC.
5. **Compilación de PyNEC con `NEC_ERROR_CHECK` activo**: no se probó
   si recompilar PyNEC con esa macro convierte el crash de
   `n_theta`/`n_phi` negativos en una excepción manejable en vez de un
   `segmentation fault`; sería útil confirmarlo para decidir si además
   de validar en el dominio de YAAS, vale la pena reportar esto
   upstream a `python-necpp`.
6. **Sentido de recorrido de `phi`** (horario o antihorario visto
   desde +Z): no verificado (§1.3). Requeriría un modelo de control
   asimétrico respecto del eje Z (por ejemplo, dos conductores en
   ángulo recto, o un elemento parásito desplazado) para poder
   distinguir `+Y` de `-Y`, y preferentemente consultar la Figura 18
   referenciada por la documentación primaria de NEC2 (no consultada
   en esta investigación, solo su texto plano).
