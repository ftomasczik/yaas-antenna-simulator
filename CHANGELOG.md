# Changelog

Todas las fechas usan el formato ISO 8601 (AAAA-MM-DD). Este proyecto
todavía no sigue un esquema de versionado formal más allá de indicar,
en cada entrada, qué cambió y qué limitaciones conocidas quedan.

Las versiones 0.1.0, 0.1.1 y 0.2.0 se publicaron bajo AntSim, el
nombre de desarrollo usado antes del cambio a YAAS (Yet Another
Antenna Simulator); ver `docs/decisions/0008-rename-to-yaas.md`.

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
