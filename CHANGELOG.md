# Changelog

Todas las fechas usan el formato ISO 8601 (AAAA-MM-DD). Este proyecto
todavía no sigue un esquema de versionado formal más allá de indicar,
en cada entrada, qué cambió y qué limitaciones conocidas quedan.

Las versiones 0.1.0, 0.1.1 y 0.2.0 se publicaron bajo AntSim, el
nombre de desarrollo usado antes del cambio a YAAS (Yet Another
Antenna Simulator); ver `docs/decisions/0008-rename-to-yaas.md`.

## [Unreleased]

`main` inició el ciclo de desarrollo 0.4.0.dev0 después de la
release 0.3.0 (integración continua en Windows/Ubuntu 22.04/Ubuntu
24.04, un build experimental y efímero del ejecutable de Linux, y la
documentación asociada). Este ciclo completó la fase 8: patrones de
radiación a una frecuencia, de punta a punta (dominio, motor, esquema
`.yaas` 4, exportación NEC y CSV, y CLI), todavía sin gráficos. Ver
`docs/phases/phase-8-radiation-patterns.md`. También inició la fase 9
con la base de una interfaz gráfica experimental (ADR 0010), que por
ahora abre proyectos `.yaas` (esquemas 1 a 4) y calcula y dibuja su
patrón de radiación en segundo plano.

### Added

- Modelos de dominio para patrones de radiación: `AngularSweep`,
  `RadiationPatternRequest`, `RadiationPatternSample` y
  `RadiationPatternResult` (matriz de ganancia `(n_theta, n_phi)`).
- Cálculo de un patrón a una única frecuencia mediante
  `PyNecEngine.simulate_radiation_pattern` (nuevo método de
  `SimulationEngine`).
- Configuración opcional `simulation.radiation_pattern` en el
  esquema `.yaas` 4 (`RadiationPatternSettings`,
  `AntennaProject.to_radiation_pattern_request()`); ver
  `docs/decisions/0009-add-radiation-pattern-schema-v4.md`.
- Exportación NEC de un patrón con una tarjeta `RP` de texto después
  de `FR` (`radiation_pattern_request_to_nec`,
  `export_radiation_pattern_nec`), sin `XQ`.
- Exportación CSV de un patrón (`radiation_pattern_to_csv`,
  `export_radiation_pattern_csv`): columnas
  `frequency_mhz,theta_deg,phi_deg,gain_db`, una fila por dirección y
  los nulos como campo vacío.
- CLI: `yaas pattern PROYECTO [--csv ARCHIVO]` (resumen de la grilla,
  puntos válidos y nulos, ganancia máxima y su dirección, y
  exportación CSV del mismo resultado sin recalcularlo) y la opción
  `--pattern` de `yaas export-nec`, mutuamente excluyente con
  `--sweep`; en inglés y español.
- Proyecto de ejemplo `examples/dipole-20m-radiation-pattern.yaas`
  (esquema 4, mismo dipolo de `examples/dipole-20m.yaas` con un corte
  vertical de su patrón).
- Pruebas de humo de los ejecutables de Windows y Linux para el
  ejemplo del esquema 4 (`validate`, `pattern`, `pattern --csv` y
  `export-nec --pattern`).
- Extra opcional `gui` (`PySide6-Essentials>=6.11.2,<7`); la
  instalación base y el extra `dev` no instalan Qt.
- Entry point `yaas-gui`, que carga Qt de forma perezosa: sin el extra
  termina con un mensaje que indica cómo instalarlo, sin traceback;
  opciones `--version`, `--help` y `--smoke-test`.
- Ventana mínima experimental (`yaas.gui.window.MainWindow`), sin
  motor, proyectos ni simulaciones.
- Ejecutables separados de la GUI (`scripts/build_gui_windows.ps1`,
  `scripts/build_gui_linux.sh`) y jobs de CI `test-gui-windows` y
  `test-gui-ubuntu-24`, con Qt en modo `offscreen`; nada se publica.
- Avisos de terceros de PySide6-Essentials, shiboken6 y los
  componentes de Qt incorporados (`THIRD_PARTY_NOTICES.md`, sección 4)
  y la política de cumplimiento de una futura release binaria de la
  GUI (`docs/packaging/gui-release-compliance.md`).
- Matplotlib (`matplotlib>=3.11.2,<4`) en el extra `gui`, solo; nunca
  se importa fuera de `yaas.gui`.
- `RadiationPatternPlotAdapter` y `RadiationPatternPlotSummary`
  (`yaas.gui.plots.radiation_pattern`): corte de azimut en un gráfico
  polar (0 grados al Este, sentido antihorario) y corte vertical en un
  gráfico cartesiano `theta` (grados) contra dBi, sobre un
  `RadiationPatternResult` existente que nunca se modifica. Los nulos
  (`None`) se dibujan como huecos y se cuentan; las ganancias por
  debajo del piso del gráfico se dibujan sobre el piso y se cuentan
  como recortadas, sin perderse; un corte enteramente nulo dibuja un
  gráfico vacío sin fallar; el mismo lienzo se reutiliza sin acumular
  elementos.
- Exportación de gráficos con `save_image`: PNG, SVG o PDF según la
  extensión; cualquier otra extensión se rechaza con `ValueError` y no
  se crean directorios.
- `RadiationPatternPlotWidget` (`show_azimuth`, `show_vertical`,
  `clear`, con un estado vacío explícito) y una pestaña "Radiation
  pattern" en `MainWindow`, vacía en producción.
- Opción `--smoke-export IMAGEN` de `yaas-gui` (repetible, requiere
  `--smoke-test`), que dibuja un corte sintético y lo exporta; los
  datos sintéticos solo existen para esta prueba de humo.
- Avisos de terceros de Matplotlib y sus dependencias transitivas
  (contourpy, cycler, fonttools, kiwisolver, pillow, pyparsing,
  python-dateutil, six, packaging y numpy), y de las fuentes y datos
  de Matplotlib incorporados al ejecutable de la GUI.
- Caso de uso `yaas.application.open_project` y `OpenedProject`
  (inmutable: ruta y `AntennaProject`): delega únicamente en
  `load_project`, conserva el `schema_version` original, no migra ni
  guarda, y propaga `ProjectFormatError` y los errores del sistema de
  archivos sin traducirlos. No carga Qt, Matplotlib, numpy ni PyNEC.
- `ProjectController` (`yaas.gui.controllers.project`), view-model de
  la GUI sobre `open_project` (inyectable): conserva el proyecto
  abierto, emite `project_opened` (con un `ProjectViewState`
  inmutable), `project_closed` y `error_occurred(título, mensaje)`;
  captura solo `ProjectFormatError` y `OSError`, y un fallo conserva
  el proyecto anterior. Nunca muestra diálogos, lee JSON, guarda ni
  ejecuta el motor.
- Menú *File* de la ventana principal (*Open…*, *Close project*,
  *Exit*) y un panel con el resumen del proyecto (nombre, ruta,
  versión de esquema, conductores, frecuencia, impedancia de
  referencia, entorno, barrido y patrón, con los ejes `theta`/`phi`
  del patrón cuando existe); sin proyecto muestra "No project loaded".
  Compatible con los cuatro ejemplos (esquemas 1 a 4), que no se
  modifican.
- Argumento opcional `yaas-gui [PROJECT]`: abre el proyecto al
  iniciar; si falla, la ventana queda vacía y un diálogo informa el
  error. Con `--smoke-test`, un proyecto que no puede abrirse hace
  terminar la prueba con código 1.
- Cálculo del patrón de radiación desde la GUI (*Calculate > Radiation
  pattern*) sin bloquear el hilo principal: `SimulationRunner`
  (`QThread` con un worker `QObject`, un trabajo por vez) ejecuta
  `calculate_radiation_pattern` con un `PyNecEngine` creado dentro del
  worker; `prepare_radiation_pattern_request` valida antes en el hilo
  principal. No se duplica ninguna validación, resumen ni regla del
  máximo.
- `RadiationPatternController`, con los estados vacío, listo,
  calculando, cancelando, resultado y error; las acciones
  incompatibles (abrir, cerrar el proyecto, recalcular) se deshabilitan
  mientras calcula.
- Cancelación cooperativa (*Calculate > Cancel calculation*): nunca se
  usa `QThread.terminate()`; una llamada nativa en curso no puede
  interrumpirse y su resultado se descarta al terminar; cancelar un
  recálculo conserva el resultado anterior. Cerrar la ventana durante
  un cálculo lo cancela y espera a que termine, sin dejar hilos (una
  decisión explícita, todavía sin diálogo de confirmación). Ninguna
  ruta (éxito, error, cancelación, cambio de proyecto, cierre, fallo
  al iniciar el hilo o al crear el motor) deja la GUI en "calculando":
  el worker se destruye en su propio hilo y el runner espera a que
  cada hilo termine del todo antes de soltarlo (soltarlo apenas llega
  `finished` provocaba un fallo nativo intermitente, cubierto por una
  prueba de estrés), un hilo que no puede iniciarse se informa como
  error, y un worker que termina sin resultado se informa como fallo.
- Selector de cortes en la pestaña "Radiation pattern": tipo de corte
  (vertical con `phi` fijo, o azimut con `theta` fijo, según lo que
  admita la grilla: solo vertical si hay varios `theta` y un `phi`,
  solo azimut si hay un `theta` y varios `phi`, ambos si hay varios de
  los dos, y vertical de un punto para una sola dirección) y ángulo
  fijo, listado con los ángulos reales del resultado. Cambiar de corte
  redibuja el último resultado y nunca vuelve a ejecutar PyNEC; cada
  modo conserva su ángulo; los controles se deshabilitan sin
  resultado, durante el cálculo y con una sola opción; el estado
  indica el corte mostrado. Un resultado nuevo vuelve, de forma
  determinista, al primer corte; cancelar un recálculo conserva
  resultado, corte y gráfico; abrir o cerrar un proyecto y un error de
  cálculo (también durante un recálculo, como antes) los limpian.
  `CutSelection` es un modelo inmutable sin Qt, y el controlador
  decide la selección: la ventana solo la dibuja.
- Opción `--smoke-calculate` de `yaas-gui` (requiere `--smoke-test` y
  `PROJECT`): calcula de verdad el patrón y falla si no se dibuja.

### Changed

- Los ejecutables de la GUI (`scripts/build_gui_windows.ps1`,
  `scripts/build_gui_linux.sh`) ahora incorporan Matplotlib y numpy
  (con los backends SVG y PDF declarados como imports ocultos), siguen
  excluyendo PyNEC, `PySide6.QtNetwork` y pyqtgraph, verifican la
  exportación PNG/SVG/PDF del ejecutable congelado, fallan si el
  análisis de PyInstaller recoge bibliotecas de una instalación ajena
  (XAMPP) e informan el tamaño. En Windows, `yaas-gui.exe` pasó de
  34,1 MB a 63,4 MB; el `yaas.exe` de la CLI no cambia (19,6 MB, sin Qt
  ni Matplotlib). Los jobs de CI de la GUI ya instalaban `.[dev,gui]`
  y no cambian.
- Los builds de la GUI también abren los cuatro proyectos de ejemplo
  (esquemas 1 a 4) con `--smoke-test PROYECTO`, antes y después de
  congelar, y comprueban que un proyecto inexistente o dañado haga
  fallar la prueba de humo; el resto de las comprobaciones no cambia.
  En Windows, `yaas-gui.exe` mide 63,5 MB.
- Los ejecutables de la GUI ahora incorporan PyNEC (antes se excluía):
  los builds declaran `yaas.engines.pynec` como import oculto, fallan
  si el análisis de PyInstaller no lo recoge, y calculan el patrón del
  ejemplo de esquema 4 con `--smoke-calculate`, antes y después de
  congelar (con exportación PNG/SVG/PDF del corte dibujado), además de
  comprobar que un proyecto sin patrón haga fallar esa prueba. En
  Windows, `yaas-gui.exe` mide 63,8 MB. Como `yaas.exe`, ahora incluye
  PyNEC/NEC2++ y Eigen, con las mismas obligaciones de una eventual
  distribución binaria.
- El lector de proyectos acepta los esquemas 1, 2, 3 y 4.
- El escritor de proyectos ahora siempre genera esquema versión 4.
- Los proyectos de los esquemas 1, 2 y 3 siguen cargando sin cambios;
  al guardarse nuevamente quedan migrados al esquema 4, sin patrón de
  radiación. Una clave `radiation_pattern` en un archivo de los
  esquemas 1, 2 o 3 ahora se rechaza en vez de ignorarse.

### Fixed

- La dirección de la ganancia máxima que informa `yaas pattern` es
  estable entre plataformas: ganancias a no más de 1e-9 dB se
  consideran empatadas y gana la primera muestra en orden theta
  externo / phi interno. En Ubuntu 24.04, `theta=0` y `theta=180` del
  dipolo en espacio libre diferían en ~3.6e-15 dB de ruido de punto
  flotante y se informaba `theta=180`. Los valores calculados no
  cambian.

### Validation/Safety

- Los conteos angulares (enteros positivos) y los rangos de `theta`
  y `phi` se validan en el dominio antes de llegar a PyNEC, donde un
  conteo negativo provoca un fallo nativo del proceso.
- Con cualquier plano de tierra, `theta` queda limitado a 90 grados:
  valores mayores dieron en PyNEC resultados no reproducibles.
- El valor centinela `-999.99` de NEC se representa como `None`
  (nulo explícito), nunca como una ganancia física; una ganancia
  `NaN`/infinita devuelta por PyNEC se trata como error.
- Convención angular, sentido de `phi` y valores numéricos validados
  externamente con 4nec2 V5.9.3
  (`docs/validation/radiation-patterns-4nec2.md`).
- Las salidas NEC puntuales y de barrido y los CSV existentes no
  cambian; 1081 pruebas automatizadas y CI en verde en Windows,
  Ubuntu 22.04 y Ubuntu 24.04, incluido el build efímero del
  ejecutable de Linux.

### Known limitations

- Un patrón por proyecto, a una única frecuencia, sobre una grilla
  angular regular y solo con ganancia total.
- La interfaz gráfica es solo un esqueleto experimental: abre
  proyectos y calcula su patrón, pero no calcula impedancia ni
  barridos, no edita, no guarda ni crea proyectos, no tiene lista de
  recientes ni arrastrar y soltar, y dibuja un corte por vez (sin
  tooltips, animación, 3D ni temas; la selección del corte no se
  guarda). La ventana puede
  pausarse durante una llamada nativa de NEC2++ (PyNEC retiene el
  GIL), y cerrar la ventana durante un cálculo espera a que esa llamada
  termine. Sus textos están solo en inglés.
- Sin gráficos, patrones multifrecuencia,
  polarización ni componentes `E_theta`/`E_phi`.

## [0.3.0] - 2026-09-27

Fase 7B: tierra real homogénea mediante el método Sommerfeld-Norton,
de punta a punta (dominio, esquema `.yaas` versión 3, motor
PyNEC/NEC2++ con una estrategia de barrido dedicada, exportación NEC y
validación externa). Esta versión, todavía no publicada
externamente al cierre de la fase 7B, se completó y se prepara para
publicarse ya bajo la identidad YAAS: fue desarrollada como "AntSim
0.3.0" y renombrada a YAAS antes de su primera publicación pública
(ver `docs/decisions/0008-rename-to-yaas.md`); no hubo ninguna versión
publicada externamente como "AntSim 0.3.0". Esta versión también
formaliza la licencia definitiva del proyecto (GPL-3.0-only), sus
avisos de terceros y la política de distribución binaria, previo a
la primera publicación pública del repositorio.

### Added

- `RealGroundEnvironment` y `RealGroundModel.SOMMERFELD_NORTON` en el
  dominio, agregados al alias `Environment`.
- Simulación puntual de tierra real con Sommerfeld-Norton
  (`geometry_complete(1)` + `gn_card(2, 0, relative_permittivity,
  conductivity_s_per_m, 0, 0, 0, 0)`).
- Barridos de tierra real con un contexto NEC2++ independiente por
  frecuencia (`PyNecEngine._simulate_sweep_per_frequency`).
- Esquema `.yaas` versión 3, con serialización de `real_ground`
  (`model`, `relative_permittivity`, `conductivity_s_per_m`).
- Exportación NEC con la tarjeta `GN` completa de tierra real (10
  campos: 4 enteros I1-I4 más 6 flotantes F1-F6).
- Proyecto de ejemplo `examples/dipole-20m-real-ground.yaas`
  (dipolo sobre tierra real).
- Validación cruzada externa con 4nec2 V5.9.3
  (`docs/validation/real-ground-dipole-4nec2.md`).
- Pruebas de humo del ejecutable de Windows para los proyectos de
  ejemplo de los esquemas 1, 2 y 3.
- Cambio de identidad completo de AntSim a YAAS (marca, distribución
  `yet-another-antenna-simulator`, módulo `yaas`, CLI `yaas`, ejecutable `yaas.exe`,
  dominio gettext `yaas`, variable `YAAS_LANGUAGE`, extensión
  `.yaas`), realizado antes de la primera publicación externa, sin
  alias ni compatibilidad con los nombres anteriores
  (`docs/decisions/0008-rename-to-yaas.md`).
- `LICENSE` con el texto canónico completo de GPL-3.0-only.
- `THIRD_PARTY_NOTICES.md`, con el inventario de dependencias de
  ejecución, herramientas de build/desarrollo y componentes
  transitivos incorporados al generar el ejecutable PyInstaller.
- Metadata de licencia PEP 621/PEP 639 en `pyproject.toml`
  (`license = "GPL-3.0-only"`, `license-files = ["LICENSE"]`),
  validada construyendo un wheel temporal fuera del repositorio.
- `docs/packaging/windows-release-compliance.md`, con la política de
  assets requerida para una futura release binaria de Windows.
- `.gitattributes`, con normalización de fin de línea LF por defecto
  y CRLF explícito para scripts de PowerShell/batch.

### Changed

- El escritor de proyectos ahora siempre genera esquema versión 3.
- El lector conserva compatibilidad con los esquemas 1, 2 y 3.
- Los proyectos de los esquemas 1 y 2 siguen cargando sin cambios; al
  guardarse nuevamente quedan migrados al esquema 3, sin intervención
  manual.
- Los comportamientos existentes de espacio libre y tierra
  perfectamente conductora se mantienen sin cambios (`GE 0` sin `GN`
  para espacio libre; `GE 1`/`GN 1 0 0 0 0 0 0 0` para tierra
  perfecta).

### Validation/Safety

- `relative_permittivity` debe ser finita y estrictamente positiva;
  `conductivity_s_per_m` debe ser finita y mayor o igual a cero
  (`0.0` se admite explícitamente, como dieléctrico sin pérdidas);
  `model` debe ser una instancia real de `RealGroundModel`, sin
  conversión silenciosa desde un string o un entero.
- La validación existente de conductores contra el plano z=0 (fase
  7A) se aplica automáticamente a tierra real, sin duplicar lógica.
- 634 pruebas automatizadas (628 de la fase 7B más 6 agregadas para
  verificar el cambio de identidad a YAAS: rechazo explícito de la
  extensión `.antsim`, y carga de los tres ejemplos `.yaas` con sus
  esquemas 1/2/3) y una ejecución completa del build de Windows
  (`scripts/build_windows.ps1`), incluidos los smoke tests de los tres
  esquemas sobre el ejecutable PyInstaller real (`dist\yaas.exe`).

### Known limitations

- El método rápido de tierra real por coeficiente de reflexión
  (Fresnel) todavía no está soportado; solo Sommerfeld-Norton.
- Los modelos MMANA-GAL con cualquier tipo de tierra (perfecta o
  real) continúan rechazándose en la importación.
- No hay radiales, pantallas de tierra ni conductores enterrados,
  para ningún tipo de tierra.
- Los barridos de tierra real no ofrecen progreso ni cancelación: un
  barrido de 81 puntos puede tardar varios segundos.

## [0.2.0] - 2026-09-27

Fase 7A: modelo de entorno de simulación, con soporte inicial de
tierra perfectamente conductora además del espacio libre ya
existente, de punta a punta (dominio, esquema `.antsim`, motor
PyNEC/NEC2++, exportación NEC y validación externa).

### Added

- `FreeSpaceEnvironment` y `PerfectGroundEnvironment` en el dominio,
  propagados a través de `SimulationRequest`, `SweepRequest` y
  `AntennaProject`.
- Simulación con PyNEC/NEC2++ sobre tierra perfectamente conductora
  (`geometry_complete(1)` + `gn_card(1, ...)`).
- Esquema `.antsim` versión 2, con `simulation.environment`
  obligatorio (`free_space` o `perfect_ground`).
- Proyecto de ejemplo `examples/monopole-20m-perfect-ground.antsim`
  (monopolo cuarto de onda sobre tierra perfecta).
- Validación cruzada con teoría de imágenes y con 4nec2 V5.9.3
  (`docs/validation/monopole-perfect-ground-4nec2.md`).
- Pruebas de humo del ejecutable de Windows para los proyectos de
  ejemplo de los esquemas 1 y 2.

### Changed

- El escritor de proyectos siempre genera esquema versión 2.
- Los proyectos del esquema 1 siguen cargando y se interpretan como
  espacio libre; al guardarse nuevamente quedan migrados al esquema
  2, sin intervención manual.
- La exportación NEC usa `GE 1`/`GN 1 0 0 0 0 0 0 0` para tierra
  perfecta, siempre después de la última tarjeta `GW` y antes de
  `EX`/`FR`.

### Validation/Safety

- Un conductor completamente bajo tierra, que cruza el plano z=0, o
  que queda contenido por completo en ese plano, se rechaza en el
  dominio antes de llegar a PyNEC, con un mensaje claro que identifica
  el conductor.
- El espacio libre conserva exactamente `GE 0` sin ninguna tarjeta
  `GN`, igual que antes de esta versión.
- 522 pruebas automatizadas y una ejecución completa del build de
  Windows (`scripts/build_windows.ps1`), incluidos los smoke tests de
  ambos esquemas sobre el ejecutable PyInstaller real.

### Known limitations

- Tierra real (con pérdidas, Sommerfeld o Fresnel) todavía no está
  soportada.
- Los modelos MMANA-GAL con cualquier tipo de tierra (perfecta o
  real) continúan rechazándose en la importación.
- No hay radiales, pantallas de tierra ni conductores enterrados; no
  se calculan patrones de radiación ni ganancia.

## [0.1.1] - 2026-09-26

Correcciones sobre hallazgos de pruebas manuales posteriores a 0.1.0.
No hay cambios de funcionalidad ni de resultados electromagnéticos:
`PyNecEngine` no se modificó.

### Fixed

- Mensaje de compatibilidad MMANA-GAL para modelos con tierra: ya no
  sugiere que los efectos de tierra "se ignoran" cuando en realidad la
  importación se rechaza (el código de incompatibilidad no cambió:
  `environment-not-free-space`).
- Las advertencias repetidas de importación MMANA-GAL (por ejemplo,
  `segmentation-taper-not-reproducible` en un modelo con varios
  conductores) ahora se agrupan en una sola línea con la cantidad de
  apariciones, en vez de repetirse una vez por conductor.

### Added

- Diagnóstico, en el dominio (`SweepResult`), de si la resonancia
  aproximada o la ROE mínima detectadas caen en un extremo del
  barrido en vez de ser un resultado interior confiable.
- Detección de ancho de banda con ROE truncado
  (`SwrBandwidth.truncated_below`/`truncated_above`): la CLI ya no
  presenta un intervalo parcial, cortado por el límite del barrido,
  como si fuera el ancho de banda completo.
- Comentario informativo `CM Reference impedance: ... ohm` en las
  exportaciones NEC de frecuencia única y de barrido, aclarando que
  NEC2++/4nec2 pueden requerir configurar manualmente esa referencia
  para mostrar la ROE.
- `docs/validation/mmana-hentenna-nec2.md`: validación cruzada, con un
  modelo real de 7 conductores (Japanese Hentenna Loop 6m), entre
  MMANA-GAL, AntSim/PyNEC y 4nec2.

### Known limitations

Se mantienen las mismas limitaciones conocidas que en 0.1.0 (ver esa
entrada); esta versión no las modifica.

## [0.1.0] - 2026-09-26

Primer hito funcional de AntSim: un simulador de antenas utilizable de
punta a punta desde la línea de comandos, sobre PyNEC/NEC2++, con
importación y comparación de datos externos.

### Added

- Dominio eléctrico y modelos de simulación (conductores rectos,
  fuente de tensión, cálculo de impedancia y ROE).
- Motor de simulación PyNEC/NEC2++, aislado detrás de un adaptador
  propio.
- Simulación de frecuencia única y barridos lineales de frecuencia.
- Detección aproximada de resonancia, ROE mínima y ancho de banda
  muestreado.
- Proyectos versionados `.antsim` (lectura, escritura y validación de
  esquema).
- CLI bilingüe (español/inglés) con selección explícita de idioma.
- Exportación de barridos a CSV y de proyectos al formato NEC
  (frecuencia única y barrido), validada externamente con 4nec2 5.9.3.
- Lectura de mediciones Touchstone de un puerto (`.s1p`), incluidos
  NanoVNA, en formatos `RI`, `MA` y `DB`.
- Comparación de un barrido simulado con una medición Touchstone sobre
  una impedancia de referencia común, con exportación a CSV.
- Importación de proyectos MMANA-GAL (`.maa`): parser estructural,
  detección de codificación, análisis de compatibilidad, conversión a
  `.antsim` y comando de CLI `import-mmana`.
- Ejecutable independiente para Windows construido con PyInstaller.
- Suite automatizada de pruebas (409 pruebas) y pruebas de humo sobre
  el ejecutable compilado.

### Changed

- ADR 0001-0003: elección de Python, NEC2++ y la separación explícita
  entre dominio y motor de simulación.
- ADR 0005 y ADR 0006: contrato de comparación simulación/medición
  (impedancia de referencia común obligatoria, interpolación lineal
  sin extrapolación, candidatos finitos de resonancia).
- ADR 0007: densidad de segmentación NEC uniforme (`lambda/160`) para
  la importación MMANA-GAL, elegida mediante un estudio reproducible
  de convergencia.

### Known limitations

- La simulación actual solo modela espacio libre; no hay
  configuración de suelo.
- Se admite una única fuente de tensión por proyecto.
- No hay todavía ningún modelo de carga concentrada.
- No se generan gráficos ni existe interfaz gráfica.
- Solo se importan archivos Touchstone de un puerto (`.s1p`); no se
  admite `.s2p` ni otros formatos multipuerto.
- La importación MMANA-GAL es estricta: solo convierte el subconjunto
  compatible documentado (una fuente centrada, sin cargas, espacio
  libre, `segment_override=-1`); un archivo fuera de ese subconjunto
  se rechaza con un error, nunca se importa parcialmente.
- La segmentación de MMANA-GAL (tapering) se convierte a la política
  NEC uniforme `lambda/160` de AntSim; esta política no reproduce el
  mallado original de MMANA-GAL.
- Pueden existir diferencias esperables entre los resultados de
  MININEC (usado internamente por MMANA-GAL) y NEC2++ (usado por
  AntSim), incluso para geometrías equivalentes.

[0.3.0]: docs/releases/0.3.0.md
[0.2.0]: docs/releases/0.2.0.md
[0.1.1]: docs/releases/0.1.1.md
[0.1.0]: docs/releases/0.1.0.md
