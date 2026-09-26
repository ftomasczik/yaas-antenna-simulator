# Changelog

Todas las fechas usan el formato ISO 8601 (AAAA-MM-DD). Este proyecto
todavía no sigue un esquema de versionado formal más allá de indicar,
en cada entrada, qué cambió y qué limitaciones conocidas quedan.

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

[0.1.0]: docs/releases/0.1.0.md
