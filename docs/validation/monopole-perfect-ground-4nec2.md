# Validación cruzada: monopolo sobre tierra perfecta (esquema v2, PyNEC y 4nec2)

Fecha: 2026-09-27

## Objetivo

Validar el flujo completo de la fase 7A para tierra perfecta, de punta
a punta, con un modelo real y no solo con pruebas automatizadas
aisladas:

```text
.antsim (schema 2)
    -> PerfectGroundEnvironment
    -> PyNecEngine (geometry_complete(1) + gn_card(1, ...))
    -> exportación NEC (GE 1 / GN 1)
    -> 4nec2
```

Se comprueba que las cuatro etapas (esquema, motor, exportador y una
implementación NEC externa) coinciden entre sí, y que el resultado
también es consistente con una predicción analítica independiente
(teoría de imágenes).

## Herramientas

- AntSim (rama `feat/perfect-ground`, posterior a 0.1.1)
- PyNEC / NEC2++
- 4nec2 V5.9.3
- Windows x64

## Modelo

**Monopolo de 20 metros sobre tierra perfecta**
(`examples/monopole-20m-perfect-ground.antsim`):

- Frecuencia: 14.150 MHz.
- Conductor vertical único, de z=0 a z=5.03 m (toca el plano de
  tierra en su base).
- Radio del conductor: 0.001 m.
- Segmentos: 38.
- Fuente: conductor 1, segmento 1 (en la base, contra el plano de
  tierra).
- Impedancia de referencia: 50 ohm.
- Entorno: `perfect_ground`.
- Sin cargas concentradas.

## Predicción analítica

Un monopolo cuarto de onda alimentado en su base contra un plano de
tierra perfectamente conductor es, por teoría de imágenes,
eléctricamente equivalente a la mitad superior de un dipolo de media
onda: la corriente de imagen en el plano de tierra reproduce la mitad
inferior que el dipolo tendría en espacio libre. La impedancia de
entrada resultante es exactamente la mitad de la del dipolo
equivalente (parte real y parte imaginaria, ambas a la mitad).

- Dipolo de referencia (espacio libre, mismo brazo de 5.03 m,
  14.150 MHz): 67.43 - j31.25 ohm
  (`docs/decisions/0002-use-nec2plusplus.md`).
- Mitad por teoría de imágenes: 33.72 - j15.63 ohm.

La teoría de imágenes permite una comprobación **independiente** del
orden de magnitud y del signo esperados, ya que no depende de ningún
motor NEC en particular; sin embargo, **no sustituye** la comparación
directa entre AntSim/PyNEC y una implementación NEC externa (4nec2),
que es lo que valida específicamente que la exportación de AntSim es
correcta.

## AntSim/PyNEC

Simulación de frecuencia única (`antsim simulate`):

- Z = 33.79 - j15.62 ohm
- ROE = 1.72 respecto de 50 ohm

Combinación de llamadas usada por `PyNecEngine` para este entorno
(ver `docs/research/nec-ground-configuration.md`):

```text
geometry_complete(1)
gn_card(1, 0, 0, 0, 0, 0, 0, 0)
```

Barrido (`antsim sweep`), 13.500-15.500 MHz, 81 puntos:

- Resonancia aproximada: 14.450 MHz, Z = 35.99 - j0.30 ohm, ROE = 1.39.
- ROE mínima: 1.38, a 14.500 MHz.
- Ancho de banda para ROE <= 2.00: 14.025-15.050 MHz (1025.0 kHz,
  7.05 % porcentual).

Ninguno de estos tres resultados (resonancia, ROE mínima, ancho de
banda) quedó truncado por los límites del barrido: los tres caen en
el interior del rango 13.500-15.500 MHz (ver el diagnóstico de
límites de barrido de `SweepResult`, que no marcó ninguna advertencia
de truncamiento para este barrido).

## NEC exportado

Tarjetas relevantes, en el orden en que aparecen en el archivo
generado por `antsim export-nec`:

```text
GW 1 38 0 0 0 0 0 5.03 0.001
GE 1
GN 1 0 0 0 0 0 0 0
EX 0 1 1 0 1 0
FR 0 1 0 0 14.15 0
```

`GE 1` termina la geometría e indica que hay un plano de tierra
activo: NEC2 aplica el método de imágenes a la estructura declarada.
`GN 1 0 0 0 0 0 0 0` declara que ese plano de tierra es perfectamente
conductor (`ground_type=1`), sin radiales (`rad_wire_count=0`); los
seis parámetros restantes no aplican a este tipo de tierra. `GE`
siempre precede a `GN`, nunca al revés.

## Resultado de 4nec2

4nec2 V5.9.3 abrió el archivo NEC exportado por AntSim sin requerir
ninguna modificación, y a 14.150 MHz mostró:

- Z = 33.8 - j15.6 ohm
- ROE = 1.72 respecto de 50 ohm
- 38 segmentos
- Eficiencia: 100 %
- Tierra perfecta detectada correctamente
- Sin errores

4nec2 mostró además el siguiente mensaje informativo:

```text
GROUND PLANE SPECIFIED.
WHERE WIRE ENDS TOUCH GROUND, CURRENT WILL BE INTERPOLATED TO IMAGE.
PERFECT GROUND
```

Este mensaje **no es una advertencia de error**: confirma que 4nec2
detectó que el extremo del conductor toca z=0 y que aplica
correctamente su imagen, exactamente el comportamiento esperado para
un monopolo alimentado en la base contra tierra perfecta.

No se incorpora ninguna captura de pantalla al repositorio; los
valores observados arriba son suficientes para documentar el
resultado.

Nota sobre el voltaje mostrado por 4nec2: la interfaz de 4nec2
normaliza la potencia de entrada a 100 W y muestra un voltaje
calculado a partir de esa normalización. Ese voltaje **no** debe
compararse con la amplitud unitaria (1 V) de la fuente de tensión que
usa AntSim en la tarjeta `EX`; ambos programas resuelven el mismo
circuito lineal, así que la impedancia de entrada (independiente de
la amplitud de excitación) es la magnitud comparable entre ambos, no
el voltaje mostrado en la interfaz.

## Comparación y conclusión

| Fuente | Impedancia | ROE (50 ohm) |
|---|---:|---:|
| Predicción analítica (teoría de imágenes) | 33.72 - j15.63 ohm | — |
| AntSim / PyNEC | 33.79 - j15.62 ohm | 1.72 |
| 4nec2 V5.9.3 | 33.8 - j15.6 ohm | 1.72 |

Diferencia AntSim - 4nec2: 0.01 ohm en resistencia, 0.02 ohm en
reactancia.

**Conclusión:**

- AntSim/PyNEC y 4nec2 coinciden entre sí dentro del margen de
  redondeo ya observado en otras validaciones de este proyecto
  (`docs/validation/nec-export-4nec2.md`,
  `docs/validation/mmana-hentenna-nec2.md`).
- El resultado de ambos coincide también con la predicción
  independiente de la teoría de imágenes (33.72 - j15.63 ohm), lo que
  descarta un acuerdo casual entre AntSim y 4nec2 debido a un error
  compartido.
- El esquema `.antsim` v2, el motor (`PyNecEngine` con
  `geometry_complete(1)`/`gn_card(1, ...)`) y la exportación NEC
  (`GE 1`/`GN 1`) son coherentes entre sí para tierra perfecta.
- Esta validación cubre **tierra perfecta únicamente**. No valida
  tierra real (con pérdidas, aproximación de Fresnel o Sommerfeld):
  eso queda para una fase posterior (7B/7D).
- Esta validación **no** cubre patrones de radiación, ganancia,
  radiales de pantalla de tierra ni conductores enterrados (bajo el
  plano de tierra): ninguno de esos aspectos se ejercitó aquí.

## Reproducibilidad

```powershell
antsim validate .\examples\monopole-20m-perfect-ground.antsim

antsim simulate .\examples\monopole-20m-perfect-ground.antsim

antsim sweep .\examples\monopole-20m-perfect-ground.antsim

antsim export-nec `
    .\examples\monopole-20m-perfect-ground.antsim `
    .\monopole-20m-perfect-ground.nec

antsim export-nec `
    --sweep `
    .\examples\monopole-20m-perfect-ground.antsim `
    .\monopole-20m-perfect-ground-sweep.nec
```
