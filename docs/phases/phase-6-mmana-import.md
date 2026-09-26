# Fase 6 — Importación de proyectos MMANA-GAL

## Estado

Completada.

## Objetivo

Importar un archivo de proyecto MMANA-GAL (`.maa`) y convertirlo en un
proyecto `.antsim`, reutilizable desde la CLI y, en el futuro, desde la
interfaz gráfica, sin duplicar en ningún punto la lógica de parsing,
compatibilidad, conversión o escritura.

La fase se dividió en sub-fases explícitas, cada una con su propio
alcance cerrado antes de avanzar a la siguiente: 6A (parser
estructural), 6B.1 (compatibilidad semántica), 6B.2 (estudio de
segmentación NEC), 6B.3 (conversión a `AntennaProject` y workflow de
escritura), y finalmente el comando de CLI bilingüe.

## Investigación del corpus

Se inspeccionaron 26 archivos `.maa`/`.MAA` reales (fuera del
repositorio, nunca importados a él), de antenas variadas: dipolos,
verticales GP, delta loops multibanda, antenas Beverage, un reflector
de esquina, una discone, un quad con trampas LC y antenas J. Confirmó:

- estructura idéntica en los 26 archivos (título, marcador `*`,
  frecuencia, `Wires`, `Source`, `Load`, `Segmentation`,
  `G/H/M/R/AzEl/X`, `Comment` opcional);
- el texto decorativo de cada encabezado de sección varía por idioma
  (11 archivos en ASCII, 15 en Windows-1251 cirílico) y por versión
  (con y sin espacios), por lo que el parser reconoce las secciones
  por posición, nunca por el texto del encabezado;
- `segment_override` fue siempre `-1` en las más de 200 filas de
  `Wires` revisadas, sin una sola excepción.

Detalle completo en `docs/research/mmana-format-characterization.md`.

## Experimentos controlados

Para confirmar el significado de los campos que el corpus original no
alcanzaba a ejercitar por sí solo, se generó un corpus experimental de
20 archivos `.maa` (un modelo base y 19 variantes, cada una cambiando
un solo campo) con una instalación real de MMANA-GAL. Confirmaron,
entre otros: el radio en metros, el orden `wire_ref, phase_degrees,
voltage_volts` de `Source`, la sintaxis `w<N><ancla>[<desplazamiento>]`
de las referencias a conductores, el orden `DM1, DM2, SC, EC` de la
fila global de segmentación, y el significado de `G` (tipo de
entorno) y `H` (altura adicional). También reveló que el segundo campo
de los encabezados de conteo de `Source`/`Load` no es constante y sigue
sin interpretarse.

Detalle completo, con la tabla experimento por experimento, en
`docs/research/mmana-format-characterization.md`.

## Parser estructural (fase 6A)

`src/antsim/importers/mmana.py` lee un archivo `.maa` completo sin
convertirlo a dominio ni invocar PyNEC. Expone `MmanaDocument` (título,
marcador, frecuencia, conductores, fuentes, cargas, segmentación,
entorno y comentario) y sus modelos asociados (`MmanaWire`,
`MmanaSource`, `MmanaLoad`, `MmanaSegmentation`, `MmanaEnvironment`).
Reconoce las secciones por posición dentro del archivo, nunca por el
texto de sus encabezados decorativos, que varían por idioma y versión.

Un archivo estructuralmente inválido (contador que no coincide con la
cantidad real de filas, marcador de la segunda línea distinto de `*`,
cantidad de campos incorrecta en una fila, etc.) se rechaza con
`MmanaFormatError`, con ruta, número de línea y explicación cuando se
conocen.

## Codificaciones

`detect_mmana_encoding` resuelve la codificación de un archivo `.maa`
sin depender de heurísticas estadísticas: UTF-8 (con o sin BOM) se
detecta sin ambigüedad; un archivo que decodifica exclusivamente como
CP1251 o exclusivamente como CP1252 también se resuelve solo; el caso
genuinamente ambiguo (ambas codificaciones decodifican sin error, sin
ningún byte decisivo) exige un `legacy_encoding` explícito y nunca se
adivina en silencio.

Esta política reemplazó un diseño inicial basado en la proporción de
caracteres cirílicos, descartado tras verificar empíricamente las 256
posiciones de ambas tablas de códigos: ambas ocupan el rango
`0xC0`-`0xFF` con su alfabeto completo, así que cualquier letra
acentuada válida en CP1252 (por ejemplo, `é` = `0xE9`) decodifica
igualmente, sin error, como una letra cirílica bajo CP1251 — una
proporción de caracteres "parecidos al cirílico" no es una señal
válida. Detalle completo en
`docs/research/mmana-format-characterization.md`.

## Compatibilidad (fase 6B.1)

`src/antsim/importers/mmana_compatibility.py` interpreta
semánticamente los campos ya parseados (referencias de conductor,
fuente, cargas, segmentación, entorno) y ejecuta
`analyze_mmana_compatibility(document)`, que produce un
`MmanaCompatibilityReport` con dos tipos de hallazgo:

- **errores** (severidad `"error"`): impiden la conversión; si hay al
  menos uno, `report.raise_if_incompatible()` lanza
  `MmanaCompatibilityError` con todos los errores adjuntos, y la
  conversión nunca se intenta;
- **advertencias** (severidad `"warning"`): no impiden la conversión,
  pero se conservan en el informe para que la CLI o una futura GUI las
  muestren.

Un documento se considera compatible solo si, simultáneamente: la
frecuencia es finita y positiva; todo conductor tiene radio y
geometría finitos y de longitud distinta de cero; todo conductor usa
`segment_override=-1`; hay exactamente una fuente, centrada en un
conductor existente y sin desplazamiento, con fase y amplitud finitas
y amplitud distinta de cero; no hay ninguna carga concentrada; el
entorno es espacio libre con impedancia de referencia y altura
adicional finitas; los parámetros globales de segmentación cumplen sus
dominios documentados (`DM1 > 0`, `DM2 > 0`, `1 < SC < 3`, `EC` entero
positivo); y el título no está vacío.

En total, la capa de compatibilidad reconoce 21 códigos de
incompatibilidad distintos (errores y advertencias combinados; ver
`src/antsim/importers/mmana_compatibility.py` para la lista completa
de valores de `MmanaCompatibilityIssue.code`). Los códigos son
identificadores estables, en inglés, que nunca se traducen; la CLI los
usa para mapear cada uno a un mensaje traducible (ver más abajo).

Cada regla de esta capa se documenta explícitamente como una de tres
cosas distintas, para no confundir un hecho verificado con una
elección de producto: **observación** (lo que el corpus o un
experimento demuestra), **documentación/especificación** (un contrato
aportado sin que el corpus disponible lo ejercite, por ejemplo
`segment_override=-2`/`-3`) o **decisión de AntSim** (una restricción
de alcance, por ejemplo que solo `segment_override=-1` se acepte, o
que la presencia de cualquier carga sea un error aunque MMANA-GAL las
admita perfectamente). Ver
`docs/research/mmana-format-characterization.md`, sección
"Observación vs. documentación vs. decisión de AntSim".

## Política de segmentación NEC (fase 6B.2, ADR 0007)

MMANA-GAL segmenta cada conductor con **tapering**: segmentos de
longitud variable, concentrados hacia uno o ambos extremos, controlado
por `segment_override` y los parámetros globales `DM1`/`DM2`/`SC`/`EC`.
El modelo `Wire` de AntSim solo admite una cantidad uniforme y
explícita de segmentos por conductor, así que una conversión exacta de
esa malla no es posible con el modelo actual.

`docs/research/nec-segmentation-convergence.md` documenta un estudio
reproducible (`scripts/analyze_nec_segmentation.py`) que simuló 6
geometrías sintéticas — 4 representativas (cercanas a resonancia) y 2
de estrés (`|gamma| ~ 0.99`) — con densidades uniformes desde
`lambda/10` hasta `lambda/640`, evaluando cada candidato contra
`lambda/640` como ancla práctica. `docs/decisions/0007-use-uniform-nec-segmentation.md`
(ADR 0007) registra la conclusión: **`lambda/160`** es la densidad
uniforme mínima que las 4 geometrías representativas cumplen
simultáneamente (error absoluto de impedancia, error relativo y
`abs(delta gamma)` dentro de los límites fijados de antemano), con un
conductor alimentado forzado a una cantidad impar de segmentos para
garantizar un segmento central exacto.

El ADR también documenta, explícitamente, dos limitaciones que la
conversión hereda:

- **no reproduce el tapering de MMANA-GAL**: es una aproximación
  deliberada y documentada, nunca presentada como equivalente al
  mallado original;
- **no cubre geometrías con `|gamma|` cercano a 1** (impedancia de
  alimentación próxima a un circuito abierto): ninguna densidad
  uniforme evaluada, ni siquiera `lambda/640`, produce resultados
  estables en ese régimen, porque la relación `Z = Z0 (1+gamma)/(1-gamma)`
  tiene una derivada que diverge cerca de `gamma = 1`.

## Conversión a `AntennaProject` (fase 6B.3)

`src/antsim/application/mmana_conversion.py` expone:

- `derive_nec_segments(wire_length_m, frequency_mhz, *, requires_center_segment)`,
  que aplica la fórmula del ADR 0007
  (`segments = max(1, ceil(wire_length_m / (wavelength_m / 160)))`,
  forzando un total impar cuando `requires_center_segment` es
  verdadero);
- `convert_mmana_to_project(document, *, sweep)`, que llama primero a
  `analyze_mmana_compatibility(document).raise_if_incompatible()` — la
  conversión nunca produce un `AntennaProject` parcial a partir de un
  documento incompatible — y luego construye cada `Wire` (con
  `derive_nec_segments`), la fuente de tensión (a partir de fase y
  amplitud), los metadatos del proyecto (título y comentario del
  `.maa`) y el barrido, que se pasa **tal cual** se recibió: el
  formato MMANA-GAL no contiene una definición de barrido propia, así
  que esta función nunca inventa una.

## Workflow de importación atómico (fase 6B.3, continuación)

`src/antsim/application/mmana_import.py` expone dos funciones
reutilizables por la CLI y por una futura GUI:

- `prepare_mmana_import(source, *, sweep, legacy_encoding=None)`: lee
  el archivo, analiza compatibilidad, convierte y devuelve un
  `MmanaImportResult` (proyecto, informe de compatibilidad completo —
  incluidas las advertencias —, ruta de origen y codificación
  detectada). No escribe ningún archivo.
- `write_mmana_import(result, destination, *, overwrite=False)`:
  escribe el proyecto ya preparado como `.antsim`, atómicamente.
  Crea un archivo temporal en el mismo directorio que el destino,
  escribe sobre él con `antsim.projects.save_project` (nunca
  reimplementa la serialización), y solo entonces lo mueve al destino
  con `os.replace`. Ante cualquier excepción, elimina el temporal y
  propaga la excepción original sin modificarla: el destino anterior
  (si existía) queda intacto. Rechaza explícitamente que el destino
  sea el mismo archivo que el origen MMANA-GAL, incluso con
  `overwrite=True`.

## Comando CLI bilingüe

```powershell
antsim import-mmana `
    .\antena.maa `
    .\antena.antsim `
    --sweep-start 13.5 `
    --sweep-stop 15.5 `
    --sweep-points 81 `
    --swr-limit 2.0
```

`src/antsim/cli/main.py` (`run_import_mmana`) solo construye
`SweepSettings` a partir de los argumentos, invoca
`prepare_mmana_import`, imprime el resumen y las advertencias, e
invoca `write_mmana_import`; no contiene lógica de parsing,
compatibilidad, conversión ni serialización propia. Nunca importa
`PyNecEngine`: el comando no simula nada.

Las cuatro opciones de barrido (`--sweep-start`, `--sweep-stop`,
`--sweep-points`, `--swr-limit`) son obligatorias, sin valor por
defecto, por la misma razón que `convert_mmana_to_project` nunca
inventa un barrido: el formato MMANA-GAL no lo contiene.
`--legacy-encoding cp1251|cp1252` se reenvía tal cual a
`prepare_mmana_import`; solo importa cuando el archivo no es UTF-8 y
resulta genuinamente ambiguo. `--force` habilita sobrescribir un
destino existente (por defecto, el comando se niega).

La CLI mantiene, en su propia capa, un diccionario que traduce cada
uno de los 21 códigos de `MmanaCompatibilityIssue` a un mensaje en
inglés (idioma fuente), traducido recién en el momento de imprimir
(nunca al cargar el módulo, para no quedar atado al idioma activo en
el momento de la importación de Python). Los códigos mismos nunca se
traducen. Ni `antsim.importers` ni `antsim.application` importan
`gettext`.

Errores controlados (código de salida 2 en todos los casos, sin
traceback):

| Causa | Mensaje (inglés, fuente) |
|---|---|
| `SweepSettings` inválido | `Invalid sweep settings: {error}` |
| Archivo `.maa` mal formado o codificación ambigua sin resolver | `Invalid MMANA-GAL file: {error}` |
| Documento incompatible | `Incompatible MMANA-GAL model:` + una línea `- [código] descripción` por cada error |
| Origen inexistente o fallo de E/S | `MMANA-GAL import failed: {error}` |
| Destino existente sin `--force` | `Destination already exists: {path}` + `Use --force to overwrite it.` |
| Origen igual al destino | `MMANA-GAL import failed: {error}` |

## Build Windows

`scripts/build_windows.ps1` incluye una prueba de humo dedicada de 9
pasos sobre el ejecutable compilado: genera un archivo `.maa` mínimo,
solo ASCII y compatible; ejecuta `import-mmana` en español con las
cuatro opciones de barrido obligatorias; verifica el código de salida
y la frase de éxito esperada; verifica que el `.antsim` se haya
creado; ejecuta `antsim validate` sobre ese proyecto para confirmar
que es cargable y consistente; repite la importación en inglés,
sobrescribiendo con `--force`; verifica su código de salida y frase de
éxito; y limpia ambos archivos temporales en un bloque `finally`, se
haya producido o no un error en los pasos anteriores.

## Pruebas

- `tests/unit/test_mmana_importer.py` (21 pruebas): parser estructural
  — casos exitosos, archivos inválidos, ambas codificaciones legadas,
  ubicación de errores.
- `tests/unit/test_mmana_compatibility.py` (72 pruebas): cada código de
  incompatibilidad, individualmente y en combinación, incluidos los
  precondicionantes que `convert_mmana_to_project` necesita
  garantizados (finitud de frecuencia, fase, voltaje, altura
  adicional; título no vacío como error estable).
- `tests/unit/test_mmana_conversion.py` (43 pruebas): `derive_nec_segments`
  (incluida la regla de segmento central impar), `convert_mmana_to_project`
  (geometría, fuente, metadatos, barrido pasado sin modificar), y la
  prueba contractual de que todo documento compatible convierte sin
  errores atribuibles a MMANA.
- `tests/unit/test_mmana_import_workflow.py` (16 pruebas):
  `prepare_mmana_import` y `write_mmana_import`, incluidas las
  garantías de atomicidad (sin archivo temporal visible tras éxito o
  fallo, destino anterior intacto ante un fallo simulado de
  `save_project`, rechazo de origen igual a destino).
- `tests/test_cli.py` (18 pruebas del comando `import-mmana`): ayuda en
  español e inglés, importación UTF-8 exitosa con recarga, resúmenes
  bilingües, barrido incompleto o inválido, modelo incompatible,
  archivo mal formado, archivo inexistente, codificación ambigua sin y
  con `--legacy-encoding` (ambos valores), destino existente rechazado
  sin alterar su contenido, `--force`, origen igual a destino,
  advertencias mostradas, y verificación explícita de que el comando
  no instancia `PyNecEngine`.

En total, 170 pruebas cubren específicamente la importación MMANA-GAL,
dentro de una suite completa de 409 pruebas.

## Limitaciones

- No reproduce el tapering de MMANA-GAL; usa una densidad de
  segmentación uniforme (`lambda/160`, ADR 0007).
- Admite únicamente `segment_override=-1` (el único modo observado en
  la práctica); los demás modos, aunque documentados por MMANA-GAL, se
  rechazan.
- Admite únicamente exactamente una fuente, centrada y sin
  desplazamiento; amplitud finita y distinta de cero.
- No admite ninguna carga concentrada (`Load`), aunque MMANA-GAL las
  admite y AntSim ya sabe interpretar sus dos formas (`MmanaResistiveLoad`,
  `MmanaLcqLoad`) a nivel semántico.
- Solo admite entornos de espacio libre (`G=0`); `G=1`/`G=2` (tierra
  perfecta o real) se rechazan, en parte porque el `.maa`, en el
  subconjunto observado, tampoco contiene los parámetros de terreno
  necesarios para modelarla.
- No cubre geometrías con impedancia de alimentación cercana a un
  circuito abierto (`|gamma|` próximo a 1): quedan fuera de la
  garantía experimental del ADR 0007.
- Un documento que no cumple estas restricciones se rechaza siempre
  con un error explícito; nunca se ignora en silencio ni se importa
  parcialmente.

## Decisiones pendientes

- Si conviene aproximar el tapering de MMANA-GAL con una segmentación
  no uniforme (por ejemplo, más densa hacia los extremos) en vez de
  rechazar directamente esa aproximación, y cómo validarla.
- Cómo admitir múltiples fuentes y cargas concentradas, lo que exige
  primero extender el modelo de dominio (`Wire`/`AntennaProject`), no
  solo el importador.
- Cómo, o si, admitir tierra perfecta o real, dado que AntSim en su
  conjunto todavía simula únicamente en espacio libre.
- Si conviene una estrategia de segmentación adaptativa (no uniforme,
  ajustada por región) para las geometrías con `|gamma|` cercano a 1,
  identificada en el ADR 0007 como la vía más prometedora pero no
  investigada todavía.

## Resultado

AntSim puede importar un archivo de proyecto MMANA-GAL compatible y
convertirlo en un proyecto `.antsim` completo — con una densidad de
segmentación NEC documentada y experimentalmente respaldada —, listo
para validarse, simularse, exportarse a NEC o compararse con una
medición real, mediante un único comando de CLI bilingüe que reutiliza
íntegramente la misma capa de aplicación que usará la futura interfaz
gráfica.
