# Caracterización del formato MMANA-GAL (.maa)

Este documento registra cómo se investigó el formato de proyecto de
MMANA-GAL y qué se confirmó, para sustentar el parser estructural
(`src/antsim/importers/mmana.py`, fase 6A) y la capa de compatibilidad
(`src/antsim/importers/mmana_compatibility.py`, fase 6B.1). No se
incluyen los archivos de terceros usados como material de
investigación; solo su análisis y fixtures sintéticos derivados.

## Corpus original de 26 archivos

Se inspeccionaron 26 archivos `.maa`/`.MAA` reales, aportados por el
usuario, de antenas variadas (dipolos, verticales GP, delta loops
multibanda, antenas Beverage, un reflector de esquina, una discone,
un quad con trampas LC, antenas J). Hallazgos estructurales, sin
modificar ningún archivo:

- Fin de línea CRLF uniforme; sin BOM.
- 11 archivos en ASCII puro (origen anglófono); 15 en Windows-1251
  (cirílico, MMANA-GAL localizado en ruso), confirmado decodificando
  con `iconv -f WINDOWS-1251` (los encabezados decorativos resultan
  legibles: "Провода" = Wires, "Источ." = Source, "Нагрузка" = Load,
  "Автосегм" = Segmentation, "Коммент." = Comment).
- Estructura idéntica en los 26 archivos: título, marcador literal
  `*`, frecuencia, `Wires`, `Source`, `Load`, `Segmentation`,
  `G/H/M/R/AzEl/X`, y opcionalmente `Comment` (texto libre sin
  contador, hasta EOF).
- El texto decorativo de cada encabezado de sección varía por idioma
  y, aun dentro del inglés, por versión (con y sin espacios,
  `**Segmentation**` vs. `*** Segmentation ***`, `***   Load   ***`
  con espaciado irregular). Por eso el parser estructural reconoce
  las secciones por posición, nunca por el texto del encabezado.
- El campo final de cada fila de `Wires` fue **siempre `-1`** en los
  26 archivos (más de 200 filas revisadas), sin una sola excepción.
- El conteo que antecede a `Wires`/`Source`/`Load` coincidió siempre
  con la cantidad real de filas siguientes: es un contador
  estructural fiable.
- No se importó ningún archivo real al repositorio.

Detalle completo en el informe de investigación de esa fase (no
versionado como archivo aparte; ver el resumen anterior en el
historial de la conversación con el agente).

## Experimentos controlados

Para confirmar el significado de los campos que la fase 6A dejó
deliberadamente sin interpretar, se generó un corpus experimental de
**20 archivos** `.maa` con MMANA-GAL real
(`C:\dev\mmana-experiments`, fuera del repositorio): un modelo base
(`00-base-dipole.maa`, dipolo de referencia a 14.15 MHz) y 19
variantes controladas, cada una cambiando un solo campo respecto de
la base:

| Experimento | Variable | Resultado observado |
|---|---|---|
| radio 1 mm vs. 2 mm | `Wires`, campo de radio | `0.001` vs. `0.002` |
| fuente en inicio/centro/final | `wire_ref` de `Source` | `w1b` / `w1c` / `w1e` |
| fuente 1 V / 0.5 V, 0°/90°/180° | valores de `Source` | `(fase, voltaje)` en ese orden |
| `DM1` = 400 vs. 800 | 1er campo de `Segmentation` | cambia solo ese campo |
| `DM2` = 40 vs. 80 | 2do campo de `Segmentation` | cambia solo ese campo |
| espacio libre / tierra perfecta / tierra real | 1er campo de `G/H/M/R/AzEl/X` | `0` / `1` / `2` |
| carga R = 50 Ω / 100 Ω | `Load` tipo 1 | `(R, X)` con `X=0.0` |
| carga L = 10 µH | `Load` tipo 0 | `(L, C, Q)` |

Estos experimentos también revelaron que:

- Los encabezados decorativos de esta instalación de MMANA-GAL no
  llevan espacios (`***Source***`, `***Load***`,
  `***G/H/M/R/AzEl/X***`, `###Comment###`), distinto de buena parte
  del corpus original de 26 archivos. Ambas variantes se tratan como
  "canónicas" en la capa de compatibilidad (ver más abajo); cualquier
  otra genera una advertencia, nunca un error.
- El segundo campo de los encabezados de `Source`/`Load`
  (previamente hipotetizado como constante) varía (`0` en los
  experimentos, `1` o `2` en el corpus original): confirma que no es
  un valor fijo, y sigue sin interpretarse.
- Un `Load` puede referenciar un punto con desplazamiento
  (`w1c1`, no solo `w1c`), lo cual valida la sintaxis de
  `MmanaWireReference` para cargas además de fuentes.

Los desplazamientos negativos (`w2c-2`) y los valores de
`segment_override` distintos de `-1` (`-2`, `-3`, positivos) no
aparecen en ninguno de los 26 archivos reales ni en los 20
experimentos: su contrato se tomó de la especificación aportada
directamente para esta fase, no de una observación propia. Se marcan
como tales en la tabla siguiente.

## Campos confirmados

| Campo | Contrato | Procedencia |
|---|---|---|
| Radio del conductor | Metros (`1 mm -> 0.001`) | Experimento |
| `Source`: `wire_ref, phase_degrees, voltage_volts` | Orden confirmado | Experimento |
| `wire_ref` = `w<N><ancla>[<desplazamiento>]` | `b`=inicio, `c`=centro, `e`=final; sufijo entero = desplazamiento en pulsos | Experimento (anclas) + especificación (desplazamiento negativo) |
| `Segmentation` = `DM1, DM2, SC, EC` | Ver "Segmentación de MMANA-GAL" más abajo | Experimento (`DM1`/`DM2`) + ayuda de MMANA-GAL (nombres y significado completo) |
| `segment_override` | Los **5 modos están documentados**: positivo=manual; `0`=automática; `-1`=tapering ambos extremos; `-2`=tapering desde inicio; `-3`=tapering desde final. De los 5, **solo `-1` fue observado** en el corpus real de 26 archivos y en los 20 experimentos; **solo `-1` es aceptado** por el MVP de compatibilidad (los otros 4 son un error igualmente, no por ser menos válidos en MMANA-GAL, sino por no estar evidenciados en la práctica ni ser reproducibles por `Wire.segments`) | Especificación (documentado); observación (solo `-1` visto) |
| `G/H/M/R/AzEl/X`, campo 1 (`G`) | `0`=espacio libre; `1`=tierra perfecta; `2`=tierra real | Experimento |
| `G/H/M/R/AzEl/X`, campo 2 (`H`) | `additional_height_m`: altura adicional sobre el nivel de referencia, en metros | Ayuda de MMANA-GAL |
| `G/H/M/R/AzEl/X`, campo 4 (`R`) | Impedancia de referencia (Ω) | Experimento |
| `Load` tipo 1 | `wire_ref, 1, resistance_ohm, reactance_ohm` | Experimento |
| `Load` tipo 0 | `wire_ref, 0, inductance_uh, capacitance_pf, quality_factor` | Experimento |

## Campos todavía opacos

Estos campos se conservan crudos en `antsim.importers.mmana` y no se
interpretan en `antsim.importers.mmana_compatibility`:

- El marcador constante de la segunda línea (`*`): nunca varió en
  ningún archivo ni experimento; se desconoce su propósito.
- El segundo campo de los encabezados de conteo de `Source`/`Load`
  (llamado `flag` en el parser estructural): valores observados `0`,
  `1`, `2`, sin patrón confirmado.
- Los campos `M` y `X` de `G/H/M/R/AzEl/X`: completamente opacos, sin
  ningún uso ni siquiera indirecto (a diferencia de `Az`/`El`, que sí
  se consultan para una advertencia; ver más abajo).
- Los parámetros detallados de un suelo real (`G=2`): los archivos
  experimentales no contienen conductividad, permitividad ni ningún
  otro parámetro de terreno; ver la limitación dedicada más abajo.

`Az` y `El` (patrón puntual solicitado) ocupan un punto intermedio:
no tienen un nombre físico propio asignado todavía (no forman parte
de esta corrección), pero sí se leen posicionalmente en
`_check_environment` para emitir la advertencia
`environment-azel-not-preserved` cuando son distintos de cero. `G` y
`R` (confirmados desde la fase anterior) y `H` (confirmado en esta
corrección como `additional_height_m`) tienen nombre físico propio en
`MmanaEnvironmentSemantics`.

## Segmentación de MMANA-GAL

La fila global de segmentación del archivo `.maa` contiene, en este
orden:

```text
DM1, DM2, SC, EC
```

Este orden fue confirmado mediante los archivos experimentales y
coincide con la ayuda de MMANA-GAL.

Según la ayuda de MMANA-GAL:

- `DM1` controla el intervalo inicial o más fino del tapering.
- `DM2` controla el intervalo final o más grueso del tapering.
- `SC` es el multiplicador o parámetro de progresión empleado para
  cambiar gradualmente la longitud de los segmentos. La documentación
  indica normalmente `1 < SC < 3`.
- `EC` indica cuántos segmentos del tamaño asociado a `DM1` se colocan
  en el extremo donde comienza el tapering. Normalmente vale `1`,
  aunque puede tomar otros valores.

Los experimentos controlados confirmaron que modificar `DM1` o `DM2`
cambia, respectivamente, el primer o segundo campo de esta fila, sin
alterar los demás (`10-segmentation-dm1-800.maa`,
`12-segmentation-dm2-80.maa`). `SC` fue `2.0` en el 100% de los 26
archivos reales y los 20 experimentos, sin una sola excepción. `EC`
varía (`1` o `2` en el corpus original; `2` en todos los experimentos
salvo los de segmentación `DM1`/`DM2`, que usan `1`); no se diseñó un
experimento dedicado a aislar su efecto.

La ayuda describe las longitudes de los segmentos mediante expresiones
basadas en la longitud de onda, `DM1`, `DM2`, `SC` y `EC`. Sin
embargo, las fórmulas y ejemplos publicados no son completamente
consistentes entre sí respecto de la posición exacta de los
multiplicadores `SC` y `EC`. Por ese motivo, AntSim no intenta
actualmente reproducir el algoritmo de tapering de MMANA-GAL.

El modelo actual `Wire` de AntSim solamente admite una cantidad
uniforme y explícita de segmentos por conductor
(`antsim.domain.models.Wire.segments`). La conversión futura de
`.maa` utilizará una política NEC propia, documentada y validada
mediante convergencia numérica. Esa política no deberá presentarse
como equivalente al mallado de MMANA-GAL.

### Modo de segmentación por conductor

La columna `SEG` de cada conductor (`segment_override` en
`antsim.importers.mmana.MmanaWire`) selecciona el modo de
segmentación:

| Valor | Significado documentado |
|---:|---|
| `> 0` | Segmentación manual regular |
| `0` | Segmentación automática regular |
| `-1` | Tapering en ambos extremos |
| `-2` | Tapering desde el extremo inicial |
| `-3` | Tapering desde el extremo final |

Los 26 archivos del corpus utilizaron `-1`. Los demás valores están
documentados por MMANA-GAL, pero no fueron observados directamente en
ese corpus.

El MVP de importación de AntSim acepta únicamente `-1`. Esta es una
restricción de alcance de AntSim y no una restricción del formato
MMANA-GAL. Incluso ese único caso aceptado siempre genera la
advertencia `segmentation-taper-not-reproducible`, porque
`Wire.segments` (un entero uniforme) no puede reproducir un tapering
real; ver `antsim.importers.mmana_compatibility._check_wires`.

### Referencias

- MMANA-GAL Basic Help, secciones "Segmentation" y
  "How MMANA-GAL Segmentation Process Operates":
  <https://hamsoft.ca/pages/mmana-gal/mmana-gal_basic_help/MMANA-GAL%20basic%20help.htm>

## Observación vs. documentación vs. decisión de AntSim

Este proyecto distingue tres tipos de afirmación sobre el formato,
para no confundir un hecho verificado con una elección de producto:

1. **Observación**: lo que un archivo real o un experimento controlado
   demuestra directamente (por ejemplo, "el radio es metros").
2. **Documentación/especificación**: lo que se aportó como contrato
   confirmado sin que el corpus disponible lo ejercite directamente
   (por ejemplo, `segment_override=-2`/`-3`, o el desplazamiento
   negativo `w2c-2`). Se acepta como válido, pero se señala su origen.
3. **Decisión de AntSim**: una regla que no proviene del formato en sí,
   sino de cuánto se quiere admitir en esta fase. Por ejemplo, que
   `segment_override` distinto de `-1` sea un **error** de
   compatibilidad no es una propiedad de MMANA-GAL (los cinco valores
   son igualmente válidos allí); es una decisión de alcance: `-1` es
   el único valor observado en el corpus real de 26 archivos, así que
   es el único que esta fase certifica como "visto en la práctica".
   Todos los demás valores son, en los hechos, igual de no soportados
   por el modelo `Wire` actual de AntSim (ver la limitación siguiente);
   `-1` no es más "correcto" que los otros, solo más evidenciado.

## Limitación: tierra real

`G=2` ("tierra real") no viene acompañado, en ningún archivo del
corpus ni en los experimentos, de conductividad, permitividad ni
ningún otro parámetro de terreno: el formato `.maa`, en el subconjunto
observado, no contiene esa información en absoluto. AntSim, además,
solo simula en espacio libre hoy. En consecuencia:

- `G=1` y `G=2` se tratan igual que cualquier otro valor no
  confirmado como espacio libre: error `environment-not-free-space`.
- No se intenta aproximar una tierra real con espacio libre ni con
  ningún otro modelo; se rechaza explícitamente.
- Si en el futuro se encuentran archivos `.maa` con parámetros de
  tierra adicionales, este documento deberá actualizarse antes de
  cambiar el comportamiento.

## Tabla de cargas

| Tipo | Campos tras el tipo | Significado | Modelo semántico |
|---|---|---|---|
| 1 | 2 valores | `resistance_ohm`, `reactance_ohm` | `MmanaResistiveLoad` |
| 0 | 3 valores | `inductance_uh`, `capacitance_pf`, `quality_factor` | `MmanaLcqLoad` |

Ambos tipos se interpretan correctamente en
`antsim.importers.mmana_compatibility.interpret_load`, pero **su sola
presencia** es un error de compatibilidad (`loads-present`): AntSim no
tiene todavía ningún modelo de carga concentrada en su dominio. La
interpretación semántica existe para que una futura fase de dominio no
tenga que re-descubrir el contrato de campos, no porque ya se acepten.

## Política de codificación

Ver `antsim.importers.mmana.detect_mmana_encoding` para la
implementación. Resumen: BOM UTF-8 o UTF-8 estricto se detectan sin
ambigüedad; un archivo que solo decodifica como CP1251 o CP1252 (nunca
ambas sin overlap) también se resuelve solo; el caso genuinamente
ambiguo (ambas decodifican, sin bytes decisivos) exige un
`legacy_encoding` explícito y nunca se adivina en silencio. Esta
política se diseñó verificando empíricamente las 256 posiciones de
ambas tablas de códigos, no por inspección visual de unos pocos
bytes.

## Alcance del MVP (fase 6B.1)

Un documento MMANA-GAL se considera **compatible** (`is_compatible`)
solo si, simultáneamente:

- la frecuencia principal es finita y positiva;
- todo conductor tiene radio finito y positivo, geometría finita y de
  longitud distinta de cero;
- todo conductor usa `segment_override=-1` (con la advertencia de
  tapering ya mencionada);
- hay exactamente una fuente, centrada en un conductor existente, sin
  desplazamiento (`wNc`);
- no hay ninguna carga concentrada;
- el entorno es espacio libre (`G=0`) con impedancia de referencia
  finita y positiva;
- los parámetros globales de segmentación cumplen sus dominios básicos
  documentados: `DM1 > 0`, `DM2 > 0`, `1 < SC < 3`, `EC` entero y
  positivo (sin validar relaciones entre ellos, como `DM1` vs. `DM2`,
  que no están respaldadas por documentación ni por una decisión
  explícita del proyecto).

Todo lo demás (fase de fuente distinta de cero, parámetros de patrón
puntual Az/El, encabezados decorativos no canónicos, título o
comentario vacíos) genera advertencias, no bloquea. Esta fase no
convierte ningún documento compatible a `AntennaProject`; solo
diagnostica. La conversión, la CLI y la GUI quedan para fases
posteriores.
