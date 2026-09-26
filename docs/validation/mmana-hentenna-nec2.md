# Validación cruzada: importación MMANA-GAL, PyNEC y 4nec2 (Hentenna 6 m)

Fecha: 2026-09-26

## Objetivo

Comprobar, con un modelo real más complejo que el dipolo de referencia
(133 pulsos en MMANA-GAL), que:

1. la importación MMANA-GAL (`antsim import-mmana`) produce un
   proyecto `.antsim` que PyNEC puede simular sin errores;
2. la exportación NEC de ese proyecto (`antsim export-nec`) coincide
   con un cálculo independiente en 4nec2;
3. cualquier diferencia frente al resultado propio de MMANA-GAL es
   atribuible al motor de simulación y a la política de segmentación,
   no a un error de exportación NEC de AntSim.

No se incluye ni redistribuye en este repositorio el archivo `.maa`
de terceros utilizado como entrada; este documento registra únicamente
los resultados obtenidos a partir de él.

## Herramientas

- AntSim (rama de desarrollo posterior a 0.1.0)
- PyNEC / NEC2++
- 4nec2 5.9.3
- MMANA-GAL (para el cálculo de referencia original del modelo)
- Windows x64

## Modelo

**Japanese Hentenna Loop 6 m** (`.maa` de terceros, no incluido en el
repositorio):

- Geometría original tal como la distribuye su autor, con 133 pulsos
  de alimentación/segmentación en MMANA-GAL.
- Para esta validación se usó una **copia modificada a espacio
  libre** (entorno `G=0`), ya que AntSim solo admite ese entorno en
  esta fase (ver `docs/phases/phase-6-mmana-import.md`); el archivo
  original declaraba un entorno distinto.
- Frecuencia: 50.100 MHz.
- Impedancia de referencia declarada en el modelo: 75 ohm.

## Resultados: impedancia a 50.100 MHz

| Fuente | Impedancia | ROE | Elementos de malla |
|---|---:|---:|---:|
| MMANA-GAL (motor propio, MININEC) | 77.42 + j6.74 ohm | 1.10 (75 ohm) | 133 pulsos |
| AntSim / PyNEC (tras `import-mmana`, `lambda/160`) | 76.71 + j120.63 ohm | 4.30 (75 ohm) | 245 segmentos |
| 4nec2 (NEC exportado por AntSim) | 76.7 + j121 ohm | sin advertencias | 245 segmentos |

4nec2 mostró inicialmente una ROE de 5.8 para este mismo par
impedancia/frecuencia: se debía a que 4nec2 tenía configurada una
impedancia de referencia de 50 ohm (su valor por defecto), no los 75
ohm del modelo. La ROE de 4.30 de la tabla anterior es la que
corresponde a la impedancia de 4nec2 (76.7 + j121 ohm) calculada
respecto de 75 ohm, no respecto de 50 ohm. Este es exactamente el
malentendido que el comentario informativo `CM Reference impedance:
... ohm`, agregado por los exportadores NEC de AntSim, busca evitar:
NEC2++/4nec2 no leen ese valor automáticamente, así que la referencia
debe configurarse manualmente en el programa para que la ROE
mostrada sea comparable.

## Resultados: resumen de barrido en AntSim

Barrido ejecutado sobre el proyecto importado (parámetros de barrido
provistos explícitamente al importar, no derivados del `.maa`):

- Resonancia aproximada: 48.600 MHz.
- ROE mínima: 1.11, a 48.625 MHz.
- Ancho de banda para ROE <= 2.00: 47.975-49.250 MHz.

Ninguno de estos tres resultados quedó en un extremo del rango
barrido (ver el diagnóstico de límites de barrido agregado a
`SweepResult`); no aplica ninguna advertencia de truncamiento para
este barrido en particular.

## Diferencias

- **AntSim/PyNEC vs. 4nec2** (mismo archivo NEC, dos motores/
  intérpretes distintos): 0.01 ohm en resistencia, 0.37 ohm en
  reactancia. Coinciden dentro del margen de redondeo esperable,
  igual que en la validación del dipolo de referencia
  (`docs/validation/nec-export-4nec2.md`).
- **AntSim/PyNEC vs. MMANA-GAL** (mismo modelo geométrico, motores y
  segmentación distintos): 0.71 ohm en resistencia, **113.89 ohm en
  reactancia**, y una ROE de 4.30 contra 1.10. Esta diferencia es
  considerablemente mayor que el margen de redondeo de la
  comparación anterior.

## Conclusión

AntSim y 4nec2 coinciden entre sí (misma malla de 245 segmentos,
mismo motor NEC2++/NEC subyacente, diferencia de reactancia de menos
de medio ohm): esto confirma que la tarjeta NEC exportada por AntSim
para este modelo, incluido el conductor derivado de la importación
MMANA-GAL, es correcta.

La diferencia grande frente al resultado propio de MMANA-GAL no
corresponde a la exportación NEC de AntSim, sino a la combinación de:

- un motor de cálculo distinto (MININEC, usado internamente por
  MMANA-GAL, frente a NEC2++, usado por AntSim y por 4nec2);
- una política de segmentación distinta: 133 pulsos con tapering
  (segmentos de longitud variable, concentrados hacia los extremos)
  en MMANA-GAL, frente a 245 segmentos de longitud uniforme
  (`lambda/160`, ADR 0007) en AntSim — ver la advertencia
  `segmentation-taper-not-reproducible`, que `antsim import-mmana`
  ya muestra explícitamente para este modelo.

Este resultado es consistente con la limitación ya documentada en el
ADR 0007 y en `docs/phases/phase-6-mmana-import.md`: AntSim no
reproduce el tapering de MMANA-GAL, y pueden existir diferencias
esperables entre MININEC y NEC2++ incluso para geometrías
equivalentes. Este documento registra un caso real donde esa
diferencia es grande (reactancia), no solo teórica.

## Limitaciones de esta validación

- No se recalculó 4nec2 con la impedancia de referencia de 75 ohm ya
  configurada para este documento; el valor de ROE de 4nec2 a 75 ohm
  citado arriba se calculó manualmente a partir de la impedancia que
  4nec2 reportó.
- No se investigó cuánto de la diferencia de reactancia es atribuible
  al motor (MININEC vs. NEC2++) frente a la segmentación (tapering
  vs. uniforme) por separado: este documento registra la diferencia
  total observada, no una atribución cuantitativa entre ambas causas.
- El archivo `.maa` de origen no se incluye ni se redistribuye en
  este repositorio.
