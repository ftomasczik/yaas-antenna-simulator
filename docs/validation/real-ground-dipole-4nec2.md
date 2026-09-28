# Validación cruzada: dipolo a 10 m sobre tierra real Sommerfeld-Norton (PyNEC y 4nec2)

Fecha: 2026-09-27

> Esta validación se realizó bajo **AntSim**, el nombre de desarrollo
> del proyecto en ese momento; el producto pasó a llamarse **YAAS**
> antes de su primera publicación pública (ver
> `docs/decisions/0008-rename-to-yaas.md`). Los resultados numéricos y
> la tarjeta `GN` documentados aquí no cambian: no dependen del nombre
> del producto.

## 1. Objetivo

A diferencia de `docs/validation/monopole-perfect-ground-4nec2.md`
(que valida un flujo completo ya implementado en AntSim), esta
validación es **preparatoria**: no existe todavía `RealGroundEnvironment`
ni soporte de tierra real en `PyNecEngine` ni en el exportador. El
objetivo es confirmar, antes de escribir ese código, que:

- la llamada PyNEC `gn_card(2, 0, 13.0, 0.005, 0.0, 0.0, 0.0, 0.0)`
  (Sommerfeld-Norton) calcula una impedancia de entrada correcta,
  contrastada contra una implementación NEC2 externa (4nec2), no solo
  plausible;
- la tarjeta NEC de texto equivalente a esa llamada está bien
  formada, para cuando se escriba el exportador de 7B;
- la estrategia de barrido más segura para `PyNecEngine.simulate_sweep`
  (contexto único vs. contexto nuevo por frecuencia) tiene un costo de
  rendimiento aceptable.

Es continuación directa de `docs/research/nec-real-ground.md`
("Próxima investigación recomendada", punto 1) y no reemplaza esa
investigación: aquí solo se documenta la validación externa y la
decisión de arquitectura que de ella se deriva.

## 2. Geometría

Mismo dipolo de referencia ya usado en el resto de la fase 7A/7B,
elevado a 10 m sobre el plano de tierra en vez de en z=0:

- Conductor único, de (-5.03, 0, 10) a (5.03, 0, 10) m.
- Radio: 0.001 m.
- Segmentos: 101.
- Fuente: conductor 1, segmento 51 (centro del conductor).
- Tensión de excitación: 1 + j0 V.
- Impedancia de referencia: 50 ohm.
- Altura sobre tierra: 10 m (~0.47 lambda a 14.15 MHz).

## 3. Parámetros de tierra

- Método: Sommerfeld-Norton (`ground_type`/I1 = 2).
- Permitividad relativa: 13.0.
- Conductividad: 0.005 S/m.
- Sin radiales (`rad_wire_count`/I2 = 0).
- Sin segundo medio (F3-F6 = 0).

## 4. Diferencia entre llamada PyNEC y tarjeta NEC

`gn_card()` en PyNEC recibe **8 argumentos posicionales**:
`ground_type, rad_wire_count, F1, F2, F3, F4, F5, F6`. No existen I3
ni I4 en esa firma porque son campos reservados/en blanco que la
tarjeta NEC de texto sí exige explícitamente. La tarjeta NEC completa
tiene **4 campos enteros (I1-I4)** seguidos de **6 campos flotantes
(F1-F6)** — 10 valores en total tras `GN`, no 8. Confundir ambas
formas produce un archivo `.nec` mal formado (los valores se
desplazan un campo hacia la izquierda a partir de F1), aunque la
llamada Python equivalente sea correcta. Ver
`docs/research/nec-real-ground.md`, sección "Tarjetas NEC
correspondientes", para el registro completo de esta corrección.

## 5. Tarjeta GN completa correcta

```text
GN 2 0 0 0 13 0.005 0 0 0 0
```

`I1=2` (Sommerfeld-Norton), `I2=0` (sin radiales), `I3=0`, `I4=0`
(reservados), `F1=13` (permitividad relativa), `F2=0.005`
(conductividad, S/m), `F3=F4=F5=F6=0` (sin pantalla de radiales ni
segundo medio). Fuente documental:
[Ground Parameters (GN) — nec2.org](https://www.nec2.org/part_3/cards/gn.html).

Verificado programáticamente (conteo explícito de campos) en los 8
archivos `.nec` generados para esta validación: `I1=2, I2=0, I3=0,
I4=0, F1=13, F2=0.005`, con el orden de tarjetas
`GW < GE < GN < EX < FR < EN` y `EX` en el segmento 51.

## 6. Puntos independientes de PyNEC

Seis frecuencias, cada una con un contexto NEC recién creado
(`nec_context()` nuevo por punto, sin reutilizar estado entre
llamadas), tomados directamente de
`real-ground-independent-points.csv` (valores completos, no
redondeados):

| Frecuencia (MHz) | R (ohm) | X (ohm) | ROE (50 ohm) |
|---:|---:|---:|---:|
| 13.50 | 60.299986943615465 | -106.76423940161166 | 5.638466048890743 |
| 14.00 | 65.08459641124557 | -56.45649066280615 | 2.6756217934038533 |
| 14.15 | 66.5650394910273 | -41.357407423074825 | 2.125990900708858 |
| 14.50 | 69.95808168781186 | -6.052230206479039 | 1.4202416531690862 |
| 15.00 | 75.21206702937926 | 45.00907927216867 | 2.2665175109906905 |
| 15.50 | 81.79952406083048 | 97.18372807913387 | 4.3252667872220085 |

Las seis frecuencias se corrieron dos veces cada una (dos contextos
frescos independientes); ambas corridas coincidieron exactamente
(diferencia 0.0 en R y en X) en los seis casos.

## 7. Comparación puntual a 14.15 MHz

| Motor | Z (ohm) | ROE (50 ohm) |
|---|---|---:|
| PyNEC (contexto fresco) | 66.565039 - j41.357407 | 2.125991 |
| 4nec2 5.9.3 | 66.6 - j41.4 | 2.13 |

Diferencia (PyNEC menos 4nec2, con la precisión que reporta 4nec2):
~0.035 Ω en R, ~-0.04 Ω en X, ~-0.004 en ROE. 4nec2 redondea R y X a
un decimal y la ROE a dos decimales, así que la diferencia observada
está dentro de esa resolución de redondeo: no puede afirmarse, con
estos datos, que sea una discrepancia real entre motores en vez de un
efecto de la lectura redondeada.

## 8. Comparación de barrido en 13.5, 14.5 y 15.5 MHz

Los valores de PyNEC son los mismos de la tabla de la sección 6
(contexto fresco por frecuencia), no los de un barrido de contexto
único:

| Frecuencia (MHz) | PyNEC R (Ω) | PyNEC X (Ω) | PyNEC ROE | 4nec2 R (Ω) | 4nec2 X (Ω) | 4nec2 ROE | diff R (Ω) | diff X (Ω) | diff ROE |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 13.5 | 60.299987 | -106.764239 | 5.638466 | 60.2981 | -106.78 | 5.64002 | 0.0019 | 0.0158 | -0.0016 |
| 14.5 | 69.958082 | -6.052230 | 1.420242 | 69.9534 | -6.0735 | 1.4203 | 0.0047 | 0.0213 | -0.0001 |
| 15.5 | 81.799524 | 97.183728 | 4.325267 | 81.7964 | 97.1602 | 4.32414 | 0.0031 | 0.0235 | 0.0011 |

Todas las diferencias son del orden de 0.002-0.024 Ω, dentro de la
resolución de redondeo de 4nec2 y de las diferencias normales
esperables entre dos implementaciones independientes de NEC2
(PyNEC/necpp frente al motor usado por 4nec2).

## 9. Mediciones de rendimiento

Medido para el mismo dipolo a 10 m, barridos de 11, 81 y 201 puntos
entre 13.5 y 15.5 MHz:

| Puntos | Contexto único | Contexto nuevo por frecuencia |
|---:|---:|---:|
| 11 | ~505-511 ms | ~449-462 ms |
| 81 | ~3360-3456 ms | ~3381-3494 ms |
| 201 | ~8517-8637 ms | ~8333-8454 ms |

Aproximadamente 42 ms por punto en promedio, sin importar la
estrategia. Para referencia: 11 puntos ~0.45-0.50 s en total; 81
puntos ~3.4 s; 201 puntos ~8.5 s.

## 10. Contexto único frente a contexto por frecuencia

- **Correctitud:** con el dipolo a 10 m, la diferencia entre el
  barrido de contexto único y el cálculo independiente por frecuencia
  fue del orden de 1e-7 a 1e-8 Ω — ruido de punto flotante, no un
  error sistemático. Esto contrasta con el monopolo alimentado en
  z=0 estudiado en `docs/research/nec-real-ground.md`, donde la misma
  comparación mostró una discrepancia sistemática de ~0.6-0.9 Ω.
- **Orden del barrido:** ejecutar el barrido de contexto nuevo en
  orden ascendente o descendente no cambió ningún resultado
  (diferencia exactamente 0.0 en R y en X, frecuencia por
  frecuencia).
- **Rendimiento:** según la sección 9, ninguna estrategia fue
  consistentemente más lenta que la otra; el costo está dominado por
  el cálculo de Sommerfeld-Norton en sí (~40 ms/punto), no por la
  creación del contexto.

## 11. Decisión para AntSim

**`PyNecEngine.simulate_sweep`, para `RealGroundEnvironment` con
Sommerfeld-Norton, debe crear un contexto NEC independiente por cada
frecuencia del barrido**, en vez de reutilizar un único contexto con
`fr_card(0, points, start, step)` como ya hace hoy para espacio libre
y tierra perfecta.

Esta decisión prioriza la **consistencia** por sobre un ahorro de
rendimiento que, de todos modos, esta validación no encontró (sección
9: ambas estrategias tuvieron un costo equivalente). Es
deliberadamente conservadora: aunque el dipolo a 10 m validado aquí no
muestra discrepancias relevantes entre estrategias, AntSim no puede
garantizar que todo conductor con tierra real quedará siempre lejos
del plano de tierra — un monopolo alimentado en la base, tocando z=0,
es un caso de uso legítimo y esperado, y es exactamente el caso donde
`docs/research/nec-real-ground.md` sí observó una discrepancia
sistemática. La estrategia de contexto nuevo por frecuencia se adopta
entonces de forma general para Sommerfeld-Norton, no solo para las
geometrías elevadas que, como este dipolo, no la necesitarían.

## 12. Limitaciones

- Esta validación cubre **solo impedancia de entrada y ROE**. No
  valida patrones de radiación ni ganancia.
- El suelo se modeló como **homogéneo** (un único medio); no se probó
  ningún segundo medio ni tierra estratificada.
- **Sin radiales** (`rad_wire_count=0`): no se validó ninguna pantalla
  de radiales con tierra real.
- **Sin conductores enterrados**: el dipolo está enteramente por
  encima del plano de tierra (z=10 m); no se validó ningún conductor
  que cruce o quede bajo z=0 con tierra real.
- **No valida el método de coeficiente de reflexión** (`ground_type=0`):
  esta validación cubre exclusivamente Sommerfeld-Norton, consistente
  con la recomendación de alcance de 7B (coeficiente de reflexión
  pospuesto).
- Los valores de 4nec2 fueron reportados manualmente por Federico
  Tomasczik tras ejecutar el programa; no se automatizó ni se
  scriptó la lectura de 4nec2 (a diferencia de PyNEC, que sí corrió
  mediante script).

## 13. Instrucciones de reproducción con 4nec2

Los archivos `.nec` de esta validación se generaron fuera del
repositorio, en `C:\dev\antsim-ground-validation\real-ground\`, y no
se incorporan a AntSim (ni el script que los generó, ni los CSV, ni
capturas de pantalla). Para reproducir la comparación:

1. Abrir 4nec2 5.9.3 (o una versión compatible).
2. **File -> Open** y seleccionar el archivo `.nec` puntual
   correspondiente (por ejemplo, el de 14.15 MHz) o el de barrido de
   81 puntos, según qué fila de las tablas anteriores se quiera
   reproducir. Cada archivo contiene comentarios `CM` con la
   frecuencia y los parámetros de tierra usados.
3. Ejecutar el cálculo (**Calculate -> Currents/Impedance** para un
   punto; **Calculate -> Freq. sweep** para el barrido).
4. Leer la impedancia de entrada del segmento 51 del conductor 1 en
   la ventana de resultados.
5. Configurar manualmente la impedancia de referencia (50 ohm) en
   4nec2 si se desea ver la ROE directamente, igual que en
   `docs/validation/monopole-perfect-ground-4nec2.md`.
6. Comparar contra las tablas de las secciones 6-8 de este documento.

Para regenerar los mismos archivos `.nec` y los mismos cálculos de
PyNEC desde cero (fuera del repositorio, sin afectar AntSim), la
tarjeta GN de la sección 5 y la geometría de la sección 2 son
suficientes para reconstruir el modelo en cualquier herramienta NEC2
compatible.
