# Convergencia de segmentación uniforme NEC2++ (fase 6B.2, revisión 4)

Estudio de investigación reproducible. `derive_nec_segments` (o
equivalente) **sigue sin agregarse** al código de AntSim en esta
fase — esta revisión concluye qué densidad usaría esa función algún
día, no la implementa. Esta revisión sí escribe un ADR
(`docs/decisions/0007-use-uniform-nec-segmentation.md`), porque llegó
a una conclusión positiva (`lambda/160` aceptada); no se toca ningún
código de producción.

Script: `scripts/analyze_nec_segmentation.py`. Reutiliza únicamente
`antsim.domain` y `antsim.engines.pynec.PyNecEngine`; no accede a
PyNEC directamente ni modifica el motor. No se agregaron densidades
ni geometrías nuevas en esta revisión (sigue siendo `10, 20, 40, 80,
160, 320, 640`, y las mismas 6 geometrías): se reutilizaron los
resultados ya calculados de `lambda/160` y `lambda/320` contra
`lambda/640`, generalizando el mecanismo de comparación del script
(antes fijo en `lambda/80`) para aceptar cualquier candidato. Los CSV
completos se escriben en un directorio temporal fuera del
repositorio.

## Qué cambió en esta revisión

1. **Clasificación explícita de cada geometría** en `representativa`
   o `estrés` (campo `GeometrySpec.classification`). Las dos V
   invertidas ya existentes (corta y larga) se marcaron `estrés` — se
   conservan sin cambios para diagnóstico, pero **ya no pueden decidir
   por sí solas ninguna política general**.
2. **Nueva geometría representativa**: una tercera V invertida,
   diseñada para acercarse a resonancia en vez de alejarse de ella
   (ver más abajo).
3. **Criterio práctico de MVP**, aplicado únicamente a las
   geometrías `representativa`: compara directamente `lambda/80`
   contra `lambda/640`, usado explícitamente como "ancla práctica"
   para evaluar ese candidato — no como verdad general. El análisis
   de convergencia por diferencias sucesivas de la revisión anterior
   (sin ningún nivel de referencia) se mantiene sin cambios, en
   paralelo.
4. **Conclusión explícita** sobre `lambda/80`: ver la última sección.

## Geometrías representativas vs. de estrés

| Geometría | Clasificación | \|gamma\| en λ/640 |
|---|---|---:|
| Dipolo de referencia | representativa | 0.2932 |
| Yagi simple (3 elementos) | representativa | 0.2410 |
| Loop cuadrado (onda completa) | representativa | 0.7295 |
| V invertida cercana a resonancia (**nueva**) | representativa | 0.7098 |
| V invertida, sección central corta (1.0 m) | **estrés** | 0.9872 |
| V invertida, sección central larga (5.0 m) | **estrés** | 0.9886 |

Las dos de estrés se conservan íntegramente (mismas dimensiones que
la revisión anterior); solo cambió su rótulo y el hecho de que ya no
participan en la evaluación del criterio de MVP salvo como referencia
separada.

## Geometría nueva: V invertida cercana a resonancia

Se construyó reutilizando la misma fábrica de las otras V
(`_build_inverted_v`, ahora generalizada para aceptar altura de
vértice, altura y alcance de las patas como parámetros explícitos —
antes estaban fijos dentro de la función). Dimensiones, fijadas
**antes** de correr el estudio y no ajustadas después:

- **Sección central alimentada**: 0.30 m total (0.15 m a cada lado
  del centro). Pequeña pero físicamente justificable: del orden del
  tramo recto/aislador central de una V invertida real, muy por
  debajo de los 1.0 m / 5.0 m de las variantes de estrés.
- **Vértice**: 6.0 m de altura. **Puntas de pata**: 2.0 m de altura
  (caída de 4.0 m) — dimensiones de mástil modestas, típicas de una
  instalación de aficionado en HF.
- **Longitud de cada pata**: 4.88 m, elegida junto con la sección
  central (0.15 m) para que cada "brazo" completo (centro + pata) sea
  **5.03 m** — la misma longitud de medio dipolo que ya se sabe
  cercana a resonancia en el dipolo de referencia de este estudio, a
  14.15 MHz. Reutilizar esa longitud conocida es la justificación de
  diseño; la posición horizontal resultante de la punta de pata
  (2.9454 m) es una consecuencia geométrica de imponer esa longitud
  de pata junto con la caída de altura de 4.0 m, no un valor elegido
  libremente.
- **Radio**: 0.001 m, igual que el resto del estudio.
- **Extremos**: la sección central y cada pata comparten coordenadas
  exactas en sus uniones (mismas tuplas), igual que en las demás
  geometrías conectadas.
- **Por qué es una antena razonable**: reproduce la forma y escala de
  una V invertida de HF real (vértice a media altura de mástil,
  patas hacia abajo y hacia afuera), con una longitud eléctrica total
  por brazo igual a la de un dipolo ya conocido como cercano a
  resonancia a esta frecuencia.

**Resultado real, sin ajustar nada después de verlo**: `|gamma|` en
`lambda/640` es **0.7098** — claramente menor que 0.9, como pedía el
enunciado. La reactancia es negativa y relativamente grande
(-67.9 Ω en `lambda/640`, contra -31.1 Ω del dipolo recto), es decir,
el doblez de la V corre el punto de resonancia respecto de un dipolo
recto de igual longitud de brazo: la antena queda funcionalmente
capacitiva a esta frecuencia exacta, no perfectamente resonante. Esto
se reporta tal cual, sin modificar la geometría para "arreglarlo":
sigue siendo una geometría representativa válida (ROE ~5.9, muy lejos
del régimen de reflexión casi total de las V de estrés, ROE ~156-175).

## Tabla consolidada (las 6 geometrías, λ/80 · λ/160 · λ/320 · λ/640)

Columnas: `R`/`X` en ohm, `|Z|` en ohm, `gamma` complejo. El error
absoluto/relativo y `abs(delta gamma)` son **siempre λ/80 vs.
λ/640** (el candidato de MVP contra el ancla práctica), no contra un
nivel intermedio.

### Dipolo de referencia — representativa

| Divisor | R | X | \|Z\| | gamma |
|---:|---:|---:|---:|---|
| 80 | 67.4801 | -31.5373 | 74.4860 | 0.2060 -0.2131j |
| 160 | 67.4421 | -31.3196 | 74.3596 | 0.2051 -0.2120j |
| 320 | 67.4243 | -31.1701 | 74.2807 | 0.2045 -0.2112j |
| 640 | 67.4163 | -31.0625 | 74.2282 | 0.2040 -0.2106j |

λ/80 vs λ/640: error absoluto = **0.4791 Ω**, error relativo =
**0.643 %**, abs(Δgamma) = **0.003243**.

### Yagi simple, elemento excitado — representativa

| Divisor | R | X | \|Z\| | gamma |
|---:|---:|---:|---:|---|
| 80 | 40.1160 | -20.4047 | 45.0072 | -0.0556 -0.2390j |
| 160 | 40.0895 | -20.1652 | 44.8754 | -0.0570 -0.2366j |
| 320 | 40.0751 | -20.0040 | 44.7903 | -0.0580 -0.2350j |
| 640 | 40.0666 | -19.8900 | 44.7319 | -0.0587 -0.2338j |

λ/80 vs λ/640: error absoluto = **0.5171 Ω**, error relativo =
**1.149 %**, abs(Δgamma) = **0.006067**.

### Loop cuadrado, lado alimentado — representativa

| Divisor | R | X | \|Z\| | gamma |
|---:|---:|---:|---:|---|
| 80 | 110.1998 | -146.1643 | 183.0519 | 0.6594 -0.3108j |
| 160 | 109.7210 | -146.1475 | 182.7506 | 0.6592 -0.3118j |
| 320 | 109.4305 | -146.1271 | 182.5600 | 0.6591 -0.3124j |
| 640 | 109.2478 | -146.1057 | 182.4335 | 0.6591 -0.3128j |

λ/80 vs λ/640: error absoluto = **0.9538 Ω**, error relativo =
**0.521 %**, abs(Δgamma) = **0.002035**.

### V invertida cercana a resonancia — representativa (nueva)

| Divisor | R | X | \|Z\| | gamma |
|---:|---:|---:|---:|---|
| 80 | 25.6872 | -68.6674 | 73.3147 | 0.2753 -0.6575j |
| 160 | 25.6858 | -68.3588 | 73.0252 | 0.2723 -0.6572j |
| 320 | 25.6307 | -68.0279 | 72.6961 | 0.2691 -0.6574j |
| 640 | 25.6160 | -67.8680 | 72.5413 | ver \|gamma\| arriba (0.7098) |

λ/80 vs λ/640: error absoluto = **0.8026 Ω**, error relativo =
**1.095 %**, abs(Δgamma) = **0.007730**.

### [ESTRÉS] V invertida, sección central corta (1.0 m)

| Divisor | R | X | \|Z\| | gamma |
|---:|---:|---:|---:|---|
| 80 | 1633.0268 | +3171.1266 | 3566.9063 | 0.9869 +0.0246j |
| 160 | 1773.4491 | +3265.5954 | 3716.0780 | 0.9870 +0.0233j |
| 320 | 1880.8885 | +3332.8133 | 3826.9291 | 0.9870 +0.0225j |
| 640 | 1951.8533 | +3374.7862 | 3898.5784 | 0.9870 +0.0219j |

λ/80 vs λ/640: error absoluto = **378.32 Ω**, error relativo =
**10.61 %**, abs(Δgamma) = **0.002686**, `|gamma(λ/640)|` = 0.9872.

### [ESTRÉS] V invertida, sección central larga (5.0 m)

| Divisor | R | X | \|Z\| | gamma |
|---:|---:|---:|---:|---|
| 80 | 4229.8042 | -4364.5206 | 6077.8519 | 0.9886 -0.0117j |
| 160 | 3601.8274 | -4297.6851 | 5607.4288 | 0.9885 -0.0135j |
| 320 | 3297.3718 | -4231.7634 | 5364.7444 | 0.9885 -0.0145j |
| 640 | 3122.2095 | -4183.4376 | 5220.0903 | 0.9885 -0.0152j |

λ/80 vs λ/640: error absoluto = **1122.30 Ω**, error relativo =
**18.47 %**, abs(Δgamma) = **0.003497**, `|gamma(λ/640)|` = 0.9886.

## Criterio práctico de MVP (solo geometrías representativas)

Fijado antes de ver los resultados de esta revisión:

- `|delta Z| <= 1 Ω` respecto de λ/640 (excepto en estrés con
  `|gamma| >= 0.98`, ver más abajo);
- error relativo de Z `<= 1 %`;
- `abs(delta gamma) <= 0.005`;
- resultados finitos y repetibles.

| Geometría | \|ΔZ\| | Error rel. | abs(Δgamma) | ¿Cumple? |
|---|---:|---:|---:|---|
| Dipolo de referencia | 0.479 Ω | 0.64 % | 0.00324 | **Sí** |
| Yagi simple | 0.517 Ω | 1.15 % | 0.00607 | No (falla relativo y gamma) |
| Loop cuadrado | 0.954 Ω | 0.52 % | 0.00204 | **Sí** (margen escaso en Ω: 0.954<1) |
| V cercana a resonancia | 0.803 Ω | 1.10 % | 0.00773 | No (falla relativo y gamma) |

**No se ajustó ningún límite después de ver esta tabla.**

Repetibilidad: verificada explícitamente en `lambda/80` (el
candidato), además de `lambda/320` y `lambda/640`, para las 6
geometrías — las 18 combinaciones dieron resultados idénticos entre
dos corridas. Finitud: 0 excepciones y 0 resultados no finitos en las
42 combinaciones geometría×divisor (6 geometrías × 7 divisores) de
esta revisión.

### Casos de estrés: por qué no aplican el límite absoluto

| Geometría | \|ΔZ\| | Error rel. | abs(Δgamma) | \|gamma(λ/640)\| |
|---|---:|---:|---:|---:|
| V corta | 378.32 Ω | 10.6 % | 0.00269 | 0.9872 |
| V larga | 1122.30 Ω | 18.5 % | 0.00350 | 0.9886 |

Ambas tienen `|gamma| >= 0.98`: por diseño, no se les exige el
límite absoluto de 1 Ω (quedarían reprobadas por una razón que no
tiene que ver con la calidad de la simulación). La explicación: cerca
de una reflexión casi total, `Z = Z0 (1+gamma)/(1-gamma)` tiene una
derivada respecto de gamma que diverge cuando `gamma -> 1` — un
cambio pequeño y bien comportado en gamma (`abs(Δgamma)` de ambas
está, de hecho, por debajo de 0.005, igual que las representativas
que sí cumplen) se amplifica en un cambio enorme de Z en ohms. Aun
así, **ninguna de las dos cumple el criterio de error relativo**
(10.6 % y 18.5 %, ambos >> 1 %): la exención del límite absoluto no
alcanza para que sean aceptables, y de hecho no deberían serlo — estos
modelos **requieren diagnóstico dedicado o refinamiento adaptativo**
(no uniforme) y **no garantizan precisión de impedancia absoluta**
con ninguna densidad uniforme estudiada aquí, sin importar cuán densa.

## Análisis de convergencia por diferencias sucesivas (sin cambios de metodología)

Se mantiene exactamente el marco de la revisión anterior (pares
`40→80, 80→160, 160→320, 320→640`; convergencia solo si los dos
últimos son estables; ningún nivel tratado como verdad). Con la
geometría nueva incorporada:

| Geometría | Convergencia (160→320 y 320→640 estables) |
|---|---|
| Dipolo de referencia | No converge (falla por gamma, margen mínimo: 0.00102 vs. umbral 0.001) |
| Yagi simple | No converge |
| Loop cuadrado | **Converge** |
| V cercana a resonancia | No converge |
| V corta (estrés) | No converge (falla por Z, no por gamma) |
| V larga (estrés) | No converge |

Esto es un criterio **más estricto** que el práctico de MVP de
arriba (umbrales de 0.5 Ω / 0.001 en gamma, aplicados a los dos
últimos refinamientos en vez de λ/80 vs λ/640) — por diseño, ambos
análisis coexisten y no se espera que den la misma respuesta. El
detalle completo (7 divisores, tiempos, forzado de segmentos impares)
del dipolo, Yagi, loop y ambas V de estrés no cambió respecto de la
revisión anterior; se omite repetirlo aquí para no duplicar contenido
y se remite al historial de esta misma investigación y a los CSV
(`cases.csv`, `successive_differences.csv`) de cualquier corrida
nueva del script.

## Diagnóstico de la V invertida de estrés (sin cambios de fondo)

Se mantiene el hallazgo de la revisión anterior: la variante de
sección larga (hasta 153 segmentos en la parte alimentada) converge
**peor**, no mejor, que la corta (máximo 31 segmentos) — refutando
que la falta de segmentos en la sección central fuera la causa de la
inestabilidad. La causa probable sigue siendo la proximidad a
`|gamma| = 1`, ahora reforzada por el contraste con la V
representativa (`|gamma|` = 0.71, sin ningún comportamiento
patológico) construida con la misma fábrica de geometría y el mismo
rango de segmentación.

## Diferencia entre segmentación tapering de MMANA y segmentación uniforme de AntSim

Sin cambios: este estudio sigue usando exclusivamente segmentación
uniforme (`Wire.segments`). Ninguna densidad estudiada reproduce el
tapering de MMANA-GAL; esta revisión tampoco valida ninguna política
de conversión MMANA→AntSim.

## λ/80 fue rechazada (revisión anterior); esta revisión evalúa λ/160 y λ/320

La revisión anterior concluyó que `lambda/80` **RECHAZADA** como
candidato de MVP: de las 4 geometrías representativas, 2 cumplían
(dipolo, loop) y 2 no (Yagi, V cercana a resonancia). Esta revisión no
repite esa evaluación (no se agregaron divisores ni geometrías
nuevas); en cambio, evalúa los dos siguientes candidatos más
económicos con el **mismo criterio, exactamente los mismos límites**:
`lambda/160` y `lambda/320`, cada uno contra el mismo ancla práctica
`lambda/640`. Igual que antes, las dos V de estrés se calculan y
reportan, pero **no participan en la decisión**.

## Tabla compacta: λ/160 y λ/320 (solo geometrías representativas)

Cada celda numérica muestra `valor en λ/160 / valor en λ/320`.

| Geometría | λ/160 cumple | λ/320 cumple | abs(ΔZ) [Ω] | error relativo | abs(Δgamma) |
|---|---|---|---|---|---|
| Dipolo de referencia | Sí | Sí | 0.2584 / 0.1080 | 0.347 % / 0.145 % | 0.001750 / 0.000732 |
| Yagi simple (3 elementos) | Sí | Sí | 0.2761 / 0.1143 | 0.615 % / 0.255 % | 0.003243 / 0.001343 |
| Loop cuadrado (onda completa) | Sí | Sí | 0.4749 / 0.1839 | 0.260 % / 0.101 % | 0.001015 / 0.000393 |
| V invertida cercana a resonancia | Sí | Sí | 0.4957 / 0.1606 | 0.679 % / 0.221 % | **0.004784** / 0.001554 |

Las cuatro geometrías representativas cumplen simultáneamente en
`lambda/160`. El margen más ajustado es el de `abs(delta gamma)` de la
V cercana a resonancia en `lambda/160` (0.004784, contra un límite de
0.005 — un margen de solo 0.000216): es el único caso de todo el
estudio donde el candidato ganador se acerca tanto al límite. En
`lambda/320` todos los márgenes son holgados.

Para contexto, las dos geometrías de estrés en los mismos dos
candidatos (no participan en la decisión):

| Geometría (estrés) | λ/160: abs(ΔZ) | λ/160: error relativo | λ/320: abs(ΔZ) | λ/320: error relativo |
|---|---:|---:|---:|---:|
| V corta (sección 1.0 m) | 209.17 Ω | 10.72 % | 82.45 Ω | 4.41 % |
| V larga (sección 5.0 m) | 493.04 Ω | 15.80 % | 181.71 Ω | 6.02 % |

Ninguna de las dos cumpliría el criterio en ningún candidato (error
relativo muy por encima del 1 % en ambos casos, incluso con la
exención del límite absoluto por `|gamma| >= 0.98`); esto es
exactamente lo esperado y no cambia la decisión, que depende
únicamente de las 4 representativas.

## Conclusión explícita

> **`lambda/160` es ACEPTADA como densidad uniforme fija mínima**,
> bajo el criterio práctico ya fijado (1 Ω / 1 % / 0.005 en gamma
> contra `lambda/640`, resultados finitos y repetibles), aplicado a
> las 4 geometrías representativas simultáneamente.

`lambda/160` se elige por ser la más económica de las dos que
cumplen (se evaluó primero, según el orden de preferencia fijado
antes de correr el estudio); `lambda/320` también cumple, con
márgenes más holgados en las cuatro geometrías, y queda documentada
como la alternativa más conservadora si una fase posterior prefiere
más margen (por ejemplo, frente al ajustado 0.004784 de `abs(delta
gamma)` de la V cercana a resonancia en `lambda/160`).

Esta conclusión sigue sin decir nada sobre las geometrías de estrés:
ninguna densidad uniforme estudiada (ni siquiera `lambda/640`) las
acerca a un error absoluto o relativo razonable, porque el problema
ahí es la proximidad a `|gamma| = 1`, no la densidad de segmentación
(ver el diagnóstico dedicado). Un ADR de densidad fija asociado a
esta conclusión se documenta en
`docs/decisions/0007-use-uniform-nec-segmentation.md`; ese ADR
también deja constancia explícita de que los casos con `|gamma|`
próximo a 1 quedan fuera de su garantía.

## Verificación de esta revisión

- Script ejecutado completo dos veces (procesos separados): todos los
  resultados de Z/gamma/ROE fueron idénticos entre ambas corridas
  (solo difirieron los tiempos de simulación, como es esperable);
  incluida la línea de `CONCLUSION` (`lambda/160 ACEPTADA...`),
  idéntica en ambas corridas.
- Repetibilidad interna verificada en `lambda/80`, `lambda/160`,
  `lambda/320` y `lambda/640` (los tres candidatos evaluados más el
  ancla práctica): 24/24 combinaciones (6 geometrías × 4 niveles)
  "OK (idéntico)".
- `is_finite=True` y `error=""` en las 42 filas de `cases.csv` (sin
  cambios: 6 geometrías × 7 divisores, no se agregó ninguna
  simulación nueva, solo se generalizó la comparación sobre datos ya
  calculados).
- `python -m pytest` completo: 322 passed, sin cambios en
  `src/antsim`.
- `git diff --check`: sin errores reales (solo el aviso habitual de
  normalización LF/CRLF).
- Estado del índice de git verificado antes de tocar nada: ver el
  informe final de la conversación para el detalle de qué ya estaba
  en stage (no se alteró).
