# ADR 0007: Densidad uniforme de segmentación NEC preliminar

- Estado: Aceptada
- Fecha: 2026-09-26

## Contexto

AntSim necesita, eventualmente, una función que derive automáticamente
la cantidad de segmentos NEC por conductor (`Wire.segments`) a partir
de la frecuencia y la geometría, en lugar de exigir que el usuario la
calcule a mano. Antes de implementar esa función (`derive_nec_segments`
o equivalente) hacía falta evidencia experimental de qué densidad de
segmentación uniforme (segmentos de longitud constante por conductor)
produce resultados suficientemente estables frente a un motor NEC2++
real.

`docs/research/nec-segmentation-convergence.md` documenta un estudio
reproducible (`scripts/analyze_nec_segmentation.py`) que simuló 6
geometrías sintéticas — 4 clasificadas como **representativas**
(cercanas a resonancia: dipolo recto, Yagi de 3 elementos, loop
cuadrado de onda completa, V invertida cercana a resonancia) y 2 como
**de estrés** (dos variantes de V invertida deliberadamente alejadas
de resonancia, `|gamma| ≈ 0.99`) — con densidades uniformes
`lambda/10, 20, 40, 80, 160, 320, 640`, y evaluó cada candidato contra
`lambda/640` como ancla práctica (no como verdad absoluta).

Este ADR registra la densidad uniforme mínima que ese estudio
respalda para las geometrías representativas, con las limitaciones
explícitas que el propio estudio identificó.

## Alternativas consideradas

- **`lambda/80`**: la más económica en segmentos. **Rechazada**: de
  las 4 geometrías representativas, 2 no cumplieron el criterio
  (Yagi: error relativo 1.15 %; V cercana a resonancia: 1.10 %),
  ambas por encima del límite de 1 %.
- **`lambda/160`**: **seleccionada** (ver más abajo).
- **`lambda/320`**: también cumple el criterio en las 4 geometrías
  representativas, con márgenes más holgados que `lambda/160`
  (por ejemplo, `abs(delta gamma)` de la V cercana a resonancia:
  0.001554 en `lambda/320` contra 0.004784 en `lambda/160`, con un
  límite de 0.005). Queda documentada como alternativa más
  conservadora, a un costo computacional mayor (segmentos totales
  aproximadamente el doble que en `lambda/160`).
- **Segmentación adaptativa** (no uniforme, ajustada por región de
  cada conductor en vez de por wavelength/divisor constante): no se
  implementó ni se descartó. El propio estudio muestra que ninguna
  densidad uniforme, ni siquiera `lambda/640`, resuelve las
  geometrías de estrés (`|gamma| ≈ 0.99`); una estrategia adaptativa
  queda como la vía más prometedora para esos casos, pendiente de
  investigación futura.

## Evidencia experimental

Ver `docs/research/nec-segmentation-convergence.md` para el detalle
completo. Resumen de la tabla de decisión (candidato `lambda/160`
contra `lambda/640`, geometrías representativas únicamente):

| Geometría | abs(ΔZ) | Error relativo | abs(Δgamma) | ¿Cumple? |
|---|---:|---:|---:|---|
| Dipolo de referencia | 0.2584 Ω | 0.347 % | 0.001750 | Sí |
| Yagi simple (3 elementos) | 0.2761 Ω | 0.615 % | 0.003243 | Sí |
| Loop cuadrado (onda completa) | 0.4749 Ω | 0.260 % | 0.001015 | Sí |
| V invertida cercana a resonancia | 0.4957 Ω | 0.679 % | **0.004784** | Sí |

Las 4 geometrías representativas cumplen simultáneamente los tres
criterios (`abs(ΔZ) <= 1 Ω`, error relativo `<= 1 %`,
`abs(delta gamma) <= 0.005`), con resultados finitos y repetibles
(verificado explícitamente: dos corridas independientes del script
completo, y una verificación de repetibilidad dedicada en
`lambda/160`, además de `lambda/80`, `lambda/320` y `lambda/640`, para
las 6 geometrías). El margen más ajustado es el de la V cercana a
resonancia en `abs(delta gamma)` (0.004784 contra un límite de 0.005);
es el único margen estrecho de toda la evaluación.

Las dos geometrías de estrés se calcularon en los mismos niveles y
**no cumplen** el criterio (error relativo 10.7 % y 15.8 % en
`lambda/160`), pero **no participaron en esta decisión**: se
reportan solo como diagnóstico y limitación (ver más abajo).

## Densidad seleccionada

**`lambda/160`**, para conductores rectos aislados o conectados sin
ambigüedad de alimentación, con impedancia de alimentación
razonablemente cercana a una carga de 50 Ω (`|gamma|` moderado, no
cercano a 1), a frecuencias del orden de las estudiadas (HF, ~14 MHz).

## Fórmula preliminar

```text
wavelength_m = speed_of_light / frequency_hz
target_segment_length = wavelength_m / divisor   # divisor = 160
segments = ceil(wire_length / target_segment_length)
```

Con `divisor = 160` fijo, sujeto a las siguientes reglas
adicionales, ya validadas experimentalmente en el estudio:

- **Mínimo de un segmento** por conductor
  (`segments = max(1, segments)`), aunque en la práctica nunca se
  necesitó forzar este piso con esta densidad en ninguna de las 6
  geometrías estudiadas (la fórmula ya da como mínimo varios
  segmentos incluso para el conductor más corto, la sección central
  de la V representativa, 0.30 m).
- **El conductor alimentado debe tener una cantidad impar de
  segmentos**: si el resultado de la fórmula es par, se suma 1, para
  garantizar un segmento central exacto para la fuente. Esta regla
  se aplicó consistentemente en todo el estudio y no mostró ningún
  salto discontinuo alrededor de los puntos donde se activó.

Esta fórmula es **preliminar**: describe la densidad y las reglas de
ajuste ya validadas por el estudio, pero `derive_nec_segments` (o el
nombre que finalmente tenga la función de producción) todavía no
existe en el código. Implementarla, con sus propias pruebas y
validación de invariantes de dominio, queda para una fase posterior.

## Advertencia: no reproduce el tapering de MMANA-GAL

Esta densidad es uniforme (segmentos de igual longitud dentro de cada
conductor). MMANA-GAL, documentado en
`docs/research/mmana-format-characterization.md`, describe una
política de **tapering**: segmentos de longitud variable,
concentrados hacia uno o ambos extremos de un conductor, controlada
por `segment_override` y los parámetros globales `DM1`/`DM2`/`SC`/`EC`.
Ninguna densidad uniforme — `lambda/160` incluida — reproduce esa
distribución no uniforme. Esta decisión **no** valida, ni pretende
informar por sí sola, ninguna política de conversión de un archivo
`.maa` de MMANA-GAL a un `AntennaProject` de AntSim: esa conversión
necesitará su propia decisión explícita sobre cómo tratar el tapering
(aproximarlo, ignorarlo con una advertencia, o rechazarlo).

## Casos con `|gamma|` próximo a 1: fuera de esta garantía

Esta decisión **no cubre** geometrías cuya impedancia de alimentación
esté cerca de una reflexión casi total (`|gamma| >= ~0.98`, según el
umbral de exención usado en el propio estudio). Las dos geometrías de
estrés de este estudio son un ejemplo directo: ninguna densidad
uniforme evaluada, ni siquiera `lambda/640`, las acerca a un error
absoluto o relativo razonable. La causa identificada no es la
densidad de segmentación en sí, sino que, cerca de `|gamma| = 1`, la
relación `Z = Z0 (1+gamma)/(1-gamma)` tiene una derivada que diverge:
pequeños cambios — bien comportados — en `gamma` se amplifican en
cambios grandes en `Z` (ver el diagnóstico dedicado en el informe de
investigación). Cualquier código de producción que use `lambda/160`
como densidad por defecto debe advertir explícitamente, o rechazar,
geometrías cuya impedancia resultante esté en ese régimen, en vez de
presentar una `Z` numéricamente inestable como si fuera confiable.

## Posibilidad futura de convergencia adaptativa

Para las geometrías de estrés (y, en general, para cualquier
geometría con `|gamma|` cercano a 1), una densidad uniforme fija —
sea cual sea — no es la estrategia correcta: el estudio ya muestra que
aumentar la densidad de `lambda/80` a `lambda/640` no resuelve el
problema. Una estrategia adaptativa (por ejemplo, refinar
localmente hasta que un indicador de convergencia local se
estabilice, en vez de fijar `divisor` de antemano) queda identificada
como la vía más prometedora para esos casos, pero no se investigó en
este estudio ni se implementa en este ADR.

## Consecuencias de rendimiento

El tiempo de simulación crece más rápido que linealmente con la
cantidad total de segmentos (compatible con un costo cercano a cúbico
en la resolución de la matriz densa de NEC2++, ver el informe de
investigación). En las geometrías de este estudio, `lambda/160`
implica segmentos totales de: 77 (dipolo), 230 (Yagi), 161 (loop), 77
(V representativa) — todos resueltos en menos de 25 ms por
simulación en el hardware usado para el estudio. `lambda/320`, la
alternativa más conservadora, aproximadamente duplica esos totales y
el tiempo correspondiente (compatible con el crecimiento cúbico ya
observado). Geometrías con muchos más conductores o conductores mucho
más largos que las de este estudio deberán revalidar este costo antes
de asumir que sigue siendo despreciable.

## Resultado

`lambda/160` queda registrada como la densidad uniforme mínima
respaldada experimentalmente por este estudio para geometrías
representativas (cercanas a resonancia, sin ambigüedad de
alimentación). No se implementa todavía ninguna función de
producción que la aplique; esa implementación, sus pruebas, y la
decisión de cómo tratar en código los casos de `|gamma|` alto quedan
para una fase posterior.
